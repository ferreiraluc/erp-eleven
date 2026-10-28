"""Daily session deadline; preserve the current shift for legacy logins."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa

revision = 'r0a1b2c3d4e5'
down_revision = 'q9f0a1b2c3d4'
branch_labels = None
depends_on = None


def _activation_deadline(moment):
    local = moment.astimezone(ZoneInfo('America/Sao_Paulo'))
    cutoff = local.replace(hour=21, minute=0, second=0, microsecond=0)
    if local >= cutoff:
        cutoff += timedelta(days=1)
    return cutoff.astimezone(timezone.utc)


def upgrade():
    op.add_column('auth_sessions', sa.Column('daily_expires_at', sa.DateTime(timezone=True)))
    # Do not use historical created_at here: a deployment during the shift must
    # not immediately revoke all legacy seven-day sessions. Keep earlier expiry
    # and revocation intact; runtime checks take the earliest persisted deadline.
    deadline = _activation_deadline(datetime.now(timezone.utc))
    op.get_bind().execute(sa.text('''UPDATE auth_sessions SET daily_expires_at = :deadline
        WHERE daily_expires_at IS NULL'''), {'deadline': deadline})


def downgrade():
    raise RuntimeError('Preserve session deadlines and access history; use a forward migration.')
