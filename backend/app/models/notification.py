"""Persistent inbox, reviewed message revisions and configurable event rules."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), unique=True)
    dedupe_key = Column(String(200), unique=True)
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(20), nullable=False, default='manual')
    severity = Column(String(20), nullable=False, default='info')
    action_path = Column(String(500))
    requires_ack = Column(Boolean, nullable=False, default=False)
    requires_response = Column(Boolean, nullable=False, default=False)
    entity_type = Column(String(40))
    entity_id = Column(String(100))
    scheduled_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    version = Column(Integer, nullable=False, default=1)
    __table_args__ = (Index('ix_notifications_pending', 'published_at', 'cancelled_at', 'scheduled_at'),
                      Index('ix_notifications_created', 'created_at', 'id'))


class NotificationRecipient(Base):
    __tablename__ = 'notification_recipients'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey('notifications.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    read_at = Column(DateTime(timezone=True))
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledgement_note = Column(Text)
    read_version = Column(Integer)
    acknowledged_version = Column(Integer)
    removed_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('notification_id', 'user_id', name='uq_notification_recipient'),
                      Index('ix_notification_recipient_user', 'user_id', 'read_at', 'notification_id'))


class NotificationRevision(Base):
    __tablename__ = 'notification_revisions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey('notifications.id'), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint('notification_id', 'version', name='uq_notification_revision'),)


class NotificationPreference(Base):
    __tablename__ = 'notification_preferences'
    user_id = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), primary_key=True)
    push_enabled = Column(Boolean, nullable=False, default=True)
    sound_enabled = Column(Boolean, nullable=False, default=True)
    categories = Column(JSON, nullable=False, default=lambda: ['manual', 'sales', 'tracking', 'reminder', 'greeting'])
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class NotificationTemplate(Base):
    __tablename__ = 'notification_templates'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(20), nullable=False)
    severity = Column(String(20), nullable=False, default='info')
    action_path = Column(String(500))
    requires_ack = Column(Boolean, nullable=False, default=False)
    requires_response = Column(Boolean, nullable=False, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    version = Column(Integer, nullable=False, default=1)


class NotificationRule(Base):
    __tablename__ = 'notification_rules'
    event_key = Column(String(60), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey('notification_templates.id'), nullable=False)
    user_ids = Column(JSON, nullable=False, default=list)
    local_time = Column(String(5), nullable=False, default='09:00')
    weekdays = Column(JSON, nullable=False, default=lambda: list(range(7)))
    last_run_date = Column(String(10))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    version = Column(Integer, nullable=False, default=1)
