"""Lock/re-read behavior on disposable local PostgreSQL schemas."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic, sleep
import uuid

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from app.api.endpoints.pdv import _lock_sale_stock
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier
from app.schemas.pdv import PdvSaleItemCreate


@pytest.mark.parametrize("field", ("current_stock", "stock_loja", "stock_deposito"))
def test_pdv_waits_for_item_lock_then_reloads_newly_unknown_balance(pg, field):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (Usuario, Vendedor, Supplier, Item)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        item_id = uuid.uuid4()
        with factory() as db:
            db.add(Item(id=item_id, name="Synthetic local fixture", sku_internal="LOCAL-PDV",
                        current_stock=10, stock_loja=6, stock_deposito=4))
            db.commit()

        reader_ready = Queue()
        start_lock = Event()

        def read_for_sale():
            with factory() as db:
                preloaded = db.get(Item, item_id)
                assert (preloaded.current_stock, preloaded.stock_loja, preloaded.stock_deposito) == (10, 6, 4)
                reader_ready.put(db.scalar(sa.text("SELECT pg_backend_pid()")))
                assert start_lock.wait(timeout=10)
                try:
                    _lock_sale_stock(db, [PdvSaleItemCreate(item_id=item_id, item_name="Fixture", unit_price_gs=1)])
                    return "unexpected_success"
                except HTTPException as error:
                    return error.status_code, error.detail

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(read_for_sale)
            reader_pid = reader_ready.get(timeout=10)
            with factory() as writer:
                item = writer.query(Item).filter(Item.id == item_id).with_for_update().one()
                setattr(item, field, None)
                writer.flush()
                start_lock.set()
                deadline = monotonic() + 5
                blocked = False
                with engine.connect() as observer:
                    while monotonic() < deadline:
                        blocked = bool(observer.scalar(sa.text("SELECT pg_blocking_pids(:pid)"), {"pid": reader_pid}))
                        if blocked:
                            break
                        sleep(0.01)
                assert blocked, "The PDV query must wait for the writer's row lock"
                writer.commit()
            status, detail = result.result(timeout=10)
            assert status == 409 and "Estoque não informado" in detail
        with factory() as db:
            # The reader rolls back only its transaction, preserving the writer's NULL.
            assert getattr(db.get(Item, item_id), field) is None
    finally:
        isolated.dispose()
