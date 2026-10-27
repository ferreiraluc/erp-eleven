"""Persistent notification inbox and leased device delivery; preserve all operational history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'o7d8e9f0a1b2'
down_revision = 'n6c7d8e9f0a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('request_id', UUID(as_uuid=True), nullable=True),
        sa.Column('dedupe_key', sa.String(200), nullable=True),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('action_path', sa.String(500), nullable=True),
        sa.Column('requires_ack', sa.Boolean(), nullable=False),
        sa.Column('requires_response', sa.Boolean(), nullable=False),
        sa.Column('entity_type', sa.String(40), nullable=True),
        sa.Column('entity_id', sa.String(100), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.UniqueConstraint('request_id'),
        sa.UniqueConstraint('dedupe_key'))
    op.create_index('ix_notifications_created', 'notifications', ['created_at', 'id'], unique=False)
    op.create_index('ix_notifications_pending', 'notifications', ['published_at', 'cancelled_at', 'scheduled_at'], unique=False)

    op.create_table('notification_recipients',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('notification_id', UUID(as_uuid=True), sa.ForeignKey('notifications.id'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledgement_note', sa.Text(), nullable=True),
        sa.Column('read_version', sa.Integer(), nullable=True),
        sa.Column('acknowledged_version', sa.Integer(), nullable=True),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('notification_id', 'user_id', name='uq_notification_recipient'))
    op.create_index('ix_notification_recipient_user', 'notification_recipients', ['user_id', 'read_at', 'notification_id'], unique=False)

    op.create_table('notification_revisions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('notification_id', UUID(as_uuid=True), sa.ForeignKey('notifications.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('notification_id', 'version', name='uq_notification_revision'))

    op.create_table('notification_preferences',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), primary_key=True, nullable=False),
        sa.Column('push_enabled', sa.Boolean(), nullable=False),
        sa.Column('sound_enabled', sa.Boolean(), nullable=False),
        sa.Column('categories', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))

    op.create_table('notification_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('action_path', sa.String(500), nullable=True),
        sa.Column('requires_ack', sa.Boolean(), nullable=False),
        sa.Column('requires_response', sa.Boolean(), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False))

    op.create_table('notification_rules',
        sa.Column('event_key', sa.String(60), primary_key=True, nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('template_id', UUID(as_uuid=True), sa.ForeignKey('notification_templates.id'), nullable=False),
        sa.Column('user_ids', sa.JSON(), nullable=False),
        sa.Column('local_time', sa.String(5), nullable=False),
        sa.Column('weekdays', sa.JSON(), nullable=False),
        sa.Column('last_run_date', sa.String(10), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False))

    op.create_table('notification_push_settings',
        sa.Column('key', sa.String(80), primary_key=True, nullable=False),
        sa.Column('value', sa.JSON(), nullable=False))

    op.create_table('notification_push_subscriptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('auth_session_id', UUID(as_uuid=True), sa.ForeignKey('auth_sessions.id'), nullable=False),
        sa.Column('auth_version', sa.Integer(), nullable=False),
        sa.Column('endpoint_hash', sa.String(64), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh', sa.String(200), nullable=False),
        sa.Column('auth', sa.String(100), nullable=False),
        sa.Column('device_token_hash', sa.String(64), nullable=False),
        sa.Column('device_token_encrypted', sa.Text(), nullable=False),
        sa.Column('device_name', sa.String(100), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('endpoint_hash'))
    op.create_index('ix_notification_push_subscriptions_auth_session_id', 'notification_push_subscriptions', ['auth_session_id'], unique=False)
    op.create_index('ix_notification_push_subscriptions_user_id', 'notification_push_subscriptions', ['user_id'], unique=False)

    op.create_table('notification_push_deliveries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('notification_id', UUID(as_uuid=True), sa.ForeignKey('notifications.id'), nullable=False),
        sa.Column('recipient_id', UUID(as_uuid=True), sa.ForeignKey('notification_recipients.id'), nullable=False),
        sa.Column('subscription_id', UUID(as_uuid=True), sa.ForeignKey('notification_push_subscriptions.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_token', sa.String(36), nullable=True),
        sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(100), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('notification_id', 'subscription_id', name='uq_notification_push_delivery_device'))
    op.create_index('ix_notification_push_due', 'notification_push_deliveries', ['status', 'next_attempt_at'], unique=False)
    op.create_index('ix_notification_push_lease', 'notification_push_deliveries', ['status', 'lease_until'], unique=False)


def downgrade():
    raise RuntimeError('Preserve notifications, responses and delivery history; use a forward migration.')
