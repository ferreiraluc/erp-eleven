import uuid
from pydantic import BaseModel, Field


class ArchiveOrders(BaseModel):
    request_id: uuid.UUID
    confirm: bool
    plan_token: str = Field(min_length=64, max_length=64, pattern=r'^[a-f0-9]{64}$')
    expected_count: int = Field(ge=0)
