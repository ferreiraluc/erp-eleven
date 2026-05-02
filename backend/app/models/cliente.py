from sqlalchemy import Column, String, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(200), nullable=False)
    telefone = Column(String(20))
    email = Column(String(100))
    cpf = Column(String(14), unique=True, nullable=True)
    endereco = Column(Text)  # campo livre — colar endereço completo

    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    pedidos = relationship("Pedido", back_populates="cliente")

    __table_args__ = (
        Index("idx_clientes_nome", "nome"),
        Index("idx_clientes_telefone", "telefone"),
        Index("idx_clientes_email", "email"),
    )
