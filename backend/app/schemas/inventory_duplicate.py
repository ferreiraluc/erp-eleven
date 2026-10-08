from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from .inventory import ItemBase


class DuplicateItemData(ItemBase):
    model_config = {'extra': 'forbid'}
    name: str = Field(min_length=2, max_length=200)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    brand: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    unit: str = Field(default='un', min_length=1, max_length=20)
    location: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=200)
    currency: Literal['PYG', 'BRL', 'USD', 'EUR'] = 'PYG'
    cost_currency: Literal['PYG', 'BRL', 'USD', 'EUR'] = 'BRL'
    sale_currency: Literal['PYG', 'BRL', 'USD', 'EUR'] = 'USD'
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal('9999999999.99'), decimal_places=2)
    sale_price: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal('9999999999.99'), decimal_places=2)
    min_stock: int = Field(default=0, ge=0, le=2147483647, strict=True)
    max_stock: int = Field(default=0, ge=0, le=2147483647, strict=True)
    is_active: bool = True
    group_key: None = None  # Only the source-based grouping choice is accepted.

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Informe o nome do produto.')
        return value



class DuplicateItemRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    request_id: UUID
    source_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    item: DuplicateItemData
    keep_group: bool = True
    initial_stock: int = Field(default=0, ge=0, le=1_000_000, strict=True)
    stock_location: Literal['loja', 'deposito'] = 'loja'
    confirm: Literal[True]
