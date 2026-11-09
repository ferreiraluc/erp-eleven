"""Explicit, bounded commands for a commercial order. Never implicit payments."""
import uuid
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator
from .pdv import PdvPaymentCreate


class ReservaCommand(BaseModel):
    request_id: uuid.UUID
    confirm: Literal[True]
    expected_version: Optional[int] = Field(default=None, ge=1)


class ReservaItemInput(BaseModel):
    item_id: uuid.UUID
    location: Literal['loja', 'deposito'] = 'loja'
    quantity: int = Field(ge=1, le=9999999, strict=True)
    unit_price_gs: Decimal = Field(ge=0, le=9999999999999.99, max_digits=15, decimal_places=2, allow_inf_nan=False)


class ReservaWrite(ReservaCommand):
    pdv_cliente_id: uuid.UUID
    items: list[ReservaItemInput] = Field(min_length=1, max_length=200)
    usd_rate_gs: Decimal = Field(gt=0, le=1000000, max_digits=12, decimal_places=4, allow_inf_nan=False)
    desconto_gs: Decimal = Field(default=Decimal('0'), ge=0, le=9999999999999.99, max_digits=15, decimal_places=2, allow_inf_nan=False)
    notas: Optional[str] = Field(default=None, max_length=4000)


class ReservaPayment(ReservaCommand):
    payment: PdvPaymentCreate


class ReservaReason(ReservaCommand):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason')
    @classmethod
    def nonblank_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError('Informe o motivo com pelo menos três caracteres.')
        return value.strip()


class ReservaCheckout(ReservaCommand):
    payments: list[PdvPaymentCreate] = Field(default_factory=list, max_length=30)
    print_receipt: bool = False


class ReservaRefund(ReservaReason):
    amount_gs: Optional[Decimal] = Field(default=None, gt=0, le=9999999999999.99, max_digits=15, decimal_places=2, allow_inf_nan=False)


class ReservaReturnLine(BaseModel):
    line_id: uuid.UUID
    quantity: int = Field(ge=1, le=9999999, strict=True)


class ReservaReturn(ReservaReason):
    lines: list[ReservaReturnLine] = Field(min_length=1, max_length=200)
