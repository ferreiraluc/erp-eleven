from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid
from ..models.pedido import PedidoStatus, TransportadoraTipo

class PedidoBase(BaseModel):
    cliente_nome: str
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    endereco_rua: str
    endereco_numero: Optional[str] = None
    endereco_complemento: Optional[str] = None
    endereco_bairro: Optional[str] = None
    endereco_cidade: str
    endereco_uf: str
    endereco_cep: str
    transportadora: TransportadoraTipo
    codigo_rastreio: Optional[str] = None
    valor_frete: Optional[Decimal] = None
    peso_kg: Optional[Decimal] = None
    status: Optional[PedidoStatus] = PedidoStatus.PENDENTE
    data_pedido: Optional[date] = None
    data_envio: Optional[date] = None
    data_entrega: Optional[date] = None
    observacoes: Optional[str] = None
    instrucoes_entrega: Optional[str] = None

class PedidoCreate(PedidoBase):
    created_by: Optional[uuid.UUID] = None

class PedidoUpdate(BaseModel):
    cliente_nome: Optional[str] = None
    cliente_telefone: Optional[str] = None
    cliente_email: Optional[str] = None
    endereco_rua: Optional[str] = None
    endereco_numero: Optional[str] = None
    endereco_complemento: Optional[str] = None
    endereco_bairro: Optional[str] = None
    endereco_cidade: Optional[str] = None
    endereco_uf: Optional[str] = None
    endereco_cep: Optional[str] = None
    transportadora: Optional[TransportadoraTipo] = None
    codigo_rastreio: Optional[str] = None
    valor_frete: Optional[Decimal] = None
    peso_kg: Optional[Decimal] = None
    status: Optional[PedidoStatus] = None
    data_envio: Optional[date] = None
    data_entrega: Optional[date] = None
    observacoes: Optional[str] = None
    instrucoes_entrega: Optional[str] = None

class PedidoResponse(PedidoBase):
    id: uuid.UUID
    numero_pedido: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True