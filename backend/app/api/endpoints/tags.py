from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models.pedido_tag import TagStatus
from ...models.usuario import Usuario
from ...schemas.tag_status import TagStatusCreate, TagStatusResponse, TagStatusUpdate
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid

router = APIRouter()

@router.get("/", response_model=List[TagStatusResponse])
def listar_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    ativo: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """List status tags with pagination"""
    query = db.query(TagStatus).filter(TagStatus.ativo == ativo)
    tags = query.order_by(TagStatus.ordem, TagStatus.nome).offset(skip).limit(limit).all()
    return tags

@router.post("/", response_model=TagStatusResponse, status_code=status.HTTP_201_CREATED)
def criar_tag(
    tag: TagStatusCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Create new status tag (admin/manager only)"""
    # Check if tag name already exists
    existing_tag = db.query(TagStatus).filter(TagStatus.nome == tag.nome, TagStatus.ativo == True).first()
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists"
        )

    # Validate color format (hex color)
    if not tag.cor.startswith('#') or len(tag.cor) != 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid color format. Use hex format like #FF0000"
        )

    # Create tag
    tag_data = tag.dict()
    tag_data["created_by"] = current_user.id

    db_tag = TagStatus(**tag_data)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

@router.get("/{tag_id}", response_model=TagStatusResponse)
def obter_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user)
):
    """Get tag by ID"""
    tag_uuid = validate_uuid(tag_id)
    tag = db.query(TagStatus).filter(TagStatus.id == tag_uuid, TagStatus.ativo == True).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    return tag

@router.put("/{tag_id}", response_model=TagStatusResponse)
def atualizar_tag(
    tag_id: str,
    tag_update: TagStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Update tag (admin/manager only)"""
    tag_uuid = validate_uuid(tag_id)
    db_tag = db.query(TagStatus).filter(TagStatus.id == tag_uuid).first()
    if not db_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )

    # Update fields
    update_data = tag_update.dict(exclude_unset=True)

    # Check name uniqueness if changing name
    if "nome" in update_data:
        existing_tag = db.query(TagStatus).filter(
            TagStatus.nome == update_data["nome"],
            TagStatus.ativo == True,
            TagStatus.id != tag_uuid
        ).first()
        if existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tag with this name already exists"
            )

    # Validate color format if changing color
    if "cor" in update_data:
        if not update_data["cor"].startswith('#') or len(update_data["cor"]) != 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid color format. Use hex format like #FF0000"
            )

    for field, value in update_data.items():
        setattr(db_tag, field, value)

    db.commit()
    db.refresh(db_tag)
    return db_tag

@router.delete("/{tag_id}")
def excluir_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """Soft delete tag (admin/manager only)"""
    tag_uuid = validate_uuid(tag_id)
    db_tag = db.query(TagStatus).filter(TagStatus.id == tag_uuid).first()
    if not db_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )

    # Soft delete
    db_tag.ativo = False
    db.commit()
    return {"message": "Tag deleted successfully"}

@router.post("/seed")
def criar_tags_padrao(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN"]))
):
    """Create default status tags (admin only)"""
    default_tags = [
        {"nome": "Separado", "cor": "#3B82F6", "descricao": "Pedido separado e pronto para envio", "ordem": "10"},
        {"nome": "Pago", "cor": "#10B981", "descricao": "Pagamento confirmado", "ordem": "20"},
        {"nome": "Enviado", "cor": "#F59E0B", "descricao": "Pedido enviado para entrega", "ordem": "30"},
        {"nome": "A cobrar", "cor": "#EF4444", "descricao": "Aguardando pagamento", "ordem": "40"},
        {"nome": "Entregue", "cor": "#8B5CF6", "descricao": "Pedido entregue ao cliente", "ordem": "50"},
        {"nome": "Cancelado", "cor": "#6B7280", "descricao": "Pedido cancelado", "ordem": "60"},
    ]

    created_tags = []
    for tag_data in default_tags:
        # Check if tag already exists
        existing = db.query(TagStatus).filter(TagStatus.nome == tag_data["nome"]).first()
        if not existing:
            tag_data["created_by"] = current_user.id
            db_tag = TagStatus(**tag_data)
            db.add(db_tag)
            created_tags.append(tag_data["nome"])

    db.commit()
    return {"message": f"Created {len(created_tags)} default tags", "tags": created_tags}