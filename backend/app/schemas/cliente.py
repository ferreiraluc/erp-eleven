from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class ClienteBase(BaseModel):
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    ativo: Optional[bool] = True


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    ativo: Optional[bool] = None


class ClienteResponse(ClienteBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerActivity(BaseModel):
    purchase_count: int = 0
    order_count: int = 0
    shipment_count: int = 0
    print_count: int = 0
    submitted_print_count: int = 0
    pending_print_count: int = 0
    uncertain_print_count: int = 0
    last_purchase_at: Optional[datetime] = None
    last_print_at: Optional[datetime] = None
    own_sales_only: bool = False


class ClienteDirectoryEntry(ClienteResponse):
    activity: CustomerActivity


class ClientePage(BaseModel):
    items: list[ClienteDirectoryEntry]
    total: int
    page: int
    page_size: int


class ClienteSimple(BaseModel):
    id: uuid.UUID
    nome: str
    telefone: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None

    class Config:
        from_attributes = True
