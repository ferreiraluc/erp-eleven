"""Printer-scoped credentials and durable, at-most-once dispatch."""
import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, LargeBinary, String, JSON, Integer, Index, text
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base
from .assistant import utcnow


class PrintDevice(Base):
    __tablename__ = "print_devices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    purpose = Column(String(20), nullable=False, default='documents', server_default='documents')
    driver = Column(String(20), nullable=False, default='windows', server_default='windows')
    paper_width_mm = Column(Integer, nullable=False, default=60, server_default='60')
    paper_height_mm = Column(Integer, nullable=False, default=80, server_default='80')
    auto_receipts = Column(Boolean, nullable=False, default=False, server_default='false')
    last_seen_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index('uq_print_device_auto_receipts', 'auto_receipts', unique=True,
                           postgresql_where=text('auto_receipts = true'),
                           sqlite_where=text('auto_receipts = 1')),)


class PrintJob(Base):
    __tablename__ = "print_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("print_devices.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    request_key = Column(UUID(as_uuid=True), nullable=False, unique=True)
    claim_key = Column(UUID(as_uuid=True), unique=True)
    snapshot = Column(JSON)
    diagnostic = Column(JSON)
    address_id = Column(UUID(as_uuid=True), ForeignKey('saved_addresses.id'), index=True)
    source = Column(String(20), nullable=False, default='upload')
    parent_id = Column(UUID(as_uuid=True), ForeignKey('print_jobs.id'))
    pdf = Column(LargeBinary, nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    claimed_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))



class PrintSender(Base):
    __tablename__ = "print_senders"
    id = Column(String(30), primary_key=True)
    name = Column(String(100), nullable=False)
    lines = Column(JSON, nullable=False)
    data = Column(JSON)
    active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

from .address_book import SavedAddress, PrintLayout, FreightOrder  # register FK targets
