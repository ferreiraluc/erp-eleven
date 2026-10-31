"""Durable inbox/outbox and explicitly shared operational memory."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AssistantIdentity(Base):
    __tablename__ = "assistant_identities"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_assistant_identity"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(16), nullable=False)
    external_id = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    can_register = Column(Boolean, nullable=False, default=False)


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_assistant_message"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(16), nullable=False)
    external_id = Column(String(120), nullable=False)
    conversation_id = Column(String(120), nullable=False, index=True)
    sender_id = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    text = Column(Text, nullable=False)
    response = Column(Text)
    attachment = Column(JSONB(none_as_null=True))
    should_reply = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    error_code = Column(String(80))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    available_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AssistantNote(Base):
    __tablename__ = "assistant_notes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_message_id = Column(UUID(as_uuid=True), ForeignKey("assistant_messages.id"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    kind = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    confirmed_at = Column(DateTime(timezone=True))


class AssistantDelivery(Base):
    __tablename__ = "assistant_deliveries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key = Column(String(240), nullable=False, unique=True)
    channel = Column(String(16), nullable=False)
    destination = Column(String(120), nullable=False)
    text = Column(Text, nullable=False)
    # user_id is null only for configured group notifications.
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    provider_id = Column(String(120))
    document_url = Column(String(2000))
    document_pdf = Column(LargeBinary)
    reply_markup = Column(JSONB)
    error_code = Column(String(80))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    available_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True))
    depends_on_id = Column(UUID(as_uuid=True), ForeignKey("assistant_deliveries.id"), nullable=True)
    bridge_claim_key = Column(UUID(as_uuid=True), unique=True)
    bridge_id = Column(String(20), ForeignKey("assistant_whatsapp_bridges.id"))


class AssistantWhatsAppBridge(Base):
    """One explicitly paired WhatsApp Web account, separate from Twilio."""
    __tablename__ = "assistant_whatsapp_bridges"
    id = Column(String(20), primary_key=True, default="primary")
    name = Column(String(100), nullable=False, default="WhatsApp Eleven")
    enabled = Column(Boolean, nullable=False, default=False)
    allow_private = Column(Boolean, nullable=False, default=True)
    notify_tracking = Column(Boolean, nullable=False, default=False)
    group_mode = Column(String(20), nullable=False, default="mention")
    allowed_groups = Column(JSONB, nullable=False, default=list)
    discovered_groups = Column(JSONB, nullable=False, default=list)
    token_hash = Column(String(64), unique=True)
    state = Column(String(30), nullable=False, default="starting")
    session_generation = Column(Integer, nullable=False, default=0)
    account_phone = Column(String(30))
    agent_version = Column(String(40))
    error_code = Column(String(80))
    last_seen_at = Column(DateTime(timezone=True))
    pairing_qr = Column(Text)
    pairing_qr_hash = Column(String(64))
    pairing_expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AssistantAction(Base):
    """A concrete ERP write awaiting its author's confirmation in the same conversation."""
    __tablename__ = "assistant_actions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_message_id = Column(UUID(as_uuid=True), ForeignKey("assistant_messages.id"), nullable=False, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    kind = Column(String(20), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    result_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    executed_at = Column(DateTime(timezone=True))


class AssistantKnowledge(Base):
    """Versioned capability catalog and explicitly confirmed employee aliases. No live balances."""
    __tablename__ = "assistant_knowledge"
    key = Column(String(160), primary_key=True)
    kind = Column(String(30), nullable=False, index=True)
    data = Column(JSONB, nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
