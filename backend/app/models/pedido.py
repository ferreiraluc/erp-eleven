from sqlalchemy import Column, String, DateTime, ForeignKey, DECIMAL, Date, Text, Enum
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_pedido = Column(String(50), unique=True, nullable=False)

    # Descrição do pedido (ex: "1 tênis Nike + 3 camisetas")
    descricao = Column(Text, nullable=False)

    # Valor total do pedido
    valor_total = Column(DECIMAL(10,2), nullable=False)

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

    # Relacionamentos
    usuario_criador = relationship("Usuario", foreign_keys=[created_by])
    rastreamentos = relationship("Rastreamento", back_populates="pedido")
    tags = relationship("TagStatus", secondary=pedido_tags_association, back_populates="pedidos")