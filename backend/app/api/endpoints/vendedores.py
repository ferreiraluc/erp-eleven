from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date
from ...database import get_db
from ...models.vendedor import Vendedor
from ...models.folga import Folga, TipoFolga
from ...models.usuario import Usuario
from ...schemas.vendedor import VendedorCreate, VendedorResponse
from ...schemas.folga import (
    FolgaCreate, FolgaUpdate, FolgaResponse, FolgaComVendedor,
    EstatisticasFolgas, ResumoMensal
)
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid
import uuid

router = APIRouter()

@router.get("/", response_model=List[VendedorResponse])
def listar_vendedores(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    ativo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """List vendors with pagination and filters"""
    query = db.query(Vendedor)
    
    if ativo is not None:
        query = query.filter(Vendedor.ativo == ativo)
    
    vendedores = query.offset(skip).limit(limit).all()
    return vendedores

@router.post("/", response_model=VendedorResponse, status_code=status.HTTP_201_CREATED)
def criar_vendedor(
    vendedor: VendedorCreate, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Create new vendor (admin/manager only)"""
    # Validate usuario_id if provided
    if vendedor.usuario_id:
        usuario = db.query(Usuario).filter(Usuario.id == vendedor.usuario_id).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID not found"
            )
    
    db_vendedor = Vendedor(**vendedor.dict())
    db.add(db_vendedor)
    db.commit()
    db.refresh(db_vendedor)
    return db_vendedor

@router.get("/{vendedor_id}", response_model=VendedorResponse)
def obter_vendedor(
    vendedor_id: str, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Get vendor by ID"""
    vendedor_uuid = validate_uuid(vendedor_id)
    vendedor = db.query(Vendedor).filter(Vendedor.id == vendedor_uuid).first()
    if not vendedor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Vendor not found"
        )
    return vendedor

@router.put("/{vendedor_id}", response_model=VendedorResponse)
def atualizar_vendedor(
    vendedor_id: str,
    vendedor_update: VendedorCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Update vendor (admin/manager only)"""
    vendedor_uuid = validate_uuid(vendedor_id)
    db_vendedor = db.query(Vendedor).filter(Vendedor.id == vendedor_uuid).first()
    if not db_vendedor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    # Update fields
    for field, value in vendedor_update.dict(exclude_unset=True).items():
        setattr(db_vendedor, field, value)
    
    db.commit()
    db.refresh(db_vendedor)
    return db_vendedor

@router.delete("/{vendedor_id}")
def excluir_vendedor(
    vendedor_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN"]))
):
    """Soft delete vendor (admin only)"""
    vendedor_uuid = validate_uuid(vendedor_id)
    db_vendedor = db.query(Vendedor).filter(Vendedor.id == vendedor_uuid).first()
    if not db_vendedor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    # Soft delete
    db_vendedor.ativo = False
    db.commit()
    
    return {"message": "Vendor deactivated successfully"}


# Endpoints de Folgas
@router.get("/{vendedor_id}/folgas", response_model=List[FolgaResponse])
def listar_folgas_vendedor(
    vendedor_id: str,
    ano: Optional[int] = Query(None),
    mes: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Listar folgas de um vendedor específico"""
    vendedor_uuid = validate_uuid(vendedor_id)
    
    # Verificar se vendedor existe
    vendedor = db.query(Vendedor).filter(Vendedor.id == vendedor_uuid).first()
    if not vendedor:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    
    query = db.query(Folga).filter(
        Folga.vendedor_id == vendedor_uuid,
        Folga.ativo == True
    )
    
    if ano:
        query = query.filter(func.extract('year', Folga.data) == ano)
    if mes:
        query = query.filter(func.extract('month', Folga.data) == mes)
    
    return query.order_by(Folga.data.desc()).all()

@router.post("/{vendedor_id}/folgas", response_model=FolgaResponse)
def criar_folga(
    vendedor_id: str,
    folga: FolgaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Criar nova folga para um vendedor"""
    vendedor_uuid = validate_uuid(vendedor_id)
    
    # Verificar se vendedor existe
    vendedor = db.query(Vendedor).filter(Vendedor.id == vendedor_uuid).first()
    if not vendedor:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    
    # Verificar se já existe folga na data
    existing_folga = db.query(Folga).filter(
        Folga.vendedor_id == vendedor_uuid,
        Folga.data == folga.data,
        Folga.ativo == True
    ).first()
    
    if existing_folga:
        raise HTTPException(status_code=400, detail="Já existe folga cadastrada para esta data")
    
    folga.vendedor_id = vendedor_uuid
    db_folga = Folga(**folga.model_dump())
    db.add(db_folga)
    db.commit()
    db.refresh(db_folga)
    return db_folga

@router.put("/folgas/{folga_id}", response_model=FolgaResponse)
def atualizar_folga(
    folga_id: str,
    folga_update: FolgaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Atualizar folga existente"""
    folga_uuid = validate_uuid(folga_id)
    
    folga = db.query(Folga).filter(Folga.id == folga_uuid).first()
    if not folga:
        raise HTTPException(status_code=404, detail="Folga não encontrada")
    
    update_data = folga_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(folga, field, value)
    
    db.commit()
    db.refresh(folga)
    return folga

@router.delete("/folgas/{folga_id}")
def remover_folga(
    folga_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Remover folga (soft delete)"""
    folga_uuid = validate_uuid(folga_id)
    
    folga = db.query(Folga).filter(Folga.id == folga_uuid).first()
    if not folga:
        raise HTTPException(status_code=404, detail="Folga não encontrada")
    
    folga.ativo = False
    db.commit()
    return {"message": "Folga removida com sucesso"}

# Endpoints para estatísticas e relatórios
@router.get("/folgas/calendario", response_model=List[FolgaComVendedor])
def obter_calendario_folgas(
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Retorna todas as folgas de todos os vendedores para um mês específico"""
    folgas = db.query(
        Folga.id,
        Folga.vendedor_id,
        Folga.data,
        Folga.tipo,
        Folga.periodo,
        Folga.motivo,
        Folga.aprovado,
        Folga.aprovado_por,
        Folga.ativo,
        Folga.created_at,
        Folga.updated_at,
        Vendedor.nome.label("vendedor_nome"),
        Vendedor.cor_calendario.label("vendedor_cor")
    ).join(
        Vendedor, Folga.vendedor_id == Vendedor.id
    ).filter(
        Folga.ativo == True,
        Vendedor.ativo == True,
        func.extract('year', Folga.data) == ano,
        func.extract('month', Folga.data) == mes
    ).order_by(Folga.data).all()
    
    return [
        FolgaComVendedor(
            id=folga.id,
            vendedor_id=folga.vendedor_id,
            data=folga.data,
            tipo=folga.tipo,
            periodo=folga.periodo,
            motivo=folga.motivo,
            aprovado=folga.aprovado,
            aprovado_por=folga.aprovado_por,
            ativo=folga.ativo,
            created_at=folga.created_at,
            updated_at=folga.updated_at,
            vendedor_nome=folga.vendedor_nome,
            vendedor_cor=folga.vendedor_cor
        )
        for folga in folgas
    ]

@router.get("/estatisticas/resumo", response_model=ResumoMensal)
def obter_estatisticas_resumo(
    ano: int = Query(...),
    mes: int = Query(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Retorna estatísticas resumidas de todos os vendedores para um mês"""
    vendedores = db.query(Vendedor).filter(Vendedor.ativo == True).all()
    
    # Calcular dias úteis do mês (aproximação simples)
    import calendar
    total_dias = calendar.monthrange(ano, mes)[1]
    total_dias_uteis = total_dias - (total_dias // 7) * 2  # Aproximação: remove fins de semana
    
    estatisticas = []
    
    for vendedor in vendedores:
        # Contar folgas do vendedor no mês
        folgas_mes = db.query(Folga).filter(
            Folga.vendedor_id == vendedor.id,
            Folga.ativo == True,
            func.extract('year', Folga.data) == ano,
            func.extract('month', Folga.data) == mes
        ).all()
        
        total_folgas = len(folgas_mes)
        folgas_aprovadas = len([f for f in folgas_mes if f.aprovado])
        folgas_pendentes = total_folgas - folgas_aprovadas
        dias_trabalhados = total_dias_uteis - folgas_aprovadas
        
        estatisticas.append(EstatisticasFolgas(
            vendedor_id=vendedor.id,
            vendedor_nome=vendedor.nome,
            vendedor_cor=vendedor.cor_calendario,
            total_folgas=total_folgas,
            folgas_aprovadas=folgas_aprovadas,
            folgas_pendentes=folgas_pendentes,
            dias_trabalhados=max(0, dias_trabalhados),
            ultimo_periodo=folgas_mes[-5:] if folgas_mes else []
        ))
    
    return ResumoMensal(
        mes=mes,
        ano=ano,
        vendedores=estatisticas,
        total_dias_uteis=total_dias_uteis
    )