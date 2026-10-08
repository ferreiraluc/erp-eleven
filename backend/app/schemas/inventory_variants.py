from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from .inventory import ItemResponse


class VariantSummary(BaseModel):
    id: UUID
    name: str
    sku_internal: str
    size: str | None
    color: str | None
    barcode: str | None
    is_active: bool

    model_config = {'from_attributes': True}


class VariantContext(BaseModel):
    source: ItemResponse
    source_version: str
    model_name: str
    existing: list[VariantSummary]


class VariantCreateRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    sizes: list[str] = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=2, max_length=140)
    base_barcode: str | None = Field(default=None, max_length=140)
    source_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    initial_stock: int = Field(default=0, ge=0, le=1_000_000, strict=True)
    stock_location: Literal['loja', 'deposito'] = 'loja'
    confirm: Literal[True]

    @field_validator('sizes')
    @classmethod
    def valid_sizes(cls, sizes):
        values = list(dict.fromkeys(' '.join(s.split()).upper() for s in sizes))
        if any(not s or len(s) > 50 for s in values):
            raise ValueError('Informe tamanhos de 1 a 50 caracteres.')
        return values

    @field_validator('model_name')
    @classmethod
    def valid_name(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Informe o nome do modelo.')
        return value


class VariantCreateResponse(BaseModel):
    group_key: str | None
    created: list[VariantSummary]
    existing: list[VariantSummary]
