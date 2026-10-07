"""Migration and pair consolidation against disposable PostgreSQL only."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg, upgrade
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.pdv import PdvCliente
from app.models.address_book import SavedAddress
from app.models.access import AuditEvent
from app.services.customer_maintenance import merge_customers
from app.services.address_book import save_or_reuse


def test_customer_alias_migration_preserves_rows_and_enforces_references(pg):
    engine, schema = pg
    target, source = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE clientes(id uuid PRIMARY KEY, nome text, ativo boolean)')
        conn.execute(sa.text("INSERT INTO clientes VALUES (:id,'Nome original',true)"), [{'id':target},{'id':source}])
        upgrade(conn, 'e1f2a3b4c5d6_customer_merge_aliases.py')
        assert conn.execute(sa.text('SELECT count(*) FROM clientes WHERE merged_into_id IS NULL AND ativo')).scalar() == 2
    for destination, active in [(target, False), (uuid.uuid4(), False), (source, True)]:
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
                conn.execute(sa.text('UPDATE clientes SET merged_into_id=:destination, ativo=:active WHERE id=:target'),
                             {'target':target, 'destination':destination, 'active':active})
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.execute(sa.text('UPDATE clientes SET merged_into_id=:target, ativo=false WHERE id=:source'), {'target':target,'source':source})
        assert conn.execute(sa.text('SELECT nome FROM clientes WHERE id=:source'), {'source':source}).scalar() == 'Nome original'


def test_customer_merge_is_atomic_serialized_and_future_addresses_reuse_principal(pg, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in
            (Usuario, Vendedor, Cliente, PdvCliente, Pedido, Rastreamento, SavedAddress, AuditEvent)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        uid, target_id, source_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with factory() as db:
            db.add(Usuario(id=uid,nome='Fixture',email='fixture@example.test',senha_hash='unused'))
            db.add_all([Cliente(id=target_id,nome='Mesmo Cliente'), Cliente(id=source_id,nome='MESMO CLIENTE')]); db.flush()
            db.add(SavedAddress(label='Casa',data={'pais':'PY','nome':'Mesmo Cliente','cidade':'Asunción'},cliente_id=source_id,created_by=uid))
            db.commit()
            plan = merge_customers(db, target_id, source_id)['plan_token']; db.rollback()
            merge_customers(db, target_id, source_id, apply=True, expected_plan=plan)
            db.rollback()
            assert not db.get(Cliente, source_id).merged_into_id
            assert db.query(SavedAddress).one().cliente_id == source_id
            assert db.query(AuditEvent).count() == 0
        barrier = Barrier(2)
        def run(_):
            with factory() as db:
                barrier.wait(timeout=10)
                result = merge_customers(db, target_id, source_id, apply=True, expected_plan=plan)
                db.commit(); return result['state']
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(run, range(2))) == ['already_merged','merged']
        with factory() as db:
            assert db.query(AuditEvent).filter_by(action='customer_merged').count() == 1
            assert db.query(SavedAddress).one().cliente_id == target_id
            address, _ = save_or_reuse(db, {'pais':'PY','nome':'Mesmo Cliente','cidade':'Encarnación'}, uid)
            assert address.cliente_id == target_id and db.query(Cliente).count() == 2
    finally:
        isolated.dispose()
