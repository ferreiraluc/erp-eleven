import uuid
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from ..config import settings
from ..models.access import AuthSession, now


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def get_password_hash(password):
    if not 12 <= len(password) or not password.strip() or len(password.encode('utf-8')) > 72:
        raise ValueError('Use no mínimo 12 caracteres e no máximo 72 bytes.')
    if len(set(password)) < 4 or password.lower() in ('123456789012','abcdefghijkl','password1234'):
        raise ValueError('Escolha uma senha menos previsível, de preferência uma frase.')
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def issue_session(db, user):
    expires = (datetime.now(settings.tz).replace(hour=0, minute=0, second=0, microsecond=0)
               + timedelta(days=7)).astimezone(timezone.utc)
    session = AuthSession(id=uuid.uuid4(), user_id=user.id, expires_at=expires)
    db.add(session)
    token = jwt.encode({'sub': str(user.id), 'sid': str(session.id), 'ver': user.auth_version,
                        'exp': expires, 'iat': now()}, settings.SECRET_KEY, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'expires_in': int((expires-now()).total_seconds())}


def revoke_all(db, user):
    user.auth_version = (user.auth_version or 0) + 1
    db.query(AuthSession).filter_by(user_id=user.id, revoked_at=None).update({'revoked_at': now()})
