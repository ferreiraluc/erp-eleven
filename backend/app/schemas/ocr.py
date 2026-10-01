from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from ..services.ocr_images import MAX_ENCODED_LENGTH


class LabelParseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    image: str = Field(min_length=1, max_length=MAX_ENCODED_LENGTH)
    brand: str | None = Field(default=None, max_length=100)


class LabelExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    nome: str | None = Field(default=None, max_length=200)
    marca: str | None = Field(default=None, max_length=100)
    tamanho: str | None = Field(default=None, max_length=50)
    cor: str | None = Field(default=None, max_length=50)
    codigo_barras: str | None = Field(default=None, max_length=50)
    preco: float | None = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)
    moeda: Literal['PYG', 'BRL', 'USD', 'EUR'] | None = None
    texto_bruto: str = Field(default='', max_length=8000)
    qualidade: Literal['legivel', 'parcial', 'ilegivel'] = 'parcial'
    evidencias: dict[str, str] = Field(default_factory=dict, max_length=7)


class LabelMatch(BaseModel):
    id: str
    name: str
    sku_internal: str


class LabelParseResponse(LabelExtraction):
    avisos: list[str] = Field(default_factory=list)
    requires_review: Literal[True] = True
    matches: list[LabelMatch] = Field(default_factory=list)
    matches_total: int = 0


class TemplateSaveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    brand: str = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=1500)
    sample_image: str = Field(min_length=1, max_length=MAX_ENCODED_LENGTH)
    parsed_name: str | None = Field(default=None, max_length=200)
    parsed_size: str | None = Field(default=None, max_length=50)
    parsed_color: str | None = Field(default=None, max_length=50)
    parsed_barcode: str | None = Field(default=None, max_length=50)
    parsed_price: str | None = Field(default=None, max_length=30)
    parsed_currency: Literal['PYG', 'BRL', 'USD', 'EUR'] | None = None
