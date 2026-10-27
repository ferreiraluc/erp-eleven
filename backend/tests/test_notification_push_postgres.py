"""Actual PostgreSQL lease/key/device serialization in a disposable schema."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.notification_push import NotificationPushDelivery, NotificationPushSetting, NotificationPushSubscription
from app.services import notification_push as push
from test_access_postgres import pg
from test_notification_push import TABLE_MODELS, keys, queued, subscription, user_session


@pytest.fixture
def factory(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in TABLE_MODELS])
    try:
        yield sessionmaker(bind=isolated, expire_on_commit=False)
    finally:
        isolated.dispose()


def test_overlapping_deploys_generate_one_vapid_identity(factory):
    ready = Barrier(2)
    def generate(_):
        with factory() as db:
            ready.wait(timeout=10)
            public, private = push.vapid_keys(db)
            db.commit()
            return public, private
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(generate, range(2)))
    assert results[0] == results[1]
    with factory() as db:
        assert db.query(NotificationPushSetting).count() == 1


def test_two_workers_cannot_claim_same_delivery(factory):
    with factory() as db:
        queued(db)
    ready = Barrier(2)
    def claim(_):
        with factory() as db:
            ready.wait(timeout=10)
            result = push.claim_delivery(db)
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, range(2)))
    assert sum(result is not None for result in results) == 1
    with factory() as db:
        delivery = db.query(NotificationPushDelivery).one()
        assert delivery.attempts == 1 and delivery.status == "sending"


def test_concurrent_tabs_register_same_endpoint_without_duplicate_or_transfer(factory):
    with factory() as db:
        user, session = user_session(db)
        user_id, session_id = user.id, session.id
    ready = Barrier(2)
    def register(_):
        from app.models.usuario import Usuario
        with factory() as db:
            user = db.get(Usuario, user_id)
            ready.wait(timeout=10)
            result = push.subscribe(db, user, session_id, endpoint="https://fcm.googleapis.com/local-concurrent", **keys(),
                                    device_token="concurrent_local_device_token_0123456789")
            db.commit()
            return result.id
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(register, range(2)))
    assert ids[0] == ids[1]
    with factory() as db:
        assert db.query(NotificationPushSubscription).count() == 1
