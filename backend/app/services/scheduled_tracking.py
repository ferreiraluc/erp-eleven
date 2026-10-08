"""Prevent duplicate daily tracking runs, including overlapping deployments."""
from sqlalchemy import text
from ..config import settings
from .. import database
from ..models.access import now
from ..models.operations import ScheduledRun
from .tracking_refresh import refresh_active


def run_daily(session_factory=None, refresh=refresh_active):
    session_factory = session_factory or database.SessionLocal
    key = 'tracking:' + settings.now().date().isoformat()
    with session_factory() as guard:
        # Dedicated transaction owns the advisory lock until the completion record
        # commits. It never holds locks on business rows while calling the provider.
        if guard.bind.dialect.name == 'postgresql':
            if not guard.execute(text('SELECT pg_try_advisory_xact_lock(711003)')).scalar():return None
        if guard.get(ScheduledRun,key):return None
        with session_factory() as db:
            result = refresh(db)
            db.commit()
        guard.add(ScheduledRun(key=key,completed_at=now()))
        guard.commit()
        return result
