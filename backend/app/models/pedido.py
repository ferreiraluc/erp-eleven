from sqlalchemy import Column, String, DateTime, ForeignKey, DECIMAL, Date, Text, Enum, Integer, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base
from ..config import settings
from .pedido_tag import pedido_tags_association

class PedidoStatus(enum.Enum):
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    ENVIADO = "ENVIADO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class Pedido(Base):
    __tablename__ = "pedidos"
    __table_args__ = (
        CheckConstraint("commerce_status IS NULL OR commerce_status IN ('reserved','completed','cancelled')",
                        name='ck_pedidos_commerce_status'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_pedido = Column(String(50), unique=True, nullable=False)

    # Descrição do pedido (ex: "1 tênis Nike + 3 camisetas")
    descricao = Column(Text, nullable=False)

    # Valor total do pedido
    valor_total = Column(DECIMAL(10,2), nullable=False)
    moeda = Column(String(3), nullable=False, default='R$')  # G$, R$, U$
    anexos_count = Column(Integer, nullable=False, default=0)

    # Dados do cliente (opcionais)
    cliente_nome = Column(String(200))
    cliente_telefone = Column(String(20))
    cliente_email = Column(String(100))

    # Endereço simples (opcional)
    endereco_entrega = Column(Text)  # Campo livre para endereço

    # Status e rastreamento
    status = Column(Enum(PedidoStatus), default=PedidoStatus.PENDENTE)
    codigo_rastreio = Column(String(100))

    # Metadados
    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    # FK para Cliente (opcional, retrocompatível)
    cliente_id = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=True, index=True)

    # Commercial reservations are independent of the logistics/Wonca status.
    # Null identifies legacy orders, which never reserved inventory implicitly.
    commerce_status = Column(String(20), nullable=True, index=True)
    commerce_version = Column(Integer, nullable=False, default=1, server_default='1')
    pdv_cliente_id = Column(UUID(as_uuid=True), ForeignKey('pdv_clientes.id'), nullable=True)
    vendedor_id = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=True)
    sale_id = Column(UUID(as_uuid=True), ForeignKey('pdv_sales.id'), nullable=True, unique=True)
    usd_rate_gs = Column(Numeric(12, 4), nullable=True)
    subtotal_gs = Column(Numeric(15, 2), nullable=True)
    desconto_gs = Column(Numeric(15, 2), nullable=True)
    total_gs = Column(Numeric(15, 2), nullable=True)
    paid_gs = Column(Numeric(15, 2), nullable=True)
    reserved_at = Column(DateTime(timezone=True), nullable=True)
    commerce_notes = Column(Text, nullable=True)

    # Relacionamentos
    usuario_criador = relationship("Usuario", foreign_keys=[created_by])
    rastreamentos = relationship("Rastreamento", back_populates="pedido")
    tags = relationship("TagStatus", secondary=pedido_tags_association, back_populates="pedidos")
    cliente = relationship("Cliente", back_populates="pedidos", foreign_keys=[cliente_id])
    anexos = relationship("PedidoAnexo", back_populates="pedido", cascade="all, delete-orphan", order_by="PedidoAnexo.created_at")
    reserved_items = relationship('PedidoItem', back_populates='pedido', cascade='all, delete-orphan', order_by='PedidoItem.position')
    reservation_payments = relationship('PedidoPayment', back_populates='pedido', order_by='PedidoPayment.created_at')
    vendedor = relationship('Usuario', foreign_keys=[vendedor_id])
