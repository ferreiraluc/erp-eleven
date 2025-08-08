from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models.vendedor import Vendedor
from ...models.usuario import Usuario
from ...schemas.vendedor import VendedorCreate, VendedorResponse
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid

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