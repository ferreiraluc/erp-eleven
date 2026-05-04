from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, DECIMAL, Integer, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base
from ..config import settings


class MovementType(enum.Enum):
    entry = "entry"
    exit = "exit"
    adjustment = "adjustment"
    transfer = "transfer"


class SessionStatus(enum.Enum):
    open = "open"
    counting = "counting"
    reviewing = "reviewing"
    applied = "applied"
    cancelled = "cancelled"


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    contact = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: settings.now())

    items = relationship("Item", back_populates="supplier")


class Item(Base):
    __tablename__ = "inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    size = Column(String(50))
    color = Column(String(50))
    unit = Column(String(20), default="un")
    location = Column(String(100))
    barcode = Column(String(200))
    sku_internal = Column(String(50), unique=True, nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    cost_price = Column(DECIMAL(12, 2), default=0)
    sale_price = Column(DECIMAL(12, 2), default=0)
    currency = Column(String(10), default="PYG")
    cost_currency = Column(String(10), default="BRL")
    sale_currency = Column(String(10), default="USD")
    min_stock = Column(Integer, default=0)
    max_stock = Column(Integer, default=0)
    current_stock = Column(Integer, default=0)
    brand = Column(String(100), nullable=True)
    group_key = Column(String(100), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    image_data = Column(Text, nullable=True)

    supplier = relationship("Supplier", back_populates="items")
    movements = relationship("StockMovement", back_populates="item")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    movement_type = Column(SAEnum(MovementType), nullable=False)
    quantity = Column(Integer, nullable=False)
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(String(500))
    reference_type = Column(String(50))
    reference_id = Column(String(100))
    unit_cost = Column(DECIMAL(12, 2))
    location_from = Column(String(100))
    location_to = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    item = relationship("Item", back_populates="movements")


class InventorySession(Base):
    __tablename__ = "inventory_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    status = Column(SAEnum(SessionStatus), default=SessionStatus.open)
    location_filter = Column(String(100))
    category_filter = Column(String(100))
    started_at = Column(DateTime, default=lambda: settings.now())
    finished_at = Column(DateTime)
    applied_at = Column(DateTime)
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    notes = Column(Text)

    session_items = relationship("InventorySessionItem", back_populates="session")


class InventorySessionItem(Base):
    __tablename__ = "inventory_session_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("inventory_sessions.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    system_quantity = Column(Integer, nullable=False)
    counted_quantity = Column(Integer)
    scanned_at = Column(DateTime)
    counted_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    session = relationship("InventorySession", back_populates="session_items")
    item = relationship("Item")
