"""Revocable logins, transactional audit events and estimated active screen time."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


def now():
    return datetime.now(timezone.utc)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    activity_credit_at = Column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=now)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), index=True)
    actor_name = Column(String(100), nullable=False, default="Sistema")
    source = Column(String(30), nullable=False, default="web")
    action = Column(String(40), nullable=False)
    module = Column(String(80), nullable=False)
    entity = Column(String(100))
    entity_id = Column(String(100))
    request_id = Column(String(36), index=True)
    route = Column(String(200))
    method = Column(String(10))
    status_code = Column(Integer)
    changes = Column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_audit_events_time", "occurred_at"),)


class ActivitySpan(Base):
    __tablename__ = "activity_spans"
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("auth_sessions.id"), nullable=False, index=True)
    module = Column(String(80), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, default=now)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=now)
    active_seconds = Column(Integer, nullable=False, default=0)
    sequence = Column(Integer, nullable=False, default=0)
    __table_args__ = (Index("ix_activity_spans_time", "started_at"),)
