from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
import uuid

class FuncionarioBase(BaseModel):
    nome: str
    cpf: Optional[str] = None
    cargo: Optional[str] = None
    salario: Optional[Decimal] = None
    data_admissao: Optional[date] = None
    data_demissao: Optional[date] = None
    horarios: Optional[Dict[str, Any]] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None
    ativo: Optional[bool] = True

class FuncionarioCreate(FuncionarioBase):
    usuario_id: Optional[uuid.UUID] = None

class FuncionarioUpdate(BaseModel):
    nome: Optional[str] = None
    cpf: Optional[str] = None
    cargo: Optional[str] = None
    salario: Optional[Decimal] = None
    data_admissao: Optional[date] = None
    data_demissao: Optional[date] = None
    horarios: Optional[Dict[str, Any]] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None
    ativo: Optional[bool] = None

class FuncionarioResponse(FuncionarioBase):
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True