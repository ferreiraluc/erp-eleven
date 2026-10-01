from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base
from ..config import settings

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
    auth_version = Column(Integer, nullable=False, default=0, server_default="0")
    must_change_password = Column(Boolean, nullable=False, default=False, server_default="false")
    sales_scope = Column(String(10), nullable=False, default="all", server_default="all")
    sales_seller = Column(String(100))
    vendedor_id = Column(UUID(as_uuid=True), ForeignKey("vendedores.id"))
    ultimo_login = Column(DateTime)
    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    
    # Relacionamentos
    rastreamentos_criados = relationship("Rastreamento", back_populates="criado_por")
