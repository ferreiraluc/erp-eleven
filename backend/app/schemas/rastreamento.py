from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid
from ..models.rastreamento import RastreamentoStatus


class EventoRastreio(BaseModel):
    """Modelo para um evento individual do histórico de rastreamento"""
    data: Optional[str] = None
    local: Optional[str] = None
    situacao: Optional[str] = None
    detalhes: Optional[str] = None
    origem: Optional[str] = None
    destino: Optional[str] = None


class RastreamentoBase(BaseModel):
    """Campos base para rastreamento"""
    codigo_rastreio: str = Field(..., min_length=1, max_length=100)
    descricao: Optional[str] = None
    destinatario: Optional[str] = Field(None, max_length=200)
    origem: Optional[str] = Field(None, max_length=200)
    destino: Optional[str] = Field(None, max_length=200)
    pedido_id: Optional[uuid.UUID] = None


class RastreamentoCreate(RastreamentoBase):
    """Schema para criação de rastreamento"""
    pass


class RastreamentoUpdate(BaseModel):
    """Schema para atualização de rastreamento"""
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
    """Schema para resposta de rastreamento"""
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
    """Schema para rastreamento com dados do pedido"""
    numero_pedido: Optional[str] = None
    cliente_nome: Optional[str] = None
    cliente_telefone: Optional[str] = None
    endereco_cidade: Optional[str] = None
    endereco_uf: Optional[str] = None


class RastreamentoConsulta(BaseModel):
    """Schema para consulta de rastreamento via API externa"""
    codigo: str = Field(..., description="Código de rastreamento")
    servico_id: Optional[str] = Field("0001", description="ID do serviço (0001-0007)")


class RastreamentoConsultaResponse(BaseModel):
    """Schema para resposta da consulta de rastreamento"""
    codigo: str
    status: str
    service_provider: str
    data: List[EventoRastreio]
    sucesso: bool = True
    erro: Optional[str] = None


class RastreamentoResumo(BaseModel):
    """Schema para resumo de rastreamentos na dashboard"""
    total_rastreamentos: int
    em_transito: int
    entregues: int
    pendentes: int
    com_erro: int
    rastreamentos_recentes: List[RastreamentoResponse]