from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from ..models.folga import TipoFolga
import uuid

class FolgaBase(BaseModel):
    data: date
    tipo: TipoFolga = TipoFolga.FOLGA
    periodo: str = "COMPLETO"
    motivo: Optional[str] = None

class FolgaCreate(FolgaBase):
    vendedor_id: uuid.UUID

class FolgaUpdate(BaseModel):
    data: Optional[date] = None
    tipo: Optional[TipoFolga] = None
    periodo: Optional[str] = None
    motivo: Optional[str] = None
    aprovado: Optional[bool] = None

class FolgaResponse(FolgaBase):
    id: uuid.UUID
    vendedor_id: uuid.UUID
    aprovado: bool
    aprovado_por: Optional[uuid.UUID] = None
    ativo: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class FolgaComVendedor(FolgaResponse):
    vendedor_nome: str
    vendedor_cor: str

class EstatisticasFolgas(BaseModel):
    vendedor_id: uuid.UUID
    vendedor_nome: str
    vendedor_cor: str
    total_folgas: int
    folgas_aprovadas: int
    folgas_pendentes: int
    dias_trabalhados: int
    ultimo_periodo: List[FolgaResponse] = []

class ResumoMensal(BaseModel):
    mes: int
    ano: int
    vendedores: List[EstatisticasFolgas]
    total_dias_uteis: int