from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from ...database import get_db
from ...models.pedido import Pedido, PedidoStatus
from ...models.pedido_tag import TagStatus
from ...models.cliente import Cliente
from ...models.usuario import Usuario
from ...models.pedido_anexo import PedidoAnexo
from ...schemas.pedido import PedidoCreate, PedidoResponse, PedidoUpdate
from ...schemas.pedido_anexo import PedidoAnexoCreate, PedidoAnexoResponse
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid
from ...utils import generate_order_number, validate_brazilian_cep, validate_brazilian_phone
from ...services.rastreamento_sync import RastreamentoSyncService

MAX_ANEXOS_POR_PEDIDO = 10
MAX_TAMANHO_BYTES = 5 * 1024 * 1024  # 5 MB
TIPOS_PERMITIDOS = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _sync_cliente_fields(db_pedido: Pedido, cliente: Cliente) -> None:
    """Copia dados do Cliente para os campos inline do Pedido."""
    db_pedido.cliente_nome = cliente.nome
    db_pedido.cliente_telefone = cliente.telefone
    db_pedido.cliente_email = cliente.email
    if cliente.endereco:
        db_pedido.endereco_entrega = cliente.endereco

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

    # Se cliente_id fornecido, valida e sincroniza campos
    cliente_obj = None
    if pedido.cliente_id:
        cliente_obj = db.query(Cliente).filter(Cliente.id == pedido.cliente_id, Cliente.ativo == True).first()
        if not cliente_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")

    # Create order
    pedido_data = pedido.dict(exclude={"tag_ids"})
    pedido_data["numero_pedido"] = numero_pedido
    pedido_data["created_by"] = current_user.id

    db_pedido = Pedido(**pedido_data)

    if cliente_obj:
        _sync_cliente_fields(db_pedido, cliente_obj)

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

    # Se cliente_id fornecido, valida e sincroniza campos
    if pedido_update.cliente_id is not None:
        cliente_obj = db.query(Cliente).filter(Cliente.id == pedido_update.cliente_id, Cliente.ativo == True).first()
        if not cliente_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
        _sync_cliente_fields(db_pedido, cliente_obj)

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

@router.get("/{pedido_id}/anexos", response_model=List[PedidoAnexoResponse])
def listar_anexos(
    pedido_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """List all attachments for a pedido"""
    pedido_uuid = validate_uuid(pedido_id)
    pedido = db.query(Pedido).filter(Pedido.id == pedido_uuid).first()
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return db.query(PedidoAnexo).filter(PedidoAnexo.pedido_id == pedido_uuid).order_by(PedidoAnexo.created_at).all()


@router.post("/{pedido_id}/anexos", response_model=PedidoAnexoResponse, status_code=status.HTTP_201_CREATED)
def adicionar_anexo(
    pedido_id: str,
    anexo: PedidoAnexoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Upload an image attachment to a pedido (base64-encoded)"""
    pedido_uuid = validate_uuid(pedido_id)
    pedido = db.query(Pedido).filter(Pedido.id == pedido_uuid).first()
    if not pedido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if anexo.tipo_arquivo not in TIPOS_PERMITIDOS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de arquivo não permitido. Use JPEG, PNG, GIF ou WebP.")

    if anexo.tamanho > MAX_TAMANHO_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Arquivo muito grande. Máximo permitido: 5 MB.")

    contagem = db.query(PedidoAnexo).filter(PedidoAnexo.pedido_id == pedido_uuid).count()
    if contagem >= MAX_ANEXOS_POR_PEDIDO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Limite de {MAX_ANEXOS_POR_PEDIDO} anexos por pedido atingido.")

    db_anexo = PedidoAnexo(
        pedido_id=pedido_uuid,
        nome_arquivo=anexo.nome_arquivo,
        tipo_arquivo=anexo.tipo_arquivo,
        tamanho=anexo.tamanho,
        dados=anexo.dados,
        created_by=current_user.id,
    )
    db.add(db_anexo)
    pedido.anexos_count = (pedido.anexos_count or 0) + 1
    db.commit()
    db.refresh(db_anexo)
    return db_anexo


@router.delete("/{pedido_id}/anexos/{anexo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_anexo(
    pedido_id: str,
    anexo_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Delete an attachment from a pedido"""
    pedido_uuid = validate_uuid(pedido_id)
    anexo_uuid = validate_uuid(anexo_id)
    db_anexo = db.query(PedidoAnexo).filter(
        PedidoAnexo.id == anexo_uuid,
        PedidoAnexo.pedido_id == pedido_uuid,
    ).first()
    if not db_anexo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anexo não encontrado.")
    pedido = db.query(Pedido).filter(Pedido.id == pedido_uuid).first()
    if pedido and pedido.anexos_count > 0:
        pedido.anexos_count -= 1
    db.delete(db_anexo)
    db.commit()


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