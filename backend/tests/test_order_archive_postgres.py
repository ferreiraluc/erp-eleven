"""PostgreSQL locks and additive archival migration, on a disposable schema."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Pedido, Usuario
from app.models.access import AuditEvent
from app.models.pedido_archive import PedidoArchiveOperation
from app.schemas.pedido_archive import ArchiveOrders
from app.services import order_archive
from test_access_postgres import pg, upgrade
from test_order_archive import ARCHIVE_TABLES, add_order
from test_order_reservations import seed


def test_archive_migration_preserves_existing_orders_and_references(pg):
    engine, schema = pg
    uid, oid = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE usuarios (id uuid PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE pedidos (id uuid PRIMARY KEY, description text NOT NULL)')
        conn.execute(sa.text('INSERT INTO usuarios VALUES (:id)'), {'id': uid})
        conn.execute(sa.text('INSERT INTO pedidos VALUES (:id, :description)'), {'id': oid, 'description': 'Preserved legacy order'})
        upgrade(conn, 'b0k1l2m3n4o5_order_archive.py')
        row = conn.execute(sa.text('SELECT id, description, archived_at, archived_by FROM pedidos')).one()
        assert row == (oid, 'Preserved legacy order', None, None)
        assert conn.execute(sa.text('SELECT COUNT(*) FROM pedido_archive_operations')).scalar() == 0
        assert 'ix_pedidos_archived_at' in {index['name'] for index in sa.inspect(conn).get_indexes('pedidos', schema=schema)}
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.execute(sa.text('UPDATE pedidos SET archived_by=:id'), {'id': uuid.uuid4()})


@pytest.fixture
def archive_pg(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=ARCHIVE_TABLES)
    factory = sessionmaker(bind=isolated, autoflush=False)
    uid, *_ = seed(factory)
    try:
        yield factory, uid
    finally:
        isolated.dispose()


@pytest.mark.parametrize('same_request', [True, False])
def test_concurrent_archive_is_single_effect_and_distinct_stale_preview_is_rejected(archive_pg, same_request):
    factory, uid = archive_pg
    order_id = add_order(factory, uid)
    with factory() as db:
        preview = order_archive.preview(db, db.get(Usuario, uid))
    first = dict(request_id=uuid.uuid4(), confirm=True, expected_count=preview['total'], plan_token=preview['plan_token'])
    second = first if same_request else {**first, 'request_id': uuid.uuid4()}
    barrier = Barrier(2)

    def execute(data):
        with factory() as db:
            user = db.get(Usuario, uid)
            barrier.wait(timeout=5)
            try:
                result = order_archive.confirm(db, user, ArchiveOrders(**data))
                db.commit()
                return result
            except HTTPException as exc:
                db.rollback()
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(execute, (first, second)))
    if same_request:
        assert results[0] == results[1] and results[0]['archived_count'] == 1
    else:
        assert results.count(409) == 1
        assert next(result for result in results if isinstance(result, dict))['archived_count'] == 1
    with factory() as db:
        assert db.get(Pedido, order_id).archived_by == uid
        assert db.query(Pedido).count() == db.query(PedidoArchiveOperation).count() == 1
        assert db.query(AuditEvent).filter_by(action='orders_archived').count() == 1
