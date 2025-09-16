from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from ...database import get_db
from ...models.pedido import Pedido, PedidoStatus
from ...models.pedido_tag import TagStatus
from ...models.usuario import Usuario
from ...schemas.pedido import PedidoCreate, PedidoResponse, PedidoUpdate
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid
from ...utils import generate_order_number, validate_brazilian_cep, validate_brazilian_phone
from ...services.rastreamento_sync import RastreamentoSyncService

router = APIRouter()

@router.get("/", response_model=List[PedidoResponse])
def listar_pedidos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[PedidoStatus] = Query(None),
    cidade: Optional[str] = Query(None),
    tag_id: Optional[str] = Query(None, description="Filter by tag ID"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """List orders with pagination and filters"""
    query = db.query(Pedido).options(joinedload(Pedido.tags))

    if status:
        query = query.filter(Pedido.status == status)
    if cidade:
        # Sanitize input to prevent SQL injection
        safe_cidade = cidade.replace('%', '\\%').replace('_', '\\_').replace('\\', '\\\\')
        query = query.filter(Pedido.endereco_entrega.ilike(f"%{safe_cidade}%"))
    if tag_id:
        # Filter by tag using join
        tag_uuid = validate_uuid(tag_id)
        query = query.join(Pedido.tags).filter(TagStatus.id == tag_uuid)

    pedidos = query.order_by(Pedido.created_at.desc()).offset(skip).limit(limit).all()
    return pedidos

@router.post("/", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED)
def criar_pedido(
    pedido: PedidoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Create new order"""
    # Basic validation only
    if pedido.valor_total <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order value must be greater than zero"
        )

    # Optional phone validation
    if pedido.cliente_telefone and not validate_brazilian_phone(pedido.cliente_telefone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )

    # Generate unique order number
    numero_pedido = generate_order_number(db)

    # Create order
    pedido_data = pedido.dict(exclude={"tag_ids"})
    pedido_data["numero_pedido"] = numero_pedido
    pedido_data["created_by"] = current_user.id

    db_pedido = Pedido(**pedido_data)
    db.add(db_pedido)
    db.flush()  # Get the ID without committing

    # Add tags if provided
    if pedido.tag_ids:
        tags = db.query(TagStatus).filter(TagStatus.id.in_(pedido.tag_ids), TagStatus.ativo == True).all()
        db_pedido.tags = tags

    # Sincronizar com rastreamentos se código foi fornecido
    if db_pedido.codigo_rastreio:
        RastreamentoSyncService.sincronizar_pedido_com_rastreamento(
            db, db_pedido, current_user.id
        )

    db.commit()
    db.refresh(db_pedido)
    return db_pedido

@router.get("/{pedido_id}", response_model=PedidoResponse)
def obter_pedido(
    pedido_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Get order by ID"""
    pedido_uuid = validate_uuid(pedido_id)
    pedido = db.query(Pedido).options(joinedload(Pedido.tags)).filter(Pedido.id == pedido_uuid).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    return pedido

@router.get("/numero/{numero_pedido}", response_model=PedidoResponse)
def obter_pedido_por_numero(
    numero_pedido: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Get order by order number"""
    pedido = db.query(Pedido).options(joinedload(Pedido.tags)).filter(Pedido.numero_pedido == numero_pedido).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    return pedido

@router.put("/{pedido_id}", response_model=PedidoResponse)
def atualizar_pedido(
    pedido_id: str,
    pedido_update: PedidoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Update order"""
    pedido_uuid = validate_uuid(pedido_id)
    db_pedido = db.query(Pedido).options(joinedload(Pedido.tags)).filter(Pedido.id == pedido_uuid).first()
    if not db_pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Basic validation
    update_data = pedido_update.dict(exclude_unset=True, exclude={"tag_ids"})

    if "valor_total" in update_data and update_data["valor_total"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order value must be greater than zero"
        )

    if "cliente_telefone" in update_data and update_data["cliente_telefone"] and not validate_brazilian_phone(update_data["cliente_telefone"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format"
        )

    # Update fields
    for field, value in update_data.items():
        setattr(db_pedido, field, value)

    # Update tags if provided
    if pedido_update.tag_ids is not None:
        if pedido_update.tag_ids:
            tags = db.query(TagStatus).filter(TagStatus.id.in_(pedido_update.tag_ids), TagStatus.ativo == True).all()
            db_pedido.tags = tags
        else:
            db_pedido.tags = []

    # Sincronizar com rastreamentos se código foi adicionado/alterado
    if "codigo_rastreio" in update_data and db_pedido.codigo_rastreio:
        RastreamentoSyncService.sincronizar_pedido_com_rastreamento(
            db, db_pedido, current_user.id
        )

    db.commit()
    db.refresh(db_pedido)
    return db_pedido

@router.delete("/{pedido_id}")
def excluir_pedido(
    pedido_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Delete order (admin/manager only)"""
    pedido_uuid = validate_uuid(pedido_id)
    db_pedido = db.query(Pedido).filter(Pedido.id == pedido_uuid).first()
    if not db_pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Check if order can be deleted (only pending orders)
    if db_pedido.status not in [PedidoStatus.PENDENTE, PedidoStatus.CANCELADO]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete order that is being processed or delivered"
        )
    
    db.delete(db_pedido)
    db.commit()
    return {"message": "Order deleted successfully"}

@router.get("/rastreamento/{codigo_rastreio}")
def verificar_rastreamento_existente(
    codigo_rastreio: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Verifica se existe rastreamento para o código fornecido"""
    rastreamento = RastreamentoSyncService.buscar_rastreamento_por_codigo(db, codigo_rastreio)

    if rastreamento:
        return {
            "exists": True,
            "rastreamento_id": str(rastreamento.id),
            "status": rastreamento.status.value,
            "pedido_associado": str(rastreamento.pedido_id) if rastreamento.pedido_id else None
        }

    return {"exists": False}