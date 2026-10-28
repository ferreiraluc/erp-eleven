import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import jwt
import bcrypt
from ..config import settings
from ..models.access import AuthSession, now


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def next_daily_session_expiry(moment):
    """Next 21:00 in Brasília, including logins made after the closing hour."""
    local = aware(moment).astimezone(ZoneInfo('America/Sao_Paulo'))
    cutoff = local.replace(hour=21, minute=0, second=0, microsecond=0)
    if local >= cutoff:
        cutoff += timedelta(days=1)
    return cutoff.astimezone(timezone.utc)


def effective_session_expiry(session):
    """One deadline for API access and session-bound background deliveries."""
    daily = session.daily_expires_at
    if daily is None:
        # Older API instances may briefly create sessions after the migration.
        daily = next_daily_session_expiry(session.created_at)
    return min(aware(session.expires_at), aware(daily))


def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def get_password_hash(password):
    if not 6 <= len(password) or not password.strip() or len(password.encode('utf-8')) > 72:
        raise ValueError('Use no mínimo 6 caracteres e no máximo 72 bytes.')
    if len(set(password)) < 4 or password.lower() in ('123456789012','abcdefghijkl','password1234'):
        raise ValueError('Escolha uma senha menos previsível, de preferência uma frase.')
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def issue_session(db, user):
    issued_at = now()
    expires = next_daily_session_expiry(issued_at)
    session = AuthSession(id=uuid.uuid4(), user_id=user.id, created_at=issued_at,
                          expires_at=expires, daily_expires_at=expires)
    db.add(session)
    token = jwt.encode({'sub': str(user.id), 'sid': str(session.id), 'ver': user.auth_version,
                        'exp': expires, 'iat': issued_at}, settings.SECRET_KEY, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'expires_in': int((expires-issued_at).total_seconds())}


def revoke_all(db, user):
    user.auth_version = (user.auth_version or 0) + 1
    db.query(AuthSession).filter_by(user_id=user.id, revoked_at=None).update({'revoked_at': now()})
