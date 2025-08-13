from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base

class UsuarioRole(enum.Enum):
    ADMIN = "ADMIN"
    GERENTE = "GERENTE"  # 2 managers
    VENDEDOR = "VENDEDOR"  # 3 salespeople
    LIMPEZA = "LIMPEZA"  # 1 cleaner

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    role = Column(Enum(UsuarioRole), nullable=False, default=UsuarioRole.VENDEDOR)
    ativo = Column(Boolean, default=True)
    ultimo_login = Column(DateTime)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relacionamentos
    rastreamentos_criados = relationship("Rastreamento", back_populates="criado_por")