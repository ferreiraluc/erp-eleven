"""Recovery migration and row leases on disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import copy
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg, upgrade
from test_freight_recovery import offline_provider, order, RATES
from app.database import Base
from app.models import Usuario, Vendedor, Cliente
from app.models.usuario import UsuarioRole
from app.models.address_book import SavedAddress, FreightOrder
from app.models.assistant import AssistantIdentity, AssistantMessage, AssistantDelivery
from app.models.pdv import PdvCliente
from app.models.printing import PrintDevice, PrintJob
from app.services import freight_recovery as recovery, superfrete as sf


def test_migration_preserves_existing_orders_without_scheduling_or_paying(pg):
    engine, schema = pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE freight_orders(id uuid PRIMARY KEY, state varchar(30), payload jsonb, price numeric(12,2), provider_id varchar(100), label_pdf bytea)')
        for state in ('quoted', 'creating', 'paying', 'uncertain', 'released'):
            conn.execute(sa.text("INSERT INTO freight_orders VALUES(:id,:state,CAST(:payload AS jsonb),20.15,:provider,:pdf)"),
                         {'id': uuid.uuid4(), 'state': state, 'payload': '{"snapshot":"unchanged"}',
                          'provider': 'fixture-' + state, 'pdf': b'%PDF-history'})
        before = list(conn.execute(sa.text('SELECT id,state,payload,price,provider_id,label_pdf FROM freight_orders ORDER BY id')))
        upgrade(conn, 'c9d0e1f2a3b4_freight_recovery.py')
        assert list(conn.execute(sa.text('SELECT id,state,payload,price,provider_id,label_pdf FROM freight_orders ORDER BY id'))) == before
        assert conn.execute(sa.text('SELECT count(*) FROM freight_orders WHERE recovery_attempts=0 AND recovery_kind IS NULL AND recovery_check_at IS NULL AND error_category IS NULL')).scalar() == 5
        assert any(index['name'] == 'ix_freight_orders_recovery_check_at' for index in sa.inspect(conn).get_indexes('freight_orders', schema=schema))


def test_second_worker_skips_active_recovery_and_notifies_only_once(pg, monkeypatch):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    models = (Usuario, Vendedor, Cliente, PdvCliente, SavedAddress, PrintDevice, PrintJob,
              FreightOrder, AssistantIdentity, AssistantMessage, AssistantDelivery)
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in models])
    factory = sessionmaker(bind=isolated, autoflush=False)
    user_id = uuid.uuid4()
    entered, release = Event(), Event()
    calls = []
    monkeypatch.setattr(recovery, 'SessionLocal', factory)
    monkeypatch.setattr(sf.settings, 'TELEGRAM_GROUP_ID', '-100123')
    def provider(method, path, body=None):
        calls.append((method, path)); assert path == 'calculator'
        entered.set(); assert release.wait(timeout=10)
        return copy.deepcopy(RATES)
    monkeypatch.setattr(sf, 'call', provider)
    try:
        with factory() as db:
            db.add(Usuario(id=user_id, nome='Fixture', email='fixture@example.test', senha_hash='unused', role=UsuarioRole.GERENTE))
            db.flush()
            db.add(AssistantIdentity(channel='telegram', external_id='123', user_id=user_id, can_register=True)); db.commit()
        key = order(factory, user_id, state='retry_waiting', kind='quote')
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(recovery.process_recovery)
            assert entered.wait(timeout=5)
            try:
                assert executor.submit(recovery.process_recovery).result(timeout=5) is False
            finally:
                release.set()
            assert first.result(timeout=5) is True
        with factory() as db:
            row = db.get(FreightOrder, key)
            assert row.state == 'quoted' and row.recovery_attempts == 1 and row.recovery_kind is None
            assert db.query(AssistantDelivery).count() == 1
        assert calls == [('POST', 'calculator')]
    finally:
        release.set()
        isolated.dispose()
