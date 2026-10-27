"""Private device bindings and durable Web Push delivery leases."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base
from .access import now


class NotificationPushSetting(Base):
    __tablename__ = "notification_push_settings"
    key = Column(String(80), primary_key=True)
    value = Column(JSON, nullable=False)


class NotificationPushSubscription(Base):
    __tablename__ = "notification_push_subscriptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True)
    auth_session_id = Column(UUID(as_uuid=True), ForeignKey("auth_sessions.id"), nullable=False, index=True)
    auth_version = Column(Integer, nullable=False)
    endpoint_hash = Column(String(64), nullable=False, unique=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    device_token_hash = Column(String(64), nullable=False)
    device_token_encrypted = Column(Text, nullable=False)
    device_name = Column(String(100), nullable=False, default="Navegador")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)
    last_success_at = Column(DateTime(timezone=True))


class NotificationPushDelivery(Base):
    __tablename__ = "notification_push_deliveries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notifications.id"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("notification_recipients.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("notification_push_subscriptions.id"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=now)
    lease_token = Column(String(36))
    lease_until = Column(DateTime(timezone=True))
    last_error = Column(String(100))
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (
        UniqueConstraint("notification_id", "subscription_id", name="uq_notification_push_delivery_device"),
        Index("ix_notification_push_due", "status", "next_attempt_at"),
        Index("ix_notification_push_lease", "status", "lease_until"),
    )
