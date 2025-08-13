from sqlalchemy import Column, String, Boolean, DateTime, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from ..database import Base


class RastreamentoStatus(str, enum.Enum):
    PENDENTE = "PENDENTE"
    EM_TRANSITO = "EM_TRANSITO"
    ENTREGUE = "ENTREGUE"
    ERRO = "ERRO"
    NAO_ENCONTRADO = "NAO_ENCONTRADO"


class Rastreamento(Base):
    __tablename__ = "rastreamentos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_rastreio = Column(String(100), nullable=False, unique=True, index=True)
    
    # Dados do rastreamento
    status = Column(ENUM(RastreamentoStatus, name="rastreamento_status"), default=RastreamentoStatus.PENDENTE)
    servico_provedor = Column(String(100))
    ultima_atualizacao = Column(DateTime)
    
    # Dados do objeto
    descricao = Column(Text)
    destinatario = Column(String(200))
    origem = Column(String(200))
    destino = Column(String(200))
    
    # Dados históricos (JSON para flexibilidade)
    historico_eventos = Column(JSONB, default=[])
    
    # Relacionamento com pedidos
    pedido_id = Column(UUID(as_uuid=True), ForeignKey('pedidos.id'), nullable=True)
    
    # Metadados
    data_criacao = Column(Date, default=func.current_date())
    ativo = Column(Boolean, default=True)
    
    # Auditoria
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    created_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    
    # Relacionamentos
    pedido = relationship("Pedido", back_populates="rastreamentos")
    criado_por = relationship("Usuario", back_populates="rastreamentos_criados")