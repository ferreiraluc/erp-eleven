"""Freight tracking respects the parent/code/row lock order during manual edits."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from app.config import settings
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.address_book import SavedAddress, FreightOrder
from app.models.pdv import PdvCliente
from app.models.printing import PrintDevice, PrintJob
from app.services import superfrete
from app.services.rastreamento_sync import RastreamentoSyncService
from app.services.tracking_codes import lock_tracking_codes


@pytest.fixture
def shipping_pg(pg, monkeypatch):
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    def no_provider(*args, **kwargs):
        raise AssertionError('Concurrency checks never contact providers or printers')
    monkeypatch.setattr(superfrete, 'call', no_provider)
    monkeypatch.setattr(superfrete, 'label_pdf', no_provider)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Cliente, Pedido, Rastreamento, PdvCliente,
            SavedAddress, PrintDevice, PrintJob, FreightOrder,
        )])
        factory = sessionmaker(bind=isolated, autoflush=False)
        uid, cid, oid, rid, fid = (uuid.uuid4() for _ in range(5))
        with factory() as db:
            db.add(Usuario(id=uid, nome='Gestor QA', email='tracking-lock-qa@example.test', senha_hash='unused'))
            db.add(Cliente(id=cid, nome='Destinatário Sintético'))
            db.add(Pedido(id=oid, numero_pedido='QA-LOCK-ORDER', descricao='Snapshot preservado', valor_total=10))
            db.flush()
            db.add(Rastreamento(id=rid, codigo_rastreio='QA111111111BR', pedido_id=oid,
                destinatario='Destinatário Sintético', destino='Destino preservado'))
            db.add(FreightOrder(id=fid, request_key=uuid.uuid4(), user_id=uid, environment='production',
                state='released', tracking='QA111111111BR', rates=[], payload={
                    '_customer_id': str(cid), 'to': {'name': 'Destinatário Sintético', 'city': 'Destino QA'},
                    'from': {'city': 'Origem QA'},
                }))
            db.commit()
        yield factory, isolated, (uid, cid, oid, rid, fid)
    finally:
        isolated.dispose()


def sync_worker(factory, ids, start):
    _, _, _, rid, fid = ids
    with factory() as db:
        db.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
        connection_info = db.connection().info
        connection_info['freight_sync_test'] = True
        try:
            # Keep the cached row alive to exercise populate_existing after waiting.
            cached = db.get(Rastreamento, rid)
            assert cached.codigo_rastreio == 'QA111111111BR'
            freight = db.get(FreightOrder, fid)
            start.wait(timeout=10)
            superfrete.sync_tracking(db, freight)
            db.commit()
        finally:
            connection_info.pop('freight_sync_test', None)


def observe_parent_wait(engine, waiting, attempted):
    def before_execute(conn, cursor, statement, parameters, context, many):
        if not conn.info.get('freight_sync_test'):
            return
        statement = statement.upper()
        if 'FOR UPDATE' in statement and 'FROM PEDIDOS' in statement:
            attempted.append('parent')
            waiting.set()
        elif 'PG_ADVISORY_XACT_LOCK' in statement:
            attempted.append('code')
        elif 'FOR UPDATE' in statement and 'FROM RASTREAMENTOS' in statement:
            attempted.append('parcel')
    sa.event.listen(engine, 'before_cursor_execute', before_execute)
    return before_execute


def test_freight_sync_waits_for_parent_before_code_while_order_links_same_code(shipping_pg):
    factory, engine, ids = shipping_pg
    uid, cid, oid, rid, _ = ids
    start, waiting, attempted = Barrier(2), Event(), []
    listener = observe_parent_wait(engine, waiting, attempted)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with factory() as editor:
                editor.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
                parent = editor.query(Pedido).filter(Pedido.id == oid).with_for_update().one()
                syncing = executor.submit(sync_worker, factory, ids, start)
                start.wait(timeout=10)
                assert waiting.wait(timeout=10)
                # The parent is already held. A freight worker holding the code
                # here would deadlock with this ordinary parent→code→parcel flow.
                linked, created = RastreamentoSyncService.buscar_ou_criar_rastreamento(
                    editor, 'QA111111111BR', parent, uid)
                assert not created and linked.id == rid
                editor.commit()
            syncing.result(timeout=10)
        assert attempted[:3] == ['parent', 'code', 'parcel']
        with factory() as db:
            assert db.query(Rastreamento).count() == 1
            row = db.get(Rastreamento, rid)
            assert row.cliente_id == cid and row.pedido_id == oid
    finally:
        sa.event.remove(engine, 'before_cursor_execute', listener)


@pytest.mark.parametrize('changed_field', ['code', 'parent'])
def test_freight_sync_rechecks_code_and_parent_after_concurrent_edit(shipping_pg, changed_field):
    factory, engine, ids = shipping_pg
    _, _, oid, rid, _ = ids
    start, waiting, attempted = Barrier(2), Event(), []
    listener = observe_parent_wait(engine, waiting, attempted)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with factory() as editor:
                editor.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
                editor.query(Pedido.id).filter(Pedido.id == oid).with_for_update().one()
                if changed_field == 'code':
                    lock_tracking_codes(editor, ['QA222222222BR'])
                row = editor.query(Rastreamento).filter(Rastreamento.id == rid).with_for_update().one()
                if changed_field == 'code':
                    row.codigo_rastreio = 'QA222222222BR'
                else:
                    row.pedido_id = None
                editor.flush()
                syncing = executor.submit(sync_worker, factory, ids, start)
                start.wait(timeout=10)
                assert waiting.wait(timeout=10)
                editor.commit()
            syncing.result(timeout=10)
        with factory() as db:
            assert db.query(Rastreamento).count() == 1
            row = db.get(Rastreamento, rid)
            assert row.cliente_id is None
            assert row.codigo_rastreio == ('QA222222222BR' if changed_field == 'code' else 'QA111111111BR')
            assert row.pedido_id == (None if changed_field == 'parent' else oid)
            assert row.destino == 'Destino preservado'
    finally:
        sa.event.remove(engine, 'before_cursor_execute', listener)


def test_new_parent_created_while_waiting_for_code_is_deferred_until_next_refresh(shipping_pg):
    factory, engine, ids = shipping_pg
    _, cid, oid, rid, fid = ids
    with factory() as db:
        db.query(Rastreamento).filter(Rastreamento.id == rid).delete()
        db.commit()
    start, waiting = Barrier(2), Event()
    def before_execute(conn, cursor, statement, parameters, context, many):
        if conn.info.get('freight_sync_test') and 'pg_advisory_xact_lock' in statement:
            waiting.set()
    def sync_missing():
        with factory() as db:
            db.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
            connection_info = db.connection().info
            connection_info['freight_sync_test'] = True
            try:
                assert db.get(Rastreamento, rid) is None
                freight = db.get(FreightOrder, fid)
                start.wait(timeout=10)
                superfrete.sync_tracking(db, freight)
                db.commit()
            finally:
                connection_info.pop('freight_sync_test', None)
    sa.event.listen(engine, 'before_cursor_execute', before_execute)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with factory() as editor:
                editor.query(Pedido.id).filter(Pedido.id == oid).with_for_update().one()
                lock_tracking_codes(editor, ['QA111111111BR'])
                editor.add(Rastreamento(id=rid, codigo_rastreio='QA111111111BR', pedido_id=oid,
                    destinatario='Destinatário Sintético', destino='Destino preservado'))
                editor.flush()
                syncing = executor.submit(sync_missing)
                start.wait(timeout=10)
                assert waiting.wait(timeout=10)
                editor.commit()
            syncing.result(timeout=10)
        with factory() as db:
            row = db.get(Rastreamento, rid)
            assert row.cliente_id is None and row.pedido_id == oid
            superfrete.sync_tracking(db, db.get(FreightOrder, fid))
            assert row.cliente_id == cid and row.destino == 'Destino preservado'
            assert db.query(Rastreamento).count() == 1
    finally:
        sa.event.remove(engine, 'before_cursor_execute', before_execute)
