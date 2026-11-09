"""Durable receipt for explicitly reviewed order-directory archival batches."""
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from ..config import settings
from ..database import Base


class PedidoArchiveOperation(Base):
    __tablename__ = 'pedido_archive_operations'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    order_ids = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: settings.now())
