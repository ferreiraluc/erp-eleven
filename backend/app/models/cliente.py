from sqlalchemy import Column, String, Boolean, DateTime, Text, Index, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base
from ..config import settings


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(200), nullable=False)
    telefone = Column(String(20))
    email = Column(String(100))
    cpf = Column(String(14), unique=True, nullable=True)
    endereco = Column(Text)  # campo livre — colar endereço completo

    merged_into_id = Column(UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=True, index=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: settings.now())
    updated_at = Column(DateTime, default=lambda: settings.now(), onupdate=lambda: settings.now())

    pedidos = relationship("Pedido", back_populates="cliente")

    __table_args__ = (
        CheckConstraint("merged_into_id IS NULL OR merged_into_id <> id", name="ck_clientes_merge_not_self"),
        CheckConstraint("merged_into_id IS NULL OR ativo = false", name="ck_clientes_merged_inactive"),
        Index("idx_clientes_nome", "nome"),
        Index("idx_clientes_telefone", "telefone"),
        Index("idx_clientes_email", "email"),
    )
