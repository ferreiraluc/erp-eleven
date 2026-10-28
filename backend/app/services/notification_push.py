"""Web Push subscriptions and encrypted application identity.

Provider URLs are capability secrets. Never include endpoints, keys, provider
responses or exception text in logs/audit responses. The queue reports only a
bounded error category. Network requests happen outside database transactions.
"""
import base64
from dataclasses import dataclass
from datetime import timedelta
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import secrets
from urllib.parse import urlsplit
import uuid

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
import requests
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from ..config import settings
from ..models.access import AuthSession, now
from ..models.notification_push import NotificationPushDelivery, NotificationPushSetting, NotificationPushSubscription
from ..models.usuario import Usuario
from .user_sessions import aware, effective_session_expiry

VAPID_SETTING = "vapid-v1"
MAX_ATTEMPTS = 8
MAX_DEVICE_SUBSCRIPTIONS = 12
LEASE_SECONDS = 90
MAX_DELIVERY_AGE = timedelta(days=1)
_SAFE_B64 = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


def _cipher():
    key = hashlib.sha256(("eleven:notifications:push:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt(value):
    return _cipher().encrypt(value.encode()).decode()


def _decrypt(value):
    try:
        return _cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        raise ValueError("notification_key_unavailable") from None


def vapid_keys(db: Session):
    """Generate once under the same transaction, including overlapping deploys."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 865422627182})
    row = db.get(NotificationPushSetting, VAPID_SETTING)
    if row is None:
        private = ec.generate_private_key(ec.SECP256R1())
        raw = private.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        public = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        row = NotificationPushSetting(key=VAPID_SETTING, value={
            "public_key": base64.urlsafe_b64encode(public).rstrip(b"=").decode(),
            "private_key_encrypted": _encrypt(base64.urlsafe_b64encode(raw).decode()),
        })
        db.add(row)
        db.flush()
    return row.value["public_key"], _decrypt(row.value["private_key_encrypted"])


def endpoint_hash(endpoint):
    return hashlib.sha256(endpoint.encode()).hexdigest()


def valid_endpoint(endpoint):
    """Only known Web Push provider origins, HTTPS 443, no URL credentials."""
    try:
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or "").lower()
        allowed = host in {"fcm.googleapis.com", "updates.push.services.mozilla.com"}
        allowed = allowed or host.endswith(".push.apple.com") or host.endswith(".notify.windows.com")
        return bool(allowed and parsed.scheme == "https" and parsed.port in (None, 443)
                    and not parsed.username and not parsed.password and not parsed.fragment
                    and (parsed.path not in ("", "/") or parsed.query) and len(endpoint) <= 4096
                    and not any(ord(c) < 33 or ord(c) == 127 for c in endpoint))
    except (TypeError, ValueError):
        return False


def _decode_key(value, size):
    if not _SAFE_B64.fullmatch(value):
        raise ValueError("invalid key")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(decoded) != size:
        raise ValueError("invalid key")
    return decoded


def validate_subscription(endpoint, p256dh, auth, device_token):
    if not valid_endpoint(endpoint):
        raise HTTPException(422, "O provedor de notificações deste navegador não é compatível.")
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _decode_key(p256dh, 65))
        _decode_key(auth, 16)
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", device_token):
            raise ValueError("invalid binding")
    except (ValueError, TypeError):
        raise HTTPException(422, "A inscrição de notificações é inválida. Ative novamente neste aparelho.") from None


def subscribe(db, user, session_id, *, endpoint, p256dh, auth, device_token, device_name="Navegador"):
    validate_subscription(endpoint, p256dh, auth, device_token)
    # Serialize per user as well as per endpoint: quota and ownership checks
    # remain effective when multiple tabs register simultaneously.
    if db.get_bind().dialect.name == "postgresql":
        lock_key = int(endpoint_hash(endpoint)[:15], 16)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    db.query(Usuario).filter(Usuario.id == user.id).with_for_update().one()
    session = db.get(AuthSession, session_id)
    if not session or session.user_id != user.id or session.revoked_at or effective_session_expiry(session) <= now():
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    row = db.query(NotificationPushSubscription).filter_by(endpoint_hash=endpoint_hash(endpoint)).with_for_update().one_or_none()
    if row and row.user_id != user.id:
        raise HTTPException(409, "Este aparelho ainda está vinculado a outra conta. Desative as notificações e ative novamente.")
    if row is None or not row.active:
        count = db.query(NotificationPushSubscription).filter_by(user_id=user.id, active=True).count()
        if count >= MAX_DEVICE_SUBSCRIPTIONS:
            raise HTTPException(409, "Limite de aparelhos atingido. Desative as notificações em um aparelho antigo.")
    if row is None:
        row = NotificationPushSubscription(user_id=user.id, endpoint_hash=endpoint_hash(endpoint), endpoint=endpoint)
        db.add(row)
    # A new session invalidates all queued payloads for the old binding; the SW
    # independently refuses stale tokens after logout or account switching.
    row.auth_session_id, row.auth_version = session_id, user.auth_version
    row.p256dh, row.auth = p256dh, auth
    row.device_token_hash = endpoint_hash(device_token)
    row.device_token_encrypted = _encrypt(device_token)
    row.device_name = (device_name or "Navegador").strip()[:100]
    row.active, row.updated_at = True, now()
    db.flush()
    return row


def unsubscribe(db, user_id, session_id, *, endpoint=None, device_token=None):
    query = db.query(NotificationPushSubscription).filter_by(user_id=user_id, auth_session_id=session_id, active=True)
    if endpoint:
        query = query.filter_by(endpoint_hash=endpoint_hash(endpoint))
    if device_token:
        query = query.filter_by(device_token_hash=endpoint_hash(device_token))
    return query.update({"active": False, "updated_at": now()}, synchronize_session=False)


def revoke_session_subscriptions(db, session_id):
    """Call in the logout/revocation transaction; delivery also checks sessions."""
    return db.query(NotificationPushSubscription).filter_by(auth_session_id=session_id, active=True).update(
        {"active": False, "updated_at": now()}, synchronize_session=False)


def _eligible(db, delivery, moment):
    from ..models.notification import Notification, NotificationRecipient
    sub = db.get(NotificationPushSubscription, delivery.subscription_id)
    recipient = db.get(NotificationRecipient, delivery.recipient_id)
    notice = db.get(Notification, delivery.notification_id)
    if not sub or not sub.active or not recipient or not notice:
        return None
    user, session = db.get(Usuario, sub.user_id), db.get(AuthSession, sub.auth_session_id)
    if (not user or not user.ativo or user.auth_version != sub.auth_version or not session
            or session.revoked_at or session.user_id != user.id or effective_session_expiry(session) <= moment):
        sub.active = False
        return None
    from .notification_context import notification_allowed
    if not notification_allowed(db, user, notice):
        return None
    if (recipient.user_id != user.id or recipient.notification_id != notice.id
            or recipient.read_at or recipient.removed_at or notice.cancelled_at or not notice.published_at
            or aware(delivery.created_at) + MAX_DELIVERY_AGE <= moment):
        return None
    return sub, user, notice, session


@dataclass(frozen=True)
class PushClaim:
    id: uuid.UUID
    token: str
    endpoint: str
    p256dh: str
    auth: str
    private_key: str
    payload: str
    attempts: int
    expires_at: int


def claim_delivery(db, moment=None):
    """Claim one job; caller commits before sending. PostgreSQL skips locked jobs."""
    moment = moment or now()
    query = db.query(NotificationPushDelivery).filter(or_(
        and_(NotificationPushDelivery.status.in_(("queued", "retry")), NotificationPushDelivery.next_attempt_at <= moment),
        and_(NotificationPushDelivery.status == "sending", NotificationPushDelivery.lease_until <= moment),
    )).order_by(NotificationPushDelivery.next_attempt_at, NotificationPushDelivery.id).with_for_update(skip_locked=True)
    delivery = query.first()
    if not delivery:
        return None
    eligible = _eligible(db, delivery, moment)
    if delivery.attempts >= MAX_ATTEMPTS or not eligible:
        delivery.status, delivery.last_error = "dead", "expired_or_disabled"
        delivery.lease_until, delivery.lease_token = None, None
        return None
    sub, user, notice, session = eligible
    _, private = vapid_keys(db)
    try:
        device_token = _decrypt(sub.device_token_encrypted)
    except ValueError:
        sub.active = False
        delivery.status, delivery.last_error = "dead", "device_binding_unavailable"
        delivery.lease_until, delivery.lease_token = None, None
        return None
    token = str(uuid.uuid4())
    delivery.status, delivery.lease_token = "sending", token
    delivery.lease_until = moment + timedelta(seconds=LEASE_SECONDS)
    delivery.attempts += 1
    from .notification_context import presented_fields
    from .notifications import action_allowed
    from ..schemas.notification import validate_action_path
    presented = presented_fields(db, [notice])[notice.id]
    path = notice.action_path
    try:
        path = validate_action_path(path)
        if not path or len(path.encode('utf-8')) > 500 or not action_allowed(db, user, path):
            path = '/notificacoes'
    except ValueError:
        path = '/notificacoes'
    # Leave room for encryption overhead under push providers' payload limits,
    # including multibyte names and emoji. The inbox retains the complete text.
    def bounded(value, length, byte_limit):
        value = re.sub(r'[\x00-\x1f\x7f]', ' ', str(value or '')).strip()[:length]
        return value.encode('utf-8')[:byte_limit].decode('utf-8', errors='ignore')
    expires_at = int(effective_session_expiry(session).timestamp() * 1000)
    content = {
        "notification_id": str(notice.id), "version": notice.version,
        "device_token": device_token, "user_id": str(user.id),
        "title": bounded(presented['title'], 120, 300) or 'ELEVEN',
        "body": bounded(presented['body'], 1000, 1600) or 'Você tem uma nova notificação no sistema.',
        "action_path": path, "severity": notice.severity, "sound": True, "expires_at": expires_at,
    }
    payload = json.dumps(content, ensure_ascii=False)
    # JSON escaping can expand otherwise short quotes/control characters.
    # Keep a hard byte cap regardless of the author's alphabet or formatting.
    while len(payload.encode('utf-8')) > 3072 and len(content['body']) > 128:
        content['body'] = content['body'][:-128]
        payload = json.dumps(content, ensure_ascii=False)
    return PushClaim(delivery.id, token, sub.endpoint, sub.p256dh, sub.auth, private, payload, delivery.attempts, expires_at)


class _ProviderSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def post(self, url, *args, **kwargs):
        if not valid_endpoint(url):
            raise ValueError("unsupported_push_provider")
        kwargs["allow_redirects"] = False
        return super().post(url, *args, **kwargs)


def _retry_seconds(value, moment):
    try:
        if str(value).strip().isdigit():
            return min(3600, max(1, int(value)))
        return min(3600, max(1, int((parsedate_to_datetime(str(value)) - moment).total_seconds())))
    except (TypeError, ValueError, OverflowError):
        return None


def send_claim(claim):
    """Return normalized provider outcome. Never log capability URLs or bodies."""
    from pywebpush import WebPushException, webpush
    remaining = (claim.expires_at - int(now().timestamp() * 1000)) // 1000
    if remaining <= 0:
        return "dead", "session_expired", None
    try:
        with _ProviderSession() as session:
            response = webpush(
                subscription_info={"endpoint": claim.endpoint, "keys": {"p256dh": claim.p256dh, "auth": claim.auth}},
                data=claim.payload, vapid_private_key=claim.private_key,
                vapid_claims={"sub": "mailto:contato@elevenparispy.com"},
                ttl=min(86400, remaining), timeout=(2, 3), requests_session=session,
                headers={"Topic": str(claim.id).replace("-", ""), "Urgency": "normal"},
            )
        return "delivered", None, None
    except WebPushException as error:
        response = error.response
        status = response.status_code if response is not None else None
        if status in (404, 410):
            return "gone", "subscription_expired", None
        if status == 429 or status is not None and status >= 500:
            retry = _retry_seconds(response.headers.get("Retry-After"), now())
            return "retry", "provider_rate_limited" if status == 429 else "provider_unavailable", retry
        return "dead", "provider_rejected", None
    except requests.RequestException:
        return "retry", "provider_network_error", None
    except (ValueError, TypeError):
        return "dead", "invalid_subscription", None


def finish_delivery(db, claim, outcome, moment=None):
    moment = moment or now()
    row = db.query(NotificationPushDelivery).filter_by(id=claim.id, status="sending", lease_token=claim.token).with_for_update().one_or_none()
    if not row:
        return False
    status, error, retry = outcome
    if status == "gone":
        db.query(NotificationPushSubscription).filter_by(id=row.subscription_id).update({"active": False}, synchronize_session=False)
        status = "dead"
    if status == "retry":
        if row.attempts >= MAX_ATTEMPTS:
            status = "dead"
        else:
            backoff = retry or min(3600, 15 * 2 ** min(row.attempts, 8)) + secrets.randbelow(10)
            row.next_attempt_at = moment + timedelta(seconds=backoff)
    if status == "delivered":
        row.delivered_at = moment
        db.query(NotificationPushSubscription).filter_by(id=row.subscription_id).update({"last_success_at": moment}, synchronize_session=False)
    row.status, row.last_error = status, error
    row.lease_until, row.lease_token = None, None
    return True
