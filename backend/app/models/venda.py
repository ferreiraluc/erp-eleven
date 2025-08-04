from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, DECIMAL, Date, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base

class MoedaTipo(enum.Enum):
    G_DOLLAR = "G$"
    R_DOLLAR = "R$"
    U_DOLLAR = "U$"
    EUR = "EUR"

class PagamentoMetodo(enum.Enum):
    DEBITO = "DEBITO"
    CREDITO = "CREDITO"
    PIX = "PIX"
    DINHEIRO = "DINHEIRO"
    TRANSFERENCIA = "TRANSFERENCIA"

class Venda(Base):
    __tablename__ = "vendas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_venda = Column(Date, nullable=False, default=func.current_date())
    vendedor_id = Column(UUID(as_uuid=True), ForeignKey("vendedores.id"), nullable=False)
    
    moeda = Column(Enum(MoedaTipo), nullable=False)
    valor_bruto = Column(DECIMAL(15,4), nullable=False)
    metodo_pagamento = Column(Enum(PagamentoMetodo), nullable=False)
    
    cambista_id = Column(UUID(as_uuid=True), ForeignKey("cambistas.id"))
    taxa_cambio_usada = Column(DECIMAL(8,4))
    valor_cambista = Column(DECIMAL(15,4))
    valor_liquido = Column(DECIMAL(15,4), nullable=False)
    
    descricao_produto = Column(Text)
    observacoes = Column(Text)
    
    semana_fechamento = Column(Date)
    fechado = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    vendedor = relationship("Vendedor", backref="vendas")
    cambista = relationship("Cambista", backref="vendas")
    usuario_criador = relationship("Usuario", foreign_keys=[created_by])