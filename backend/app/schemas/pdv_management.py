"""Explicit, reviewed commands for owner-only sale corrections."""
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from .pdv import PdvSaleCreate

class ReturnLine(BaseModel):
    line_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    restock: bool = True

class SaleCommand(BaseModel):
    operation: Literal['edit', 'return', 'cancel', 'delete']
    reason: str = Field(min_length=5, max_length=1000)
    edit: PdvSaleCreate | None = None
    lines: list[ReturnLine] = Field(default_factory=list, max_length=200)
    restock: bool = True

    @field_validator('reason')
    @classmethod
    def reason_required(cls, value):
        if len(value.strip()) < 5: raise ValueError('Informe o motivo da alteração.')
        return value.strip()

    @model_validator(mode='after')
    def operation_payload(self):
        if self.operation == 'edit' and self.edit is None: raise ValueError('Envie a venda corrigida.')
        if self.operation != 'edit' and self.edit is not None: raise ValueError('Dados de edição não pertencem a esta operação.')
        if self.operation == 'return' and not self.lines: raise ValueError('Selecione as peças devolvidas.')
        if self.operation != 'return' and self.lines: raise ValueError('Seleção parcial não pertence a esta operação.')
        if len({r.line_id for r in self.lines}) != len(self.lines): raise ValueError('Uma peça foi informada duas vezes.')
        return self

class SaleCommit(BaseModel):
    command: SaleCommand
    plan_token: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_id: UUID
    confirm: Literal[True]
