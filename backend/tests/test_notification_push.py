"""Local inbox/device fixtures only: no provider request or real notification."""
import base64
from datetime import timedelta
import json
from types import SimpleNamespace
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
import pytest
import requests
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Usuario, Vendedor
from app.models.access import AuthSession, now
from app.models.notification import Notification, NotificationPreference, NotificationRecipient
from app.models.notification_push import NotificationPushDelivery, NotificationPushSetting, NotificationPushSubscription
from app.services import notification_push as push

TABLE_MODELS = (Usuario, Vendedor, AuthSession, Notification, NotificationRecipient,
                NotificationPreference, NotificationPushSetting, NotificationPushSubscription, NotificationPushDelivery)


@pytest.fixture
def db():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[model.__table__ for model in TABLE_MODELS])
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def keys():
    private = ec.generate_private_key(ec.SECP256R1())
    return {
        "p256dh": encode(private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)),
        "auth": encode(b"local-test-only!"),
    }


def user_session(db, name="Sol"):
    user = Usuario(id=uuid.uuid4(), nome=name, email=f"{uuid.uuid4().hex}@fixture.local", senha_hash="unused", auth_version=0, ativo=True)
    db.add(user)
    db.flush()
    session = AuthSession(id=uuid.uuid4(), user_id=user.id, expires_at=now() + timedelta(days=1))
    db.add(session)
    db.commit()
    return user, session


def subscription(db, user, session, endpoint="https://fcm.googleapis.com/fcm/send/local-only"):
    return push.subscribe(db, user, session.id, endpoint=endpoint, **keys(), device_token="local_device_binding_token_0123456789")


def queued(db):
    user, session = user_session(db)
    sub = subscription(db, user, session)
    notice = Notification(id=uuid.uuid4(), title="Dados privados", body="Cliente e venda privados", category="sales", severity="warning", published_at=now(), version=1)
    db.add(notice)
    db.flush()
    recipient = NotificationRecipient(id=uuid.uuid4(), notification_id=notice.id, user_id=user.id)
    db.add(recipient)
    db.flush()
    delivery = NotificationPushDelivery(notification_id=notice.id, recipient_id=recipient.id, subscription_id=sub.id)
    db.add(delivery)
    db.commit()
    return user, session, sub, notice, recipient, delivery


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/path", "https://localhost/push", "https://127.0.0.1/push",
    "https://169.254.169.254/latest", "https://fcm.googleapis.com.evil.test/push",
    "https://fcm.googleapis.com@evil.test/push", "https://user@fcm.googleapis.com/push",
    "https://fcm.googleapis.com:8443/push", "https://fcm.googleapis.com/push#secret",
    "https://notify.windows.com.evil.test/push", "https://push.apple.com.evil.test/push",
    "https://fcm.googleapis.com/push\nsecret", "https://fcm.googleapis.com/", "not-a-url",
])
def test_endpoint_rejects_arbitrary_origins_and_unsafe_urls(endpoint):
    assert not push.valid_endpoint(endpoint)


@pytest.mark.parametrize("endpoint", [
    "https://fcm.googleapis.com/fcm/send/local", "https://updates.push.services.mozilla.com/wpush/v2/local",
    "https://web.push.apple.com/local", "https://europe.notify.windows.com/local",
    "https://wns2-local.notify.windows.com/?token=local-fixture",
])
def test_expected_provider_origins_are_supported(endpoint):
    assert push.valid_endpoint(endpoint)


def test_vapid_persisted_and_private_key_encrypted(db):
    first = push.vapid_keys(db)
    db.commit()
    assert push.vapid_keys(db) == first
    row = db.get(NotificationPushSetting, "vapid-v1")
    assert first[1] not in json.dumps(row.value)
    assert row.value["private_key_encrypted"].startswith("gAAAA")
    private = serialization.load_der_private_key(base64.urlsafe_b64decode(first[1]), password=None)
    assert encode(private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)) == first[0]


def test_invalid_crypto_key_and_device_binding_rejected(db):
    user, session = user_session(db)
    with pytest.raises(HTTPException) as error:
        push.subscribe(db, user, session.id, endpoint="https://fcm.googleapis.com/test", p256dh="abcd", auth="abcd", device_token="short")
    assert error.value.status_code == 422
    assert db.query(NotificationPushSubscription).count() == 0


def test_endpoint_never_changes_ownership_even_after_unsubscribe(db):
    user, session = user_session(db)
    sub = subscription(db, user, session)
    db.commit()
    stranger, other_session = user_session(db, "Lucas")
    assert push.unsubscribe(db, stranger.id, other_session.id, endpoint=sub.endpoint) == 0
    assert sub.active
    assert push.unsubscribe(db, user.id, session.id, endpoint=sub.endpoint) == 1
    db.commit()
    with pytest.raises(HTTPException) as error:
        subscription(db, stranger, other_session)
    assert error.value.status_code == 409
    assert db.get(NotificationPushSubscription, sub.id).user_id == user.id


def test_new_login_same_user_rebinds_and_rotates_device_token(db):
    user, old_session = user_session(db)
    sub = subscription(db, user, old_session)
    old_encrypted = sub.device_token_encrypted
    next_session = AuthSession(id=uuid.uuid4(), user_id=user.id, expires_at=now() + timedelta(days=1))
    db.add(next_session)
    db.commit()
    again = push.subscribe(db, user, next_session.id, endpoint=sub.endpoint, **keys(), device_token="new_local_device_binding_0123456789")
    assert again.id == sub.id
    assert again.auth_session_id == next_session.id
    assert again.device_token_encrypted != old_encrypted
    assert db.query(NotificationPushDelivery).count() == 0  # No historical replay.


@pytest.mark.parametrize("change", ["revoked", "expired", "version", "inactive", "read", "cancelled", "preferences", "category", "old"])
def test_worker_rechecks_identity_preferences_and_expiry_before_send(db, change):
    user, session, sub, notice, recipient, delivery = queued(db)
    if change == "revoked": session.revoked_at = now()
    if change == "expired": session.expires_at = now() - timedelta(seconds=1)
    if change == "version": user.auth_version += 1
    if change == "inactive": user.ativo = False
    if change == "read": recipient.read_at = now()
    if change == "cancelled": notice.cancelled_at = now()
    if change in ("preferences", "category"):
        db.add(NotificationPreference(user_id=user.id, push_enabled=change != "preferences", categories=["manual"]))
    if change == "old": delivery.created_at = now() - timedelta(days=2)
    db.commit()
    assert push.claim_delivery(db) is None
    assert delivery.status == "dead"


def test_push_payload_is_generic_and_device_bound_and_network_has_no_transaction(db, monkeypatch):
    user, session, sub, notice, recipient, delivery = queued(db)
    claim = push.claim_delivery(db)
    assert claim and delivery.status == "sending"
    db.commit()
    assert not db.in_transaction()
    payload = json.loads(claim.payload)
    assert notice.title not in claim.payload and notice.body not in claim.payload
    assert payload["user_id"] == str(user.id)
    assert payload["device_token"] == "local_device_binding_token_0123456789"
    assert payload["notification_id"] == str(notice.id)
    assert payload["action_path"] == "/notificacoes"
    calls = []
    def fake(**kwargs):
        calls.append(kwargs)
        assert not db.in_transaction()
        return SimpleNamespace(status_code=201)
    monkeypatch.setattr("pywebpush.webpush", fake)
    assert push.send_claim(claim) == ("delivered", None, None)
    assert calls[0]["timeout"] == (2, 3)
    assert calls[0]["headers"]["Topic"] == str(claim.id).replace("-", "")
    push.finish_delivery(db, claim, ("delivered", None, None))
    assert delivery.status == "delivered"


def test_provider_session_refuses_redirects_and_ignores_environment_proxy(monkeypatch):
    captured = []
    monkeypatch.setattr(requests.Session, "post", lambda self, url, *args, **kwargs: captured.append(kwargs))
    with push._ProviderSession() as session:
        assert session.trust_env is False
        session.post("https://fcm.googleapis.com/local", allow_redirects=True)
        with pytest.raises(ValueError):
            session.post("https://localhost/local")
    assert captured == [{"allow_redirects": False}]


def test_real_library_encrypts_and_signs_without_any_network(db, monkeypatch):
    queued(db)
    claim = push.claim_delivery(db)
    db.commit()
    captured = []
    def offline(self, url, *args, **kwargs):
        captured.append(kwargs)
        response = requests.Response()
        response.status_code = 201
        return response
    monkeypatch.setattr(push._ProviderSession, "post", offline)
    assert push.send_claim(claim) == ("delivered", None, None)
    assert captured[0]["headers"]["content-encoding"] == "aes128gcm"
    assert captured[0]["headers"]["Authorization"].startswith("vapid ")
    assert b"notification_id" not in captured[0]["data"]


@pytest.mark.parametrize("code,expected", [(404, "gone"), (410, "gone"), (429, "retry"), (503, "retry"), (403, "dead"), (302, "dead")])
def test_provider_errors_are_bounded_and_not_leaked(db, monkeypatch, code, expected):
    from pywebpush import WebPushException
    queued(db)
    claim = push.claim_delivery(db)
    db.commit()
    def fail(**kwargs):
        response = requests.Response()
        response.status_code = code
        response.headers["Retry-After"] = "120"
        raise WebPushException("capability_secret_do_not_log", response=response)
    monkeypatch.setattr("pywebpush.webpush", fail)
    outcome = push.send_claim(claim)
    assert outcome[0] == expected
    assert "capability_secret" not in str(outcome)
    assert outcome[2] == (120 if expected == "retry" else None)
    push.finish_delivery(db, claim, outcome)
    db.commit()
    if expected == "gone":
        assert not db.query(NotificationPushSubscription).one().active


def test_crash_lease_retry_and_stale_worker_cannot_complete_new_claim(db):
    queued(db)
    moment = now()
    original = push.claim_delivery(db, moment)
    db.commit()
    assert push.claim_delivery(db, moment + timedelta(seconds=1)) is None
    replacement = push.claim_delivery(db, moment + timedelta(seconds=91))
    db.commit()
    assert replacement.id == original.id and replacement.token != original.token
    assert not push.finish_delivery(db, original, ("delivered", None, None))
    assert push.finish_delivery(db, replacement, ("retry", "provider_network_error", 120), moment)
    row = db.get(NotificationPushDelivery, original.id)
    assert row.status == "retry" and row.next_attempt_at == moment + timedelta(seconds=120)


def test_retry_budget_is_finite(db):
    *_, delivery = queued(db)
    delivery.attempts = push.MAX_ATTEMPTS - 1
    db.commit()
    claim = push.claim_delivery(db)
    push.finish_delivery(db, claim, ("retry", "provider_network_error", None))
    assert delivery.status == "dead"


def test_one_corrupt_device_binding_is_disabled_without_retry_storm(db):
    _, _, sub, _, _, delivery = queued(db)
    sub.device_token_encrypted = "corrupted-fixture"
    db.commit()
    assert push.claim_delivery(db) is None
    assert not sub.active and delivery.status == "dead"
    assert delivery.last_error == "device_binding_unavailable"


def test_logout_hook_disables_only_its_session_devices(db):
    user, session = user_session(db)
    first = subscription(db, user, session)
    other = AuthSession(id=uuid.uuid4(), user_id=user.id, expires_at=now() + timedelta(days=1))
    db.add(other)
    db.flush()
    second = subscription(db, user, other, "https://web.push.apple.com/other-device")
    db.commit()
    assert push.revoke_session_subscriptions(db, session.id) == 1
    db.expire_all()
    assert not db.get(NotificationPushSubscription, first.id).active
    assert db.get(NotificationPushSubscription, second.id).active
