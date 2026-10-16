from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
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


class VariantCombination(BaseModel):
    model_config = {'extra': 'forbid'}
    size: str = Field(max_length=50)
    color: str | None = Field(default=None, max_length=50)
    quantity: int = Field(default=0, ge=0, le=1_000_000, strict=True)

    @field_validator('size')
    @classmethod
    def clean_size(cls, value):
        from ..services.inventory_taxonomy_v2 import canonical_size
        return canonical_size(' '.join(value.split()).upper())


class VariantCreateRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    sizes: list[str] = Field(default_factory=list, max_length=50)
    variants: list[VariantCombination] | None = Field(default=None, min_length=1, max_length=250)
    model_name: str = Field(min_length=2, max_length=140)
    base_barcode: str | None = Field(default=None, max_length=140)
    source_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    initial_stock: int = Field(default=0, ge=0, le=1_000_000, strict=True)
    stock_location: Literal['loja', 'deposito'] = 'loja'
    confirm: Literal[True]

    @model_validator(mode='after')
    def one_selection(self):
        from ..services.inventory_taxonomy import key
        if not self.sizes and not self.variants:
            raise ValueError('Informe tamanhos ou variações de cor e tamanho.')
        if self.sizes and self.variants:
            raise ValueError('Envie somente uma seleção de variações.')
        if self.variants:
            keys = [(v.size.casefold(), key(v.color, 'color')) for v in self.variants]
            if len(keys) != len(set(keys)):
                raise ValueError('Há combinações de tamanho e cor repetidas.')
        return self

    @field_validator('sizes')
    @classmethod
    def valid_sizes(cls, sizes):
        from ..services.inventory_taxonomy_v2 import canonical_size
        values = list(dict.fromkeys(canonical_size(' '.join(s.split()).upper()) for s in sizes))
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
