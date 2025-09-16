from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid
from ..models.pedido import PedidoStatus
from .tag_status import TagStatusSimple

class PedidoBase(BaseModel):
    descricao: str  # Descrição das peças/produtos
    valor_total: Decimal  # Valor total do pedido
    cliente_nome: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    endereco_entrega: Optional[str] = None  # Endereço livre
    status: Optional[PedidoStatus] = PedidoStatus.PENDENTE
    codigo_rastreio: Optional[str] = None

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

class PedidoResponse(PedidoBase):
    id: uuid.UUID
    numero_pedido: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    tags: List[TagStatusSimple] = []

    class Config:
        from_attributes = True