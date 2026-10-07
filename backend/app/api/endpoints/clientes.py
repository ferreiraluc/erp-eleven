from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from ...database import get_db
from ...models.cliente import Cliente
from ...models.pedido import Pedido
from ...models.rastreamento import Rastreamento, RastreamentoStatus
from ...models.usuario import Usuario
from ...schemas.cliente import ClienteCreate, ClienteResponse, ClienteUpdate
from ...schemas.pedido import PedidoResponse
from ...schemas.customer_links import CustomerLinkRequest, CustomerLogisticsResponse
from ...schemas.rastreamento import RastreamentoComPedido
from ...services.customer_links import customer_shipments, inherit_order_customer, validate_tracking_links, lock_tracking_row
from ...services.customer_maintenance import resolve_customer
from ...services.customer_identity import find_customer
from ...services.address_book import lock_addresses
from ...dependencies import get_current_active_user, require_role
from ..validators import validate_uuid

router = APIRouter()


def _customer(db, customer_id, *, write=False):
    row = db.get(Cliente, customer_id) if write else resolve_customer(db, customer_id)
    if not row:
        raise HTTPException(404, 'Cliente não encontrado.')
    if write and row.merged_into_id:
        raise HTTPException(409, 'Este cadastro foi unificado. Atualize a lista e selecione o cliente principal.')
    return row


@router.get("/", response_model=List[ClienteResponse])
def listar_clientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    ativo: Optional[bool] = Query(True),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Lista clientes; include_inactive inclui ambos os estados, ignorando ativo."""
    query = db.query(Cliente).filter(Cliente.merged_into_id.is_(None))
    if not include_inactive and ativo is not None:
        query = query.filter(Cliente.ativo == ativo)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Cliente.nome.ilike(term),
                Cliente.email.ilike(term),
                Cliente.telefone.ilike(term),
                Cliente.cpf.ilike(term),
                Cliente.endereco.ilike(term),
            )
        )
    return query.order_by(Cliente.nome).offset(skip).limit(limit).all()


@router.post("/", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
def criar_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Cria um cliente, evitando repetir uma identidade já reconhecida."""
    lock_addresses(db)
    existing, _, _ = find_customer(db, cliente.model_dump())
    if existing:
        raise HTTPException(409, 'Cliente já cadastrado. Localize-o na lista de clientes antes de criar outro cadastro.')
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
            Cliente.merged_into_id.is_(None),
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
    return _customer(db, uuid_)


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: str,
    update: ClienteUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Atualiza dados de um cliente."""
    uuid_ = validate_uuid(cliente_id)
    lock_addresses(db)
    db_cliente = _customer(db, uuid_, write=True)

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
    lock_addresses(db)
    db_cliente = _customer(db, uuid_, write=True)
    db_cliente.ativo = False
    db.commit()
    return {"message": "Cliente inativado com sucesso."}


@router.get("/{cliente_id}/pedidos", response_model=List[PedidoResponse])
def listar_pedidos_do_cliente(
    cliente_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Lista todos os pedidos vinculados a um cliente."""
    uuid_ = validate_uuid(cliente_id)
    uuid_ = _customer(db, uuid_).id
    return (
        db.query(Pedido)
        .filter(Pedido.cliente_id == uuid_)
        .order_by(desc(Pedido.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{cliente_id}/logistica", response_model=CustomerLogisticsResponse)
def logistica_do_cliente(
    cliente_id: str,
    orders_skip: int = Query(0, ge=0),
    shipments_skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    customer_id = validate_uuid(cliente_id)
    customer_id = _customer(db, customer_id).id
    orders = db.query(Pedido).filter(Pedido.cliente_id == customer_id)
    shipments = customer_shipments(db, customer_id)
    result = []
    for row in shipments.order_by(Rastreamento.created_at.desc(), Rastreamento.id).offset(shipments_skip).limit(limit).all():
        parcel = RastreamentoComPedido.model_validate(row)
        if row.pedido:
            parcel.numero_pedido = row.pedido.numero_pedido
            parcel.cliente_nome_pedido = row.pedido.cliente_nome
        result.append(parcel)
    return CustomerLogisticsResponse(
        order_total=orders.count(), shipment_total=shipments.count(),
        in_transit=shipments.filter(Rastreamento.ativo == True, Rastreamento.status == RastreamentoStatus.EM_TRANSITO).count(),
        delivered=shipments.filter(Rastreamento.ativo == True, Rastreamento.status == RastreamentoStatus.ENTREGUE).count(),
        orders=orders.order_by(Pedido.created_at.desc(), Pedido.id).offset(orders_skip).limit(limit).all(),
        shipments=result,
    )


@router.post("/{cliente_id}/vinculos")
def vincular_ao_cliente(
    cliente_id: str, link: CustomerLinkRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    customer_id = validate_uuid(cliente_id)
    lock_addresses(db)
    cliente = _customer(db, customer_id, write=True)
    if not cliente.ativo:
        raise HTTPException(404, "Cliente não encontrado ou inativo.")
    if link.kind == "pedido":
        order = db.query(Pedido).filter(Pedido.id == link.target_id).with_for_update().first()
        if not order:
            raise HTTPException(404, "Pedido não encontrado.")
        if order.cliente_id and order.cliente_id != customer_id:
            raise HTTPException(409, "O pedido já está vinculado a outro cliente. Revise o cadastro do pedido.")
        order.cliente_id = customer_id
        inherit_order_customer(db, order)
    else:
        row = lock_tracking_row(db, link.target_id)
        if not row or not row.ativo:
            raise HTTPException(404, "Rastreio não encontrado ou arquivado.")
        if row.cliente_id and row.cliente_id != customer_id:
            raise HTTPException(409, "O rastreio já está vinculado a outro cliente. Revise o cadastro do rastreio.")
        validate_tracking_links(db, pedido_id=row.pedido_id, cliente_id=customer_id)
        row.cliente_id = customer_id
    db.commit()
    return {"linked": True, "kind": link.kind, "target_id": link.target_id, "cliente_id": customer_id}


@router.get("/{cliente_id}/historico-enderecos")
def historico_enderecos_cliente(
    cliente_id: str, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100),
    kind: str = Query('all', pattern='^(all|frete|impressao)$'),
    db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user),
):
    from ...models.address_book import SavedAddress
    from ...services.address_book import address_family
    from ...services.address_usage import history_for_ids
    customer_id = validate_uuid(cliente_id)
    customer_id = _customer(db, customer_id).id
    addresses = db.query(SavedAddress).filter_by(cliente_id=customer_id, merged_into_id=None).order_by(SavedAddress.updated_at.desc()).all()
    ids = set()
    for address in addresses:
        ids.update(address_family(db, address))
    return {**history_for_ids(db, ids, offset, limit, kind),
            'addresses': [{'id': str(row.id), 'label': row.label, 'active': row.active,
                           'review': row.customer_link_review} for row in addresses]}
