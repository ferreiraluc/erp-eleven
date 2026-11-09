"""Reservation lines, immutable deposits and idempotent operation receipts."""
import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, Text, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base
from ..config import settings


class PedidoItem(Base):
    __tablename__ = 'pedido_items'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(UUID(as_uuid=True), ForeignKey('pedidos.id'), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey('inventory_items.id'), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)
    item_name = Column(String(300), nullable=False)
    item_sku = Column(String(50))
    item_size = Column(String(50))
    item_color = Column(String(50))
    item_category = Column(String(100))
    location = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    returned_quantity = Column(Integer, nullable=False, default=0, server_default='0')
    unit_price_gs = Column(Numeric(15, 2), nullable=False)
    total_gs = Column(Numeric(15, 2), nullable=False)
    pedido = relationship('Pedido', back_populates='reserved_items')
    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_pedido_item_quantity'),
        CheckConstraint('returned_quantity >= 0 AND returned_quantity <= quantity', name='ck_pedido_item_returned'),
        CheckConstraint("location IN ('loja', 'deposito')", name='ck_pedido_item_location'),
        CheckConstraint('unit_price_gs >= 0 AND total_gs >= 0', name='ck_pedido_item_prices'),
    )


class PedidoPayment(Base):
    __tablename__ = 'pedido_payments'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(UUID(as_uuid=True), ForeignKey('pedidos.id'), nullable=False, index=True)
    method = Column(String(30), nullable=False)
    currency = Column(String(4), nullable=False)
    amount_original = Column(Numeric(15, 2), nullable=False)
    exchange_rate = Column(Numeric(15, 6), nullable=False)
    amount_gs = Column(Numeric(15, 2), nullable=False)
    card_fee_gs = Column(Numeric(15, 2), nullable=False, default=0, server_default='0')
    card_fee_percent = Column(Numeric(5, 2), nullable=False, default=0, server_default='0')
    cambista_id = Column(UUID(as_uuid=True), ForeignKey('cambistas.id'))
    reference = Column(String(200))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    reversed_at = Column(DateTime(timezone=True))
    reversed_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    reversal_reason = Column(Text)
    sale_payment_id = Column(UUID(as_uuid=True), ForeignKey('pdv_payments.id', ondelete='SET NULL'), nullable=True, unique=True)
    pedido = relationship('Pedido', back_populates='reservation_payments')
    refunds = relationship('PedidoPaymentRefund', back_populates='payment', order_by='PedidoPaymentRefund.created_at')
    __table_args__ = (CheckConstraint('amount_gs > 0', name='ck_pedido_payment_positive'),)


class PedidoOperation(Base):
    __tablename__ = 'pedido_operations'
    id = Column(UUID(as_uuid=True), primary_key=True)  # caller's durable request_id
    pedido_id = Column(UUID(as_uuid=True), ForeignKey('pedidos.id'), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    operation = Column(String(80), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: settings.now())


class PedidoPaymentRefund(Base):
    """Append-only confirmation of money returned outside the ERP."""
    __tablename__ = 'pedido_payment_refunds'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey('pedido_payments.id'), nullable=False, index=True)
    amount_gs = Column(Numeric(15, 2), nullable=False)
    amount_original = Column(Numeric(15, 2), nullable=False)
    card_fee_gs = Column(Numeric(15, 2), nullable=False, default=0, server_default='0')
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    payment = relationship('PedidoPayment', back_populates='refunds')
    __table_args__ = (CheckConstraint('amount_gs > 0 AND amount_original >= 0 AND card_fee_gs >= 0', name='ck_pedido_refund_positive'),)
