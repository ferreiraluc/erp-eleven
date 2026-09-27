"""Daily OneDrive import schedule, independent of the server's local timezone."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SYNC_TIMEZONE = ZoneInfo('America/Sao_Paulo')


def next_daily_sync(now: datetime) -> datetime:
    """Return the next 18:00 in Brasilia as a UTC instant, strictly after now."""
    local = now.astimezone(SYNC_TIMEZONE)
    scheduled = local.replace(hour=18, minute=0, second=0, microsecond=0)
    if scheduled <= local:
        scheduled += timedelta(days=1)
    return scheduled.astimezone(timezone.utc)
