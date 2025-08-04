from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
import uuid

class CambistaBase(BaseModel):
    nome: str
    taxa_g_para_r: Optional[Decimal] = Decimal("5.65")
    taxa_u_para_r: Optional[Decimal] = Decimal("5.50")
    taxa_eur_para_r: Optional[Decimal] = Decimal("6.20")
    conta_bancaria: Optional[str] = None
    telefone: Optional[str] = None
    ativo: Optional[bool] = True
    observacoes: Optional[str] = None

class CambistaCreate(CambistaBase):
    pass

class CambistaResponse(CambistaBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True