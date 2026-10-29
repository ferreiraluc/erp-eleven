"""Wonca migration, atomic inbox and synchronization are validated on isolated PG."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg, upgrade
from test_wonca_monitoring import MOMENT, ENDPOINT, PROFILE, SIGNING, CODE, signed, subscribe, Provider
from test_customer_links import parcel
from app.database import Base
from app.config import settings
from app.models import Rastreamento
from app.models.wonca import WoncaConfig, WoncaEvent, WoncaSubscription
from app.services import wonca_monitoring as monitor


def test_migration_is_opt_in_preserves_old_history_and_creates_indexes(pg):
    engine,schema=pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql("CREATE TABLE rastreamentos(id integer PRIMARY KEY, historico_eventos jsonb)")
        conn.exec_driver_sql("INSERT INTO rastreamentos VALUES(1, '[{\"situacao\":\"Histórico original\"}]')")
        upgrade(conn,'t2c3d4e5f6a7_wonca_monitoring.py')
        assert conn.execute(sa.text('SELECT historico_eventos,provedor_verificado_em FROM rastreamentos')).one()==([{'situacao':'Histórico original'}],None)
        assert conn.execute(sa.text('SELECT count(*) FROM wonca_config')).scalar()==0
        assert conn.execute(sa.text('SELECT count(*) FROM wonca_subscriptions')).scalar()==0
        assert {i['name'] for i in sa.inspect(conn).get_indexes('wonca_events',schema=schema)}=={'ix_wonca_events_code','ix_wonca_events_status'}
        assert {c['name'] for c in sa.inspect(conn).get_columns('wonca_config',schema=schema)} >= {'secret_encrypted','daytime_only'}


def isolated_factory(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated)
    return isolated,sessionmaker(bind=isolated,autoflush=False)


def test_concurrent_receipts_have_one_durable_event_and_failed_transaction_replays(pg,monkeypatch):
    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    isolated,factory=isolated_factory(pg)
    try:
        with factory() as db:
            db.add(WoncaConfig(id='main',endpoint_id=ENDPOINT,profile_id=PROFILE,enabled=True,
                secret_encrypted=monitor.cipher().encrypt(SIGNING.encode()).decode()))
            row=parcel(db,CODE); rid=row.id; subscribe(db); db.commit()
        barrier=Barrier(2); body,headers=signed()
        def receive(_):
            with factory() as db:
                barrier.wait(timeout=5)
                result=monitor.receive(db,body,headers,MOMENT); db.commit(); return result
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert all(r['accepted'] for r in executor.map(receive,range(2)))
        with factory() as db:
            assert db.query(WoncaEvent).count()==1
            assert monitor.process_safely(db); db.rollback()
            assert db.query(WoncaEvent).one().status=='pending'
            assert not db.get(Rastreamento,rid).historico_eventos
            assert monitor.process_safely(db); db.commit()
            assert db.query(WoncaEvent).one().status=='processed'
            assert db.get(Rastreamento,rid).historico_eventos
    finally: isolated.dispose()


def test_only_one_subscription_reconciler_can_contact_provider(pg,monkeypatch):
    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    monkeypatch.setattr(settings,'WONCA_API_KEY','synthetic')
    isolated,factory=isolated_factory(pg); provider=Provider()
    try:
        with factory() as db:
            db.add(WoncaConfig(id='main',endpoint_id=ENDPOINT,profile_id=PROFILE,enabled=True,
                secret_encrypted=monitor.cipher().encrypt(SIGNING.encode()).decode()))
            parcel(db,CODE); db.commit()
        with factory() as first, factory() as second:
            assert monitor.lock(first,711014)
            assert monitor.sync_subscriptions(second,provider,MOMENT)=={'added':0,'removed':0}
            assert not provider.calls
            second.rollback(); first.rollback()
            assert monitor.sync_subscriptions(second,provider,MOMENT)['added']==1; second.commit()
            assert len(provider.calls)==1
    finally: isolated.dispose()
