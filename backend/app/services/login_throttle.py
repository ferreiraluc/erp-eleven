"""Shared fixed windows. Quota is committed before password verification."""
from datetime import timedelta
import hashlib
import hmac
from fastapi import HTTPException
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from ..config import settings
from ..models.access import now
from ..models.operations import LoginThrottle
from .user_sessions import aware

WINDOW_SECONDS = 600


def buckets(email, address):
    email = email.strip().lower()
    return sorted((hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest(), limit)
                  for value, limit in [(f'pair\0{email}\0{address}',12), (f'account\0{email}',30), (f'ip\0{address}',60)])


def login_limit(db, email, address, *, at=None):
    at = at or now()
    expired = at - timedelta(seconds=WINDOW_SECONDS)
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    retry = 0
    # Keep only short-lived opaque counters. Nothing identifies a person in clear.
    db.execute(delete(LoginThrottle).where(LoginThrottle.started_at < at-timedelta(days=1)))
    for key, limit in buckets(email, address):
        old = LoginThrottle.started_at <= expired
        statement = insert(LoginThrottle).values(bucket=key,started_at=at,attempts=1)
        statement = statement.on_conflict_do_update(index_elements=['bucket'],set_={
            'started_at':case((old,at),else_=LoginThrottle.started_at),
            'attempts':case((old,1),(LoginThrottle.attempts<=limit,LoginThrottle.attempts+1),else_=LoginThrottle.attempts),
        }).returning(LoginThrottle.attempts,LoginThrottle.started_at)
        count,started = db.execute(statement).one()
        if count > limit:retry=max(retry,int(WINDOW_SECONDS-(at-aware(started)).total_seconds())+1)
    db.commit()
    if retry:
        raise HTTPException(429,'Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.',
                            headers={'Retry-After':str(min(WINDOW_SECONDS,max(1,retry)))})
