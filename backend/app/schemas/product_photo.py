from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from ..services.ocr_images import MAX_ENCODED_LENGTH


class PhotoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    image: str = Field(min_length=1, max_length=MAX_ENCODED_LENGTH)


class PhotoEditRequest(PhotoRequest):
    confirmed: Literal[True]


class ProductPhotoResponse(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    name: str = Field(default='', max_length=200)
    description: str = Field(default='', max_length=1000)
    category: str = Field(default='', max_length=100)
    color: str = Field(default='', max_length=50)
    brand: str = Field(default='', max_length=100)
    size: str = Field(default='', max_length=50)
    brand_evidence: str = Field(default='', max_length=200)
    size_evidence: str = Field(default='', max_length=100)
    single_product: bool = False
    requires_review: Literal[True] = True


class PhotoEditResponse(BaseModel):
    image: str
    model: str
    quality: Literal['low'] = 'low'
    requires_review: Literal[True] = True
    estimated_cost_usd: float | None = None
