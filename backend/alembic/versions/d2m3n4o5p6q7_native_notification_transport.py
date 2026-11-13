"""Add opt-in mobile push transport without changing Web Push bindings."""
from alembic import op
import sqlalchemy as sa

revision = 'd2m3n4o5p6q7'
down_revision = 'c1l2m3n4o5p6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notification_push_subscriptions', sa.Column('transport', sa.String(12), nullable=False, server_default='web'))
    op.add_column('notification_push_subscriptions', sa.Column('installation_hash', sa.String(64), nullable=True))
    op.create_check_constraint('ck_notification_push_transport', 'notification_push_subscriptions', "transport IN ('web', 'fcm', 'apns')")
    op.create_index('ix_notification_push_installation', 'notification_push_subscriptions', ['installation_hash', 'transport'])


def downgrade():
    raise RuntimeError('Preserve as inscrições e históricos; use uma migração corretiva para avançar.')
