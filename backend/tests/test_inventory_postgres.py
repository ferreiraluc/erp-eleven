"""Concurrency checks against disposable local PostgreSQL, never the ERP database."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg  # isolated schema, always cleaned up
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier, StockMovement
from app.services.inventory_service import create_movement, StockMovementError


def test_concurrent_exits_reload_preloaded_stock_under_lock(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Supplier, Item, StockMovement,
        )])
        factory = sessionmaker(bind=isolated, autoflush=False)
        user_id, item_id = uuid.uuid4(), uuid.uuid4()
        with factory() as db:
            db.add(Usuario(id=user_id, nome="Local fixture", email="fixture@example.com", senha_hash="unused"))
            db.flush()
            db.add(Item(id=item_id, name="Local fixture", sku_internal="LOCAL-001", current_stock=10,
                        stock_loja=10, stock_deposito=0, created_by=user_id))
            db.commit()

        ready = Barrier(2)

        def exit_stock(_):
            with factory() as db:
                # Both callers already hold an ORM instance with the old balance.
                # Row locking alone does not refresh SQLAlchemy's identity map.
                preloaded = db.get(Item, item_id)
                assert preloaded.current_stock == 10
                ready.wait(timeout=10)
                try:
                    movement = create_movement(db, item_id, "exit", 8, user_id, location="loja")
                    remaining = movement.quantity_after
                    db.commit()
                    return "success", remaining
                except StockMovementError as exc:
                    db.rollback()
                    return "rejected", exc.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(exit_stock, range(2)))
        assert sorted(results) == [("rejected", 409), ("success", 2)]
        with factory() as db:
            item = db.get(Item, item_id)
            assert (item.current_stock, item.stock_loja, item.stock_deposito) == (2, 2, 0)
            movements = db.query(StockMovement).all()
            assert len(movements) == 1
            assert (movements[0].quantity_before, movements[0].quantity_after, movements[0].quantity) == (10, 2, 8)
    finally:
        isolated.dispose()
