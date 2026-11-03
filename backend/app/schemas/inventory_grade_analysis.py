"""Explicit, bounded grade advice and separately confirmed membership writes."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GradeSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_ids: list[UUID] = Field(min_length=2, max_length=24)

    @model_validator(mode='after')
    def distinct_items(self):
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError('Selecione produtos distintos.')
        return self


class GradeAnalysisRequest(GradeSelection):
    include_photos: bool = True


class GradeProductSummary(BaseModel):
    id: UUID
    name: str
    category: str | None
    brand: str | None
    size: str | None
    color: str | None
    group_key: str | None
    is_active: bool
    version: str
    has_image: bool


class GradeAiSuggestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_ids: list[UUID] = Field(min_length=2, max_length=24)
    confidence: Literal['high', 'medium', 'low']
    evidence: list[str] = Field(min_length=1, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def bounded_strings(self):
        if any(not value.strip() or len(value) > 500 for value in [*self.evidence, *self.warnings]):
            raise ValueError('Evidências inválidas.')
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError('Produtos repetidos na sugestão.')
        return self


class GradeModelAdvice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    suggestions: list[GradeAiSuggestion] = Field(max_length=12)


class GradeAnalysisResponse(GradeModelAdvice):
    provider: Literal['deepseek', 'anthropic']
    model: str
    analyzed_count: int
    photos_analyzed: int
    products: list[GradeProductSummary]
    warnings: list[str]
    advisory_only: Literal[True] = True


class GradeLinkPreviewRequest(GradeSelection):
    target_group_key: str | None = Field(default=None, min_length=1, max_length=100)
    new_group_name: str | None = Field(default=None, min_length=1, max_length=100)
    expected_versions: dict[UUID, str] | None = Field(default=None, max_length=24)

    @model_validator(mode='after')
    def target(self):
        self.target_group_key = self.target_group_key.strip() if self.target_group_key else None
        self.new_group_name = self.new_group_name.strip() if self.new_group_name else None
        if bool(self.target_group_key) == bool(self.new_group_name):
            raise ValueError('Escolha uma grade existente ou informe um nome para a nova grade.')
        if self.expected_versions is not None and not set(self.item_ids).issubset(self.expected_versions):
            raise ValueError('Confira a versão de todos os produtos selecionados.')
        if any(len(value) != 64 or any(c not in '0123456789abcdef' for c in value)
               for value in (self.expected_versions or {}).values()):
            raise ValueError('Versão de produto inválida.')
        return self


class GradeSourceSummary(BaseModel):
    group_key: str
    moving_count: int
    remaining_count: int


class GradeLinkPreviewResponse(BaseModel):
    preview_token: str
    expires_at: datetime
    target_group_key: str
    items: list[GradeProductSummary]
    existing_members: list[GradeProductSummary]
    source_groups: list[GradeSourceSummary]
    warnings: list[str]


class GradeLinkCommitRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_token: str = Field(min_length=20, max_length=150000)
    confirmed: Literal[True]

    @field_validator('confirmed', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('Confirme os vínculos revisados antes de aplicar.')
        return value


class GradeLinkCommitResponse(BaseModel):
    target_group_key: str
    item_ids: list[UUID]
    applied_count: int
    already_applied: bool
