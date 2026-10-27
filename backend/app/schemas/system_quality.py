"""Owner-controlled schedule; hard query/AI budgets cannot be changed by API input."""
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class QualityConfigUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    enabled: StrictBool
    ai_enabled: StrictBool
    local_time: str = Field(default='08:30', min_length=5, max_length=5)

    @field_validator('local_time')
    @classmethod
    def valid_local_time(cls, value):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError('Informe um horário de Brasília válido, como 08:30.')
        return value


class QualityScanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
