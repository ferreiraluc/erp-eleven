import enum
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base
from ..config import settings


class PdvCliente(Base):
    __tablename__ = "pdv_clientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(200), nullable=False)
    doc = Column(String(30), nullable=True)          # CPF, RUC, CI
    telefone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    tipo = Column(String(20), default="varejo")      # varejo, atacadista
    limite_fiado_gs = Column(Numeric(15, 2), default=0)
    saldo_fiado_gs = Column(Numeric(15, 2), default=0)   # saldo devedor atual
    notas = Column(Text)
    ativo = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    sales = relationship("PdvSale", back_populates="cliente")
    fiado_movements = relationship(
        "PdvFiadoMovement", back_populates="cliente",
        order_by="PdvFiadoMovement.created_at"
    )

    __table_args__ = (
        Index("idx_pdv_clientes_nome", "nome"),
        Index("idx_pdv_clientes_tipo", "tipo"),
    )


class PdvSale(Base):
    __tablename__ = "pdv_sales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendedor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    cliente_id = Column(UUID(as_uuid=True), ForeignKey("pdv_clientes.id"), nullable=True)
    cliente_nome = Column(String(200), nullable=True)   # snapshot / anônimo

    subtotal_gs = Column(Numeric(15, 2), default=0)
    desconto_gs = Column(Numeric(15, 2), default=0)
    total_gs = Column(Numeric(15, 2), default=0)

    status = Column(String(20), default="completed")    # completed, cancelled
    stock_applied = Column(Boolean, default=False)
    notas = Column(Text)

    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    vendedor = relationship("Usuario", foreign_keys=[vendedor_id])
    cliente = relationship("PdvCliente", back_populates="sales")
    items = relationship("PdvSaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments = relationship("PdvPayment", back_populates="sale", cascade="all, delete-orphan")
    fiado_movements = relationship("PdvFiadoMovement", back_populates="sale")

    __table_args__ = (
        Index("idx_pdv_sales_created_at", "created_at"),
        Index("idx_pdv_sales_vendedor", "vendedor_id"),
        Index("idx_pdv_sales_cliente", "cliente_id"),
    )


class PdvSaleItem(Base):
    __tablename__ = "pdv_sale_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("pdv_sales.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)

    item_name = Column(String(300), nullable=False)
    item_sku = Column(String(50), nullable=True)
    item_category = Column(String(100), nullable=True)
    item_size = Column(String(20), nullable=True)
    item_color = Column(String(50), nullable=True)

    quantity = Column(Numeric(10, 3), default=1)
    unit_price_gs = Column(Numeric(15, 2), nullable=False)
    original_price_gs = Column(Numeric(15, 2), nullable=True)
    discount_gs = Column(Numeric(15, 2), default=0)
    total_gs = Column(Numeric(15, 2), nullable=False)

    is_avulso = Column(Boolean, default=False)
    location = Column(String(20), default="loja")   # loja ou deposito

    sale = relationship("PdvSale", back_populates="items")


class PdvPayment(Base):
    __tablename__ = "pdv_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("pdv_sales.id"), nullable=False)
    cambista_id = Column(UUID(as_uuid=True), ForeignKey("cambistas.id"), nullable=True)

    method = Column(String(30), nullable=False)
    currency = Column(String(3), default="GS")       # GS, BRL, USD, EUR
    amount_original = Column(Numeric(15, 2), nullable=False)
    exchange_rate = Column(Numeric(15, 6), default=1)
    amount_gs = Column(Numeric(15, 2), nullable=False)
    reference = Column(String(200), nullable=True)   # últimos 4 cartão, chave PIX, etc.

    created_at = Column(DateTime, default=lambda: settings.now())

    sale = relationship("PdvSale", back_populates="payments")
    cambista = relationship("Cambista", foreign_keys=[cambista_id])


class PdvFiadoMovement(Base):
    __tablename__ = "pdv_fiado_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id = Column(UUID(as_uuid=True), ForeignKey("pdv_clientes.id"), nullable=False)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("pdv_sales.id"), nullable=True)

    tipo = Column(String(10), nullable=False)    # debit, payment
    valor_gs = Column(Numeric(15, 2), nullable=False)
    saldo_gs = Column(Numeric(15, 2), nullable=False)   # saldo após este movimento
    notas = Column(Text)

    created_at = Column(DateTime, default=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    cliente = relationship("PdvCliente", back_populates="fiado_movements")
    sale = relationship("PdvSale", back_populates="fiado_movements")

    __table_args__ = (
        Index("idx_pdv_fiado_cliente", "cliente_id"),
    )
