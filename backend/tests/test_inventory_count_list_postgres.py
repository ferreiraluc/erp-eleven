"""PostgreSQL proves count-sheet request locking; SQLite cannot prove it."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event, Lock
import uuid

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Usuario, Vendedor, Cliente
from app.models.address_book import SavedAddress
from app.models.assistant import utcnow
from app.models.inventory import Item, Supplier, StockMovement
from app.models.pdv import PdvCliente
from app.models.printing import PrintDevice, PrintJob
from app.models.usuario import UsuarioRole
from app.schemas.inventory_count_list import PrintList
from app.services import inventory_count_list as lists
from test_access_postgres import pg  # noqa: F401


@pytest.mark.parametrize('different_device', [False, True])
def test_concurrent_confirmation_serializes_before_expiry_and_creates_one_job(pg, monkeypatch, different_device):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in
        (Usuario, Vendedor, Cliente, PdvCliente, SavedAddress, Supplier, Item, StockMovement, PrintDevice, PrintJob)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    clock = [utcnow()]
    monkeypatch.setattr(lists, 'utcnow', lambda: clock[0])
    with factory() as db:
        user = Usuario(nome='Fixture', email='inventory-count@example.test', senha_hash='unused', role=UsuarioRole.GERENTE)
        devices = [PrintDevice(name=f'HP fixture {i}', token_hash=uuid.uuid4().hex * 2) for i in range(2)]
        db.add(user); db.add_all(devices); db.flush()
        item = Item(name='Fixture camiseta', sku_internal='COUNT-TEST', stock_loja=2, stock_deposito=7, current_stock=9)
        db.add(item); db.commit()
        user_id, item_id = user.id, item.id
        value = lists.preview(db, user_id, [item_id])
        key = uuid.uuid4()
        bodies = [PrintList(snapshot=value['snapshot'], signature=value['signature'], request_key=key,
                            device_id=devices[i if different_device else 0].id, confirm=True) for i in range(2)]
    barrier, both_requests, guard = Barrier(2), Event(), Lock()
    lock_attempts, renders = [], []
    original_render = lists.render
    def observe(conn, cursor, statement, *args):
        if 'pg_advisory_xact_lock' in statement:
            with guard:
                lock_attempts.append(True)
                if len(lock_attempts) == 2:
                    both_requests.set()
    sa.event.listen(isolated, 'before_cursor_execute', observe)
    def render(snapshot):
        renders.append(True)
        assert both_requests.wait(timeout=5), 'Both independent sessions must reach the request lock'
        # Simulate a preview expiring while the first confirmation is rendering.
        clock[0] += timedelta(hours=2)
        return original_render(snapshot)
    monkeypatch.setattr(lists, 'render', render)
    def run(body):
        with factory() as db:
            user = db.get(Usuario, user_id)
            barrier.wait(timeout=5)
            try:
                return lists.enqueue(db, user, body)
            except HTTPException as exc:
                db.rollback()
                return {'error': exc.status_code, 'detail': exc.detail}
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, bodies))
        assert len(renders) == 1
        if different_device:
            assert sorted(result.get('error', 200) for result in results) == [200, 409]
            assert isinstance(next(result['detail'] for result in results if 'error' in result), str)
        else:
            assert results[0]['id'] == results[1]['id']
        with factory() as db:
            assert db.query(PrintJob).count() == 1
            assert db.query(StockMovement).count() == 0
            assert db.query(SavedAddress).count() == 0
            assert db.get(Item, item_id).stock_loja == 2 and db.get(Item, item_id).stock_deposito == 7
    finally:
        sa.event.remove(isolated, 'before_cursor_execute', observe)
        isolated.dispose()
