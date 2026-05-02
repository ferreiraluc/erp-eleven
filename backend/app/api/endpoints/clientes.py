from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from ...database import get_db
from ...models.cliente import Cliente
from ...models.usuario import Usuario
from ...schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid

router = APIRouter()


def _build_endereco_str(cliente: Cliente) -> str:
    """Monta string de endereço a partir dos campos estruturados."""
    parts = [
        cliente.endereco_rua,
        cliente.endereco_bairro,
        cliente.endereco_cidade,
        cliente.endereco_uf,
        cliente.endereco_cep,
    ]
    return ", ".join(p for p in parts if p)


@router.get("/", response_model=List[ClienteResponse])
def listar_clientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    ativo: Optional[bool] = Query(True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Lista clientes com busca por nome, email, telefone ou CPF."""
    query = db.query(Cliente)
    if ativo is not None:
        query = query.filter(Cliente.ativo == ativo)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Cliente.nome.ilike(term),
                Cliente.email.ilike(term),
                Cliente.telefone.ilike(term),
                Cliente.cpf.ilike(term),
                Cliente.endereco_cidade.ilike(term),
            )
        )
    return query.order_by(Cliente.nome).offset(skip).limit(limit).all()


@router.post("/", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
def criar_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Cria um novo cliente."""
    db_cliente = Cliente(**cliente.model_dump())
    db.add(db_cliente)
    try:
        db.commit()
        db.refresh(db_cliente)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF já cadastrado para outro cliente.",
        )
    return db_cliente


@router.get("/search", response_model=List[ClienteResponse])
def buscar_clientes(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Busca rápida para autocomplete (nome, telefone, CPF, email)."""
    term = f"%{q}%"
    return (
        db.query(Cliente)
        .filter(
            Cliente.ativo == True,
            or_(
                Cliente.nome.ilike(term),
                Cliente.telefone.ilike(term),
                Cliente.cpf.ilike(term),
                Cliente.email.ilike(term),
            ),
        )
        .order_by(Cliente.nome)
        .limit(limit)
        .all()
    )


@router.get("/{cliente_id}", response_model=ClienteResponse)
def obter_cliente(
    cliente_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Retorna um cliente pelo ID."""
    uuid_ = validate_uuid(cliente_id)
    cliente = db.query(Cliente).filter(Cliente.id == uuid_).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    return cliente


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: str,
    update: ClienteUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Atualiza dados de um cliente."""
    uuid_ = validate_uuid(cliente_id)
    db_cliente = db.query(Cliente).filter(Cliente.id == uuid_).first()
    if not db_cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(db_cliente, field, value)

    try:
        db.commit()
        db.refresh(db_cliente)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF já cadastrado para outro cliente.",
        )
    return db_cliente


@router.delete("/{cliente_id}")
def excluir_cliente(
    cliente_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Soft-delete de cliente (marca ativo=False)."""
    uuid_ = validate_uuid(cliente_id)
    db_cliente = db.query(Cliente).filter(Cliente.id == uuid_).first()
    if not db_cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado.")
    db_cliente.ativo = False
    db.commit()
    return {"message": "Cliente inativado com sucesso."}
