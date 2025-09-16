from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class TagStatusBase(BaseModel):
    nome: str
    cor: str = "#6B7280"  # Cor padrão cinza
    descricao: Optional[str] = None
    ordem: str = "50"
    ativo: bool = True

class TagStatusCreate(TagStatusBase):
    created_by: Optional[uuid.UUID] = None

class TagStatusUpdate(BaseModel):
    nome: Optional[str] = None
    cor: Optional[str] = None
    descricao: Optional[str] = None
    ordem: Optional[str] = None
    ativo: Optional[bool] = None

class TagStatusResponse(TagStatusBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True

# Schema simplificado para ser usado em responses de pedidos
class TagStatusSimple(BaseModel):
    id: uuid.UUID
    nome: str
    cor: str
    ordem: str

    class Config:
        from_attributes = True