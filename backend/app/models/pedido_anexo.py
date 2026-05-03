from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from ..database import Base
from ..config import settings


class PedidoAnexo(Base):
    __tablename__ = "pedido_anexos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(UUID(as_uuid=True), ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False)
    nome_arquivo = Column(String(255), nullable=False)
    tipo_arquivo = Column(String(100), nullable=False)  # mime type: image/jpeg, image/png, etc.
    tamanho = Column(Integer, nullable=False)  # original size in bytes
    dados = Column(Text, nullable=False)  # base64-encoded image data (no prefix)
    created_at = Column(DateTime, default=lambda: settings.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    pedido = relationship("Pedido", back_populates="anexos")
    criador = relationship("Usuario", foreign_keys=[created_by])
