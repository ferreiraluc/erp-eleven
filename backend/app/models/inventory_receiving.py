"""Receiving catalog collections; never an inventory balance or stock movement."""
import uuid
from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base
from ..config import settings


class ReceivingLot(Base):
    __tablename__ = 'inventory_receiving_lots'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(160), nullable=False)
    notes = Column(Text, nullable=False, default='')
    received_on = Column(Date, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: settings.now(), nullable=False)
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now(), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)


class ReceivingLotItem(Base):
    __tablename__ = 'inventory_receiving_lot_items'
    __table_args__ = (UniqueConstraint('lot_id', 'item_id', name='uq_receiving_lot_item'),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lot_id = Column(UUID(as_uuid=True), ForeignKey('inventory_receiving_lots.id'), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey('inventory_items.id', ondelete='SET NULL'), nullable=True, index=True)
    item_name = Column(String(200), nullable=False)
    item_sku = Column(String(50), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: settings.now(), nullable=False)
