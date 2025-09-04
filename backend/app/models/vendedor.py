from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Vendedor(Base):
    __tablename__ = "vendedores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    taxa_comissao = Column(DECIMAL(5,2), default=10.00)
    meta_semanal = Column(DECIMAL(12,2), default=0)
    conta_bancaria = Column(String(50))
    telefone = Column(String(20))
    cor_calendario = Column(String(7), default="#3B82F6")
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    usuario = relationship("Usuario", backref="vendedor")