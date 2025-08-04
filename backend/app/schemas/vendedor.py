from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
import uuid

class VendedorBase(BaseModel):
    nome: str
    taxa_comissao: Optional[Decimal] = Decimal("10.00")
    meta_semanal: Optional[Decimal] = Decimal("0")
    conta_bancaria: Optional[str] = None
    telefone: Optional[str] = None
    ativo: Optional[bool] = True

class VendedorCreate(VendedorBase):
    usuario_id: Optional[uuid.UUID] = None

class VendedorResponse(VendedorBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True