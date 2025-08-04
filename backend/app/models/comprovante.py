from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base

class Comprovante(Base):
    __tablename__ = "comprovantes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venda_id = Column(UUID(as_uuid=True), ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)
    
    nome_arquivo = Column(String(255), nullable=False)
    arquivo_url = Column(String(500), nullable=False)
    tipo_arquivo = Column(String(10), nullable=False)
    tamanho_bytes = Column(BigInteger)
    
    aprovado = Column(Boolean, default=False)
    aprovado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    aprovado_em = Column(DateTime)
    
    created_at = Column(DateTime, default=func.current_timestamp())
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    venda = relationship("Venda", backref="comprovantes")
    aprovador = relationship("Usuario", foreign_keys=[aprovado_por])
    uploader = relationship("Usuario", foreign_keys=[uploaded_by])