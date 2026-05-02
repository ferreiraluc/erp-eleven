from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid
from ..models.pedido import PedidoStatus
from .tag_status import TagStatusSimple
from .cliente import ClienteSimple

class PedidoBase(BaseModel):
    descricao: str
    valor_total: Decimal
    cliente_nome: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    endereco_entrega: Optional[str] = None
    status: Optional[PedidoStatus] = PedidoStatus.PENDENTE
    codigo_rastreio: Optional[str] = None
    cliente_id: Optional[uuid.UUID] = None

class PedidoCreate(PedidoBase):
    created_by: Optional[uuid.UUID] = None
    tag_ids: Optional[List[uuid.UUID]] = []

class PedidoUpdate(BaseModel):
    descricao: Optional[str] = None
    valor_total: Optional[Decimal] = None
    cliente_nome: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    endereco_entrega: Optional[str] = None
    status: Optional[PedidoStatus] = None
    codigo_rastreio: Optional[str] = None
    tag_ids: Optional[List[uuid.UUID]] = None
    cliente_id: Optional[uuid.UUID] = None

class PedidoResponse(PedidoBase):
    id: uuid.UUID
    numero_pedido: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    tags: List[TagStatusSimple] = []
    cliente: Optional[ClienteSimple] = None

    class Config:
        from_attributes = True