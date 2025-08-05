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
    taxa_desconto_pagamento: Optional[Decimal] = None
    descricao_produto: Optional[str] = None
    observacoes: Optional[str] = None

class VendaCreate(BaseModel):
    # Sales flow: Currency, Amount, Seller, Payment Method
    moeda: MoedaTipo
    valor_bruto: Decimal
    vendedor_id: uuid.UUID
    metodo_pagamento: PagamentoMetodo
    # Optional fields
    data_venda: Optional[date] = None
    cambista_id: Optional[uuid.UUID] = None
    descricao_produto: Optional[str] = None
    observacoes: Optional[str] = None
    created_by: Optional[uuid.UUID] = None

class VendaCreateComplete(VendaBase):
    # Complete schema for internal use
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