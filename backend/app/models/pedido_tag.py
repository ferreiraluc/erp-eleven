from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base
from ..config import settings

# Tabela de associação many-to-many entre pedidos e tags
pedido_tags_association = Table(
    'pedido_tags',
    Base.metadata,
    Column('pedido_id', UUID(as_uuid=True), ForeignKey('pedidos.id'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('tags_status.id'), primary_key=True)
)

class TagStatus(Base):
    __tablename__ = "tags_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(50), unique=True, nullable=False)
    cor = Column(String(7), nullable=False, default="#6B7280")  # Hex color
    descricao = Column(String(200))
    ativo = Column(Boolean, default=True)
    ordem = Column(String(10), default="50")  # Para ordenação visual

    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    # Relacionamentos
    pedidos = relationship("Pedido", secondary=pedido_tags_association, back_populates="tags")
    usuario_criador = relationship("Usuario", foreign_keys=[created_by])