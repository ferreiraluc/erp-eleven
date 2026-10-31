"""Short-lived media for the authenticated WhatsApp Web bridge."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base
from .assistant import utcnow


class WhatsAppMedia(Base):
    __tablename__ = "assistant_whatsapp_media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True)
    conversation_id = Column(String(120), nullable=False)
    message_external_id = Column(String(120), nullable=False, unique=True)
    kind = Column(String(20), nullable=False)
    mime_type = Column(String(100), nullable=False)
    byte_size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
