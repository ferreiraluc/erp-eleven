"""Explicit display/storage contracts; never rewrite historical timestamps.

PostgreSQL's legacy timestamp-without-time-zone columns contain UTC, as do the
aware event/session columns. SQLite test fixtures drop the offset from the
settings.now() default, and therefore retain Brasília wall-clock values.
Provider events and date-only business fields have separate local semantics.
"""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = 'America/Sao_Paulo'
BUSINESS_TZ = ZoneInfo(BUSINESS_TIMEZONE)


def stored_instant(value, db=None):
    if value is None or value.tzinfo is not None:
        return value
    dialect = db.get_bind().dialect.name if db is not None else 'postgresql'
    return value.replace(tzinfo=BUSINESS_TZ if dialect == 'sqlite' else timezone.utc)


def business_datetime(value, *, naive='utc'):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=BUSINESS_TZ if naive == 'business' else timezone.utc)
    return value.astimezone(BUSINESS_TZ)


def stored_day_start(day, db):
    local = datetime.combine(day, time.min, BUSINESS_TZ)
    if db.get_bind().dialect.name == 'postgresql':
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    return local.replace(tzinfo=None)
