from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Date, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base

class TipoFolga(str, enum.Enum):
    FOLGA = "FOLGA"
    FERIAS = "FERIAS"
    LICENCA = "LICENCA"
    FALTA = "FALTA"
    MEIO_PERIODO = "MEIO_PERIODO"

class Folga(Base):
    __tablename__ = "folgas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendedor_id = Column(UUID(as_uuid=True), ForeignKey("vendedores.id"), nullable=False)
    
    data = Column(Date, nullable=False)
    tipo = Column(Enum(TipoFolga), default=TipoFolga.FOLGA)
    
    periodo = Column(String(20), default="COMPLETO")  # COMPLETO, MANHA, TARDE
    motivo = Column(Text)
    aprovado = Column(Boolean, default=False)
    aprovado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    vendedor = relationship("Vendedor", backref="folgas")
    aprovador = relationship("Usuario", foreign_keys=[aprovado_por])