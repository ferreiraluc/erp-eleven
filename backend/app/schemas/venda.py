from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid
from ..models.venda import MoedaTipo, PagamentoMetodo

class VendaBase(BaseModel):
    data_venda: Optional[date] = None
    moeda: MoedaTipo
    valor_bruto: Decimal
    metodo_pagamento: PagamentoMetodo
    taxa_cambio_usada: Optional[Decimal] = None
    valor_cambista: Optional[Decimal] = None
    valor_liquido: Decimal
    descricao_produto: Optional[str] = None
    observacoes: Optional[str] = None

class VendaCreate(VendaBase):
    vendedor_id: uuid.UUID
    cambista_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None

class VendaResponse(VendaBase):
    id: uuid.UUID
    vendedor_id: uuid.UUID
    cambista_id: Optional[uuid.UUID] = None
    semana_fechamento: Optional[date] = None
    fechado: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True