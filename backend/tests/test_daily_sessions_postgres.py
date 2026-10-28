"""Backfill validation on disposable PostgreSQL, without production credentials."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa

from test_access_postgres import pg


@pytest.mark.parametrize(('moment', 'expected'), [
    ('2026-10-27T23:59:59+00:00', '2026-10-28T00:00:00+00:00'),
    ('2026-10-28T00:00:00+00:00', '2026-10-29T00:00:00+00:00'),
    ('2026-10-28T03:10:00+00:00', '2026-10-29T00:00:00+00:00'),
])
def test_legacy_backfill_uses_activation_time_and_preserves_all_existing_session_fields(pg, monkeypatch, moment, expected):
    engine, schema = pg
    instant = datetime.fromisoformat(moment)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz or timezone.utc)

    path = Path(__file__).parents[1]/'alembic'/'versions'/'r0a1b2c3d4e5_daily_session_cutoff.py'
    spec = importlib.util.spec_from_file_location('daily_session_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration, 'datetime', Clock)
    rows = [
        {'id': uuid.uuid4(), 'created': instant-timedelta(days=5), 'expires': instant+timedelta(days=2), 'revoked': None},
        {'id': uuid.uuid4(), 'created': instant-timedelta(days=1), 'expires': instant-timedelta(hours=1), 'revoked': None},
        {'id': uuid.uuid4(), 'created': instant-timedelta(days=1), 'expires': instant+timedelta(days=2), 'revoked': instant-timedelta(hours=1)},
    ]
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE auth_sessions(id uuid PRIMARY KEY,created_at timestamptz NOT NULL,expires_at timestamptz NOT NULL,revoked_at timestamptz)')
        conn.execute(sa.text('INSERT INTO auth_sessions VALUES(:id,:created,:expires,:revoked)'), rows)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        result = conn.execute(sa.text('SELECT id,created_at,expires_at,revoked_at,daily_expires_at FROM auth_sessions')).all()
    original = {row['id']: row for row in rows}
    assert len(result) == 3
    for row in result:
        source = original[row.id]
        assert (row.created_at, row.expires_at, row.revoked_at) == (source['created'], source['expires'], source['revoked'])
        assert row.daily_expires_at == datetime.fromisoformat(expected)
