from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid
from ..models.rastreamento import RastreamentoStatus


class EventoRastreio(BaseModel):
    """Modelo para um evento individual do histórico de envio"""
    data: Optional[str] = None
    local: Optional[str] = None
    situacao: Optional[str] = None
    detalhes: Optional[str] = None
    origem: Optional[str] = None
    destino: Optional[str] = None


class RastreamentoBase(BaseModel):
    """Campos base para envio"""
    codigo_rastreio: str = Field(..., min_length=1, max_length=100)
    descricao: Optional[str] = None
    destinatario: Optional[str] = Field(None, max_length=200)
    origem: Optional[str] = Field(None, max_length=200)
    destino: Optional[str] = Field(None, max_length=200)
    pedido_id: Optional[uuid.UUID] = None


class RastreamentoCreate(RastreamentoBase):
    """Schema para criação de envio"""
    pass


class RastreamentoUpdate(BaseModel):
    """Schema para atualização de envio"""
    codigo_rastreio: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[RastreamentoStatus] = None
    servico_provedor: Optional[str] = Field(None, max_length=100)
    descricao: Optional[str] = None
    destinatario: Optional[str] = Field(None, max_length=200)
    origem: Optional[str] = Field(None, max_length=200)
    destino: Optional[str] = Field(None, max_length=200)
    historico_eventos: Optional[List[Dict[str, Any]]] = None
    pedido_id: Optional[uuid.UUID] = None
    ativo: Optional[bool] = None


class RastreamentoResponse(RastreamentoBase):
    """Schema para resposta de envio"""
    id: uuid.UUID
    status: RastreamentoStatus
    servico_provedor: Optional[str] = None
    ultima_atualizacao: Optional[datetime] = None
    historico_eventos: List[Dict[str, Any]] = Field(default_factory=list)
    data_criacao: date
    ativo: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    
    class Config:
        from_attributes = True


class RastreamentoComPedido(RastreamentoResponse):
    """Schema para envio com dados do pedido"""
    numero_pedido: Optional[str] = None
    cliente_nome_pedido: Optional[str] = None
    cliente_telefone: Optional[str] = None
    endereco_cidade: Optional[str] = None
    endereco_uf: Optional[str] = None


class RastreamentoResumo(BaseModel):
    """Schema para resumo de envios na dashboard"""
    total_rastreamentos: int
    em_transito: int
    entregues: int
    pendentes: int
    com_erro: int
    rastreamentos_recentes: List[RastreamentoResponse]