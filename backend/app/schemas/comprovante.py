from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class ComprovanteBase(BaseModel):
    nome_arquivo: str
    arquivo_url: str
    tipo_arquivo: str
    tamanho_bytes: Optional[int] = None

class ComprovanteCreate(ComprovanteBase):
    venda_id: uuid.UUID
    uploaded_by: Optional[uuid.UUID] = None

class ComprovanteUpdate(BaseModel):
    aprovado: Optional[bool] = None
    aprovado_por: Optional[uuid.UUID] = None

class ComprovanteResponse(ComprovanteBase):
    id: uuid.UUID
    venda_id: uuid.UUID
    aprovado: bool
    aprovado_por: Optional[uuid.UUID] = None
    aprovado_em: Optional[datetime] = None
    created_at: datetime
    uploaded_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True