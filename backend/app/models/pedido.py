from sqlalchemy import Column, String, DateTime, ForeignKey, DECIMAL, Date, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base

class PedidoStatus(enum.Enum):
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    ENVIADO = "ENVIADO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"

class TransportadoraTipo(enum.Enum):
    CORREIOS = "CORREIOS"
    AZUL_CARGO = "AZUL_CARGO"
    PARTICULAR = "PARTICULAR"
    SUPERFRETE = "SUPERFRETE"

class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_pedido = Column(String(50), unique=True, nullable=False)
    
    cliente_nome = Column(String(200), nullable=False)
    cliente_telefone = Column(String(20))
    cliente_email = Column(String(100))
    
    endereco_rua = Column(String(300), nullable=False)
    endereco_numero = Column(String(20))
    endereco_complemento = Column(String(100))
    endereco_bairro = Column(String(100))
    endereco_cidade = Column(String(100), nullable=False)
    endereco_uf = Column(String(2), nullable=False)
    endereco_cep = Column(String(10), nullable=False)
    
    transportadora = Column(Enum(TransportadoraTipo), nullable=False)
    codigo_rastreio = Column(String(100))
    valor_frete = Column(DECIMAL(10,2))
    peso_kg = Column(DECIMAL(8,3))
    
    status = Column(Enum(PedidoStatus), default=PedidoStatus.PENDENTE)
    data_pedido = Column(Date, default=func.current_date())
    data_envio = Column(Date)
    data_entrega = Column(Date)
    
    observacoes = Column(Text)
    instrucoes_entrega = Column(Text)
    
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    usuario_criador = relationship("Usuario", foreign_keys=[created_by])
    rastreamentos = relationship("Rastreamento", back_populates="pedido")