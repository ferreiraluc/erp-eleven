from typing import Literal
from pydantic import BaseModel, Field


class ItemDeletionConfirmation(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    plan_token: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm: Literal[True]
