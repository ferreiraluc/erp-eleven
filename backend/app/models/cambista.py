from sqlalchemy import Column, String, Boolean, DateTime, DECIMAL, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from ..database import Base
from ..config import settings

class Cambista(Base):
    __tablename__ = "cambistas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    taxa_g_para_r = Column(DECIMAL(8,4), default=5.65)
    taxa_u_para_r = Column(DECIMAL(8,4), default=5.50)
    taxa_eur_para_r = Column(DECIMAL(8,4), default=6.20)
    conta_bancaria = Column(String(50))
    telefone = Column(String(20))
    ativo = Column(Boolean, default=True)
    observacoes = Column(Text)
    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
