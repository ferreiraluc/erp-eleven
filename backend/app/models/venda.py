from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, DECIMAL, Date, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base
from ..config import settings

class MoedaTipo(enum.Enum):
    G_DOLLAR = "G$"
    R_DOLLAR = "R$"
    U_DOLLAR = "U$"
    EUR = "EUR"

class PagamentoMetodo(enum.Enum):
    PIX_POWER = "PIX_POWER"
    PIX_THAIS = "PIX_THAIS"
    PIX_MERCADO_PAGO = "PIX_MERCADO_PAGO"
    CREDITO = "CREDITO"
    DEBITO = "DEBITO"
    PY_TRANSFER_SUDAMERIS = "PY_TRANSFER_SUDAMERIS"
    PY_TRANSFER_INTERFISA = "PY_TRANSFER_INTERFISA"

class Venda(Base):
    __tablename__ = "vendas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_venda = Column(Date, nullable=False, default=func.current_date())
    vendedor_id = Column(UUID(as_uuid=True), ForeignKey("vendedores.id"), nullable=False)
    
    moeda = Column(Enum(MoedaTipo, name='moeda_tipo', native_enum=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    valor_bruto = Column(DECIMAL(15,4), nullable=False)
    metodo_pagamento = Column(Enum(PagamentoMetodo, name='pagamento_metodo', native_enum=True, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    
    cambista_id = Column(UUID(as_uuid=True), ForeignKey("cambistas.id"))
    taxa_cambio_usada = Column(DECIMAL(8,4))
    valor_cambista = Column(DECIMAL(15,4))
    valor_liquido = Column(DECIMAL(15,4), nullable=False)
    taxa_desconto_pagamento = Column(DECIMAL(5,4), default=0)  # Fee percentage applied
    
    # Thais transfer tracking
    pending_transfer_id = Column(UUID(as_uuid=True), ForeignKey("money_transfers.id"), nullable=True)
    requires_thais_transfer = Column(Boolean, default=False)  # True for PIX_THAIS sales
    
    descricao_produto = Column(Text)
    observacoes = Column(Text)
    
    semana_fechamento = Column(Date)
    fechado = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    vendedor = relationship("Vendedor", backref="vendas")
    cambista = relationship("Cambista", backref="vendas")
    usuario_criador = relationship("Usuario", foreign_keys=[created_by])
    pending_transfer = relationship("MoneyTransfer", foreign_keys=[pending_transfer_id], back_populates="related_sales")