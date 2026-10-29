"""Opt-in Wonca monitoring; no subscriptions or remote calls during migration."""
from alembic import op
import sqlalchemy as sa

revision = 't2c3d4e5f6a7'
down_revision = 's1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rastreamentos', sa.Column('provedor_verificado_em', sa.DateTime(timezone=True)))
    op.create_table('wonca_config',
        sa.Column('id', sa.String(16), primary_key=True),
        sa.Column('endpoint_id', sa.String(36), nullable=False),
        sa.Column('profile_id', sa.String(36), nullable=False),
        sa.Column('interval_hours', sa.Integer(), nullable=False),
        sa.Column('monitor_days', sa.Integer(), nullable=False),
        sa.Column('daytime_only', sa.Boolean(), nullable=False),
        sa.Column('secret_encrypted', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('wonca_subscriptions',
        sa.Column('code', sa.String(13), primary_key=True),
        sa.Column('remote_id', sa.String(36)),
        sa.Column('endpoint_id', sa.String(36), nullable=False),
        sa.Column('profile_id', sa.String(36), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('retry_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(40)))
    op.create_index('ix_wonca_subscriptions_state', 'wonca_subscriptions', ['state'])
    op.create_table('wonca_events',
        sa.Column('event_id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(13), nullable=False),
        sa.Column('body_hash', sa.String(64), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', sa.JSON()),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(40)),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_wonca_events_code', 'wonca_events', ['code'])
    op.create_index('ix_wonca_events_status', 'wonca_events', ['status'])


def downgrade():
    raise RuntimeError('Preserve monitoring identities and delivery receipts; use a forward migration.')
