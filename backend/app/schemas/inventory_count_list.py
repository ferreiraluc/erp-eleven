"""Bounded, signed stock snapshots for a paper count; never an inventory mutation."""
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_ITEMS = 5000


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_ids: list[UUID] = Field(min_length=1, max_length=MAX_ITEMS)


class CountLine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    color: str | None = Field(default=None, max_length=50)
    size: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=100)
    stock_loja: int | None = Field(default=None, ge=-2147483648, le=2147483647, strict=True)
    stock_deposito: int | None = Field(default=None, ge=-2147483648, le=2147483647, strict=True)


class CountTotals(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: int = Field(ge=1, le=MAX_ITEMS, strict=True)
    stock_loja: int = Field(strict=True)
    stock_deposito: int = Field(strict=True)
    unknown_loja: int = Field(ge=0, le=MAX_ITEMS, strict=True)
    unknown_deposito: int = Field(ge=0, le=MAX_ITEMS, strict=True)


class CountSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    user_id: UUID
    created_at: AwareDatetime
    items: list[CountLine] = Field(min_length=1, max_length=MAX_ITEMS)
    totals: CountTotals

    @model_validator(mode='after')
    def coherent_totals(self):
        if len({row.id for row in self.items}) != len(self.items):
            raise ValueError('A lista não pode repetir o mesmo produto.')
        expected = {'items': len(self.items)}
        for field, unknown in [('stock_loja', 'unknown_loja'), ('stock_deposito', 'unknown_deposito')]:
            expected[field] = sum(getattr(row, field) for row in self.items if getattr(row, field) is not None)
            expected[unknown] = sum(getattr(row, field) is None for row in self.items)
        if self.totals.model_dump() != expected:
            raise ValueError('Os totais não correspondem aos produtos desta lista.')
        return self


class SignedList(BaseModel):
    model_config = ConfigDict(extra='forbid')
    snapshot: CountSnapshot
    signature: str = Field(pattern=r'^[0-9a-f]{64}$')


class PrintList(SignedList):
    device_id: UUID
    request_key: UUID
    confirm: Literal[True]

    @field_validator('confirm', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('Confirme o envio à impressora antes de continuar.')
        return value
