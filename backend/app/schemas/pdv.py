from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid


# ── PDV Cliente ───────────────────────────────────────────────────────────────

class PdvClienteCreate(BaseModel):
    nome: str
    doc: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    tipo: str = "varejo"          # varejo, atacadista
    limite_fiado_gs: float = 0
    notas: Optional[str] = None


class PdvClienteUpdate(BaseModel):
    nome: Optional[str] = None
    doc: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    tipo: Optional[str] = None
    limite_fiado_gs: Optional[float] = None
    notas: Optional[str] = None
    ativo: Optional[bool] = None


class PdvClienteResponse(BaseModel):
    id: uuid.UUID
    nome: str
    doc: Optional[str]
    telefone: Optional[str]
    email: Optional[str]
    tipo: str
    limite_fiado_gs: float
    saldo_fiado_gs: float
    notas: Optional[str]
    ativo: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── PDV Sale Items ────────────────────────────────────────────────────────────

class PdvSaleItemCreate(BaseModel):
    item_id: Optional[uuid.UUID] = None
    item_name: str
    item_sku: Optional[str] = None
    item_category: Optional[str] = None
    item_size: Optional[str] = None
    item_color: Optional[str] = None
    quantity: float = 1.0
    unit_price_gs: float
    original_price_gs: Optional[float] = None
    discount_gs: float = 0.0
    is_avulso: bool = False
    location: str = "loja"


class PdvSaleItemResponse(BaseModel):
    id: uuid.UUID
    item_id: Optional[uuid.UUID]
    item_name: str
    item_sku: Optional[str]
    item_category: Optional[str]
    item_size: Optional[str]
    item_color: Optional[str]
    quantity: float
    unit_price_gs: float
    original_price_gs: Optional[float]
    discount_gs: float
    total_gs: float
    is_avulso: bool
    location: str

    class Config:
        from_attributes = True


# ── PDV Payments ──────────────────────────────────────────────────────────────

class PdvPaymentCreate(BaseModel):
    method: str                   # cash_gs, cash_brl, pix, card, fiado, etc.
    currency: str = "GS"          # GS, BRL, USD, EUR
    amount_original: float
    exchange_rate: float = 1.0
    amount_gs: float
    cambista_id: Optional[uuid.UUID] = None
    reference: Optional[str] = None


class PdvPaymentResponse(BaseModel):
    id: uuid.UUID
    method: str
    currency: str
    amount_original: float
    exchange_rate: float
    amount_gs: float
    cambista_id: Optional[uuid.UUID]
    reference: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── PDV Sale ──────────────────────────────────────────────────────────────────

class PdvSaleCreate(BaseModel):
    vendedor_id: Optional[uuid.UUID] = None
    cliente_id: Optional[uuid.UUID] = None
    cliente_nome: Optional[str] = None
    items: List[PdvSaleItemCreate]
    desconto_gs: float = 0.0
    payments: List[PdvPaymentCreate]
    notas: Optional[str] = None


class PdvSaleResponse(BaseModel):
    id: uuid.UUID
    vendedor_id: Optional[uuid.UUID]
    cliente_id: Optional[uuid.UUID]
    cliente_nome: Optional[str]
    subtotal_gs: float
    desconto_gs: float
    total_gs: float
    status: str
    stock_applied: bool
    notas: Optional[str]
    items: List[PdvSaleItemResponse]
    payments: List[PdvPaymentResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class PdvSaleListItem(BaseModel):
    id: uuid.UUID
    cliente_nome: Optional[str]
    total_gs: float
    desconto_gs: float
    status: str
    items_count: int
    payment_methods: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Fiado ─────────────────────────────────────────────────────────────────────

class PdvFiadoPaymentCreate(BaseModel):
    valor_gs: float
    notas: Optional[str] = None


class PdvFiadoMovementResponse(BaseModel):
    id: uuid.UUID
    tipo: str
    valor_gs: float
    saldo_gs: float
    notas: Optional[str]
    sale_id: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True
