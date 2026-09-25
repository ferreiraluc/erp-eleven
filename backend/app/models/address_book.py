"""Reusable addresses, versioned layouts and durable freight operations."""
import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, JSON, ForeignKey, Numeric, LargeBinary, Index, event, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import deferred
from ..database import Base
from .assistant import utcnow


class SavedAddress(Base):
    __tablename__ = 'saved_addresses'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String(120), nullable=False)
    cliente_id = Column(UUID(as_uuid=True), ForeignKey('clientes.id'), index=True)
    pdv_cliente_id = Column(UUID(as_uuid=True), ForeignKey('pdv_clientes.id'), index=True)
    data = Column(JSON, nullable=False)
    dedup_key = Column(String(64))
    merged_into_id = Column(UUID(as_uuid=True), ForeignKey('saved_addresses.id'), index=True)
    __table_args__ = (Index('uq_saved_address_identity', 'dedup_key', unique=True,
        postgresql_where=text('merged_into_id IS NULL AND dedup_key IS NOT NULL'),
        sqlite_where=text('merged_into_id IS NULL AND dedup_key IS NOT NULL')),)
    active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class PrintLayout(Base):
    __tablename__ = 'print_layouts'
    id = Column(String(30), primary_key=True)
    name = Column(String(100), nullable=False)
    config = Column(JSON, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class FreightOrder(Base):
    __tablename__ = 'freight_orders'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_key = Column(UUID(as_uuid=True), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    address_id = Column(UUID(as_uuid=True), ForeignKey('saved_addresses.id'), index=True)
    environment = Column(String(16), nullable=False)
    state = Column(String(30), nullable=False, default='quoted')
    payload = Column(JSON, nullable=False)
    rates = Column(JSON, nullable=False)
    provider_id = Column(String(100))
    service = Column(Integer)
    price = Column(Numeric(12,2))
    tracking = Column(String(100))
    label_url = Column(String(2000))
    label_pdf = deferred(Column(LargeBinary))
    label_status = Column(String(20), nullable=False, default='none')
    label_attempts = Column(Integer, nullable=False, default=0)
    label_check_at = Column(DateTime(timezone=True), index=True)
    label_error = Column(String(200))
    auto_print = Column(Boolean, nullable=False, default=False)
    print_device_id = Column(UUID(as_uuid=True), ForeignKey('print_devices.id'))
    print_job_id = Column(UUID(as_uuid=True), ForeignKey('print_jobs.id'))
    notify_channel = Column(String(16))
    notify_destination = Column(String(120))
    error = Column(String(200))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class FreightWebhook(Base):
    __tablename__ = 'freight_webhooks'
    environment = Column(String(16), primary_key=True)
    provider_id = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret_encrypted = Column(String(2000), nullable=False)


@event.listens_for(SavedAddress, 'before_insert')
@event.listens_for(SavedAddress, 'before_update')
def set_address_identity(mapper, connection, target):
    from ..services.address_identity import fingerprint
    target.dedup_key = None if target.merged_into_id else fingerprint(target.data)
