"""Additive migration and device ownership tested in a disposable PostgreSQL schema."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.notification_push import NotificationPushSubscription
from test_access_postgres import pg, upgrade
from test_notification_push import TABLE_MODELS, user_session
from test_notification_native_push import configured, subscribe


def test_native_push_migration_preserves_web_rows_and_constrains_transport(pg):
    engine, schema = pg
    identity = uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE notification_push_subscriptions(id uuid PRIMARY KEY, endpoint text NOT NULL)')
        conn.execute(sa.text('INSERT INTO notification_push_subscriptions VALUES(:id,:endpoint)'), {'id':identity, 'endpoint':'https://fcm.googleapis.com/fixture'})
        upgrade(conn, 'd2m3n4o5p6q7_native_notification_transport.py')
        assert conn.execute(sa.text('SELECT id,endpoint,transport,installation_hash FROM notification_push_subscriptions')).one() == (identity,'https://fcm.googleapis.com/fixture','web',None)
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.execute(sa.text('UPDATE notification_push_subscriptions SET transport=:transport'), {'transport':'invalid'})


def test_concurrent_native_registration_creates_one_binding(pg, configured):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in TABLE_MODELS])
    factory = sessionmaker(bind=isolated, expire_on_commit=False)
    with factory() as db:
        user, session = user_session(db)
        user_id, session_id = user.id, session.id
    barrier = Barrier(2)
    def register(_):
        from app.models.usuario import Usuario
        from app.models.access import AuthSession
        with factory() as db:
            user, session = db.get(Usuario, user_id), db.get(AuthSession, session_id)
            barrier.wait(timeout=10)
            row = subscribe(db, user, session)
            db.commit()
            return row.id
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(register, range(2)))
        assert results[0] == results[1]
        with factory() as db:
            assert db.query(NotificationPushSubscription).count() == 1
    finally:
        isolated.dispose()
