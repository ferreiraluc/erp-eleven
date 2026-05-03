from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class PedidoAnexoCreate(BaseModel):
    nome_arquivo: str
    tipo_arquivo: str  # mime type
    tamanho: int       # bytes
    dados: str         # base64 (no data: prefix)


class PedidoAnexoResponse(BaseModel):
    id: uuid.UUID
    pedido_id: uuid.UUID
    nome_arquivo: str
    tipo_arquivo: str
    tamanho: int
    dados: str
    created_at: datetime
    created_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True
