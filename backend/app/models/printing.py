"""Printer-scoped credentials and durable, at-most-once dispatch."""
import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base
from .assistant import utcnow


class PrintDevice(Base):
    __tablename__ = "print_devices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PrintJob(Base):
    __tablename__ = "print_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("print_devices.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    request_key = Column(UUID(as_uuid=True), nullable=False, unique=True)
    pdf = Column(LargeBinary, nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    claimed_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

