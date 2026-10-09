from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from decimal import Decimal
from datetime import date
import uuid

from ...database import get_db
from ...dependencies import get_current_active_user, require_owner
from ...schemas.pdv_management import SaleCommand, SaleCommit
from ...services import pdv_management, pdv_customers
from ...services.pdv_payments import validate_payment
from ...models.usuario import Usuario
from ...models.pdv import PdvCliente, PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement
from ...models.inventory import Item
from ...schemas.pdv import (
    PdvClienteCreate, PdvClienteUpdate, PdvClienteResponse,
    PdvSaleCreate, PdvSaleResponse, PdvSaleListItem,
    PdvFiadoPaymentCreate, PdvFiadoMovementResponse,
    validate_pdv_quantity,
    PdvCustomerSearch, PdvCustomerSelection,
)

from ...services.access_policy import sales_query, require_sale_owner, own_sales, require_all_sales
from ...services.inventory_service import create_movement, StockMovementError

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stock_conflict(db: Session, detail: str):
    db.rollback()
    raise HTTPException(status_code=409, detail=detail)


def _lock_sale_stock(db: Session, sale_items, *, allow_inactive=False) -> dict[uuid.UUID, Item]:
    """Validate every real line, then re-read products under ordered locks."""
    item_ids = set()
    for item in sale_items:
        if item.is_avulso:
            continue
        try:
            validate_pdv_quantity(item.quantity, avulso=False)
        except ValueError as error:
            _stock_conflict(db, f"Quantidade inválida no item da venda. {error}")
        if item.location not in ("loja", "deposito"):
            _stock_conflict(db, "Local inválido no item da venda. Confira o local original; use loja ou deposito.")
        if not item.item_id:
            _stock_conflict(db, "Produto de catálogo sem vínculo no item da venda. Confira o cadastro antes de continuar.")
        item_ids.add(item.item_id)
    if not item_ids:
        return {}
    with db.no_autoflush:
        items = (
            db.query(Item).filter(Item.id.in_(item_ids)).order_by(Item.id)
            .populate_existing().with_for_update().all()
        )
    if len(items) != len(item_ids):
        _stock_conflict(db, "Um produto de catálogo da venda não existe. Confira o cadastro antes de continuar.")
    for item in items:
        if item.deleted_at:
            _stock_conflict(db, 'Produto excluído do catálogo. Confira o histórico antes de alterar esta venda; o produto não será reativado.')
        if not allow_inactive and not item.is_active:
            _stock_conflict(db, f'Produto inativo: "{item.name}". Selecione um produto ativo para vender.')
        if any(value is None for value in (item.current_stock, item.stock_loja, item.stock_deposito)):
            detail = f'Estoque não informado para "{item.name}". Confira os três saldos antes de concluir esta operação.'
            _stock_conflict(db, detail)
    return {item.id: item for item in items}


def _apply_stock(db: Session, sale: PdvSale, created_by_id, stock_items: dict[uuid.UUID, Item], *, reverse=False):
    """Use the shared conservation rules; a conflict rolls back the entire sale."""
    try:
        for item in sale.items:
            if item.is_avulso:
                continue
            movement = create_movement(
                db=db, item_id=stock_items[item.item_id].id,
                movement_type="entry" if reverse else "exit",
                quantity=int(validate_pdv_quantity(item.quantity, avulso=False)),
                created_by=created_by_id,
                reason="pdv_cancel" if reverse else "pdv_sale",
                reference_type="pdv_sale", reference_id=str(sale.id),
                location=item.location,
                location_to=item.location if reverse else None,
            )
            if reverse:
                # Keep PDV cancellation history as an entry into the original location.
                movement.location_from = None
    except (StockMovementError, ValueError) as error:
        _stock_conflict(db, str(error))
    sale.stock_applied = not reverse


def _update_fiado(db: Session, sale: PdvSale, created_by_id):
    """Create fiado debit for the fiado payment portion."""
    fiado_total = sum(
        p.amount_gs for p in sale.payments if p.method == "fiado"
    )
    if fiado_total <= 0 or not sale.cliente_id:
        return

    cliente = db.query(PdvCliente).filter(PdvCliente.id == sale.cliente_id).with_for_update().populate_existing().first()
    if not cliente:
        return

    new_saldo = cliente.saldo_fiado_gs + fiado_total
    cliente.saldo_fiado_gs = Decimal(str(new_saldo))

    mv = PdvFiadoMovement(
        cliente_id=sale.cliente_id,
        sale_id=sale.id,
        tipo="debit",
        valor_gs=Decimal(str(fiado_total)),
        saldo_gs=Decimal(str(new_saldo)),
        created_by=created_by_id,
    )
    db.add(mv)


# ── Sales ─────────────────────────────────────────────────────────────────────

@router.get('/management')
def managed_sales(page: int = Query(1,ge=1,le=100000), page_size: int = Query(25,ge=1,le=100),
                  q: str = Query('',max_length=150), status: Optional[str] = None,
                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                  seller_id: Optional[uuid.UUID] = None, payment: Optional[str] = None, deleted: bool = False,
                  db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    return pdv_management.listing(db,user,page=page,page_size=page_size,q=q,status=status,date_from=date_from,date_to=date_to,seller_id=seller_id,payment=payment,deleted=deleted)


@router.get('/management/options')
def managed_options(db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    q=db.query(Usuario.id,Usuario.nome).filter(Usuario.ativo.is_(True))
    if own_sales(user):q=q.filter(Usuario.id==user.id)
    return {'sellers':[{'id':r.id,'name':r.nome} for r in q.order_by(Usuario.nome)]}


@router.get('/management/{sale_id}')
def managed_sale(sale_id: uuid.UUID,db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    return pdv_management.detail(db,sale_id,user)


@router.post('/management/{sale_id}/preview')
def preview_sale_change(sale_id: uuid.UUID, body: SaleCommand, db: Session = Depends(get_db), user: Usuario = Depends(require_owner)):
    try:return pdv_management.plan(db,sale_id,user,body)[-1]
    except ValueError as e:raise HTTPException(422,str(e)) from None


@router.post('/management/{sale_id}/commit')
def commit_sale_change(sale_id: uuid.UUID, body: SaleCommit, db: Session = Depends(get_db), user: Usuario = Depends(require_owner)):
    return pdv_management.commit(db,sale_id,user,body)

@router.post("/sales", response_model=PdvSaleResponse, status_code=201)
def create_sale(
    body: PdvSaleCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    require_sale_owner(current_user, body.vendedor_id or current_user.id, pdv=True)
    if not body.items:
        raise HTTPException(status_code=400, detail="A venda deve ter pelo menos 1 item")

    payments = [validate_payment(p.model_dump()) for p in body.payments]
    if any(p['method'] == 'fiado' and p['amount_gs'] > 0 for p in payments) and not body.cliente_id:
        raise HTTPException(422, 'Selecione o cliente para lançar fiado.')

    stock_items = _lock_sale_stock(db, body.items)
    customer = pdv_customers.select(db, PdvCustomerSelection(source='pdv', id=body.cliente_id), current_user) if body.cliente_id else None

    # Compute totals
    subtotal = sum(
        float(i.quantity) * float(i.unit_price_gs) - float(i.discount_gs)
        for i in body.items
    )
    desconto = float(body.desconto_gs)
    total = max(0.0, subtotal - desconto)

    sale = PdvSale(
        id=uuid.uuid4(),
        vendedor_id=body.vendedor_id or current_user.id,
        cliente_id=body.cliente_id,
        cliente_nome=customer.nome if customer else body.cliente_nome,
        subtotal_gs=Decimal(str(round(subtotal, 2))),
        desconto_gs=Decimal(str(round(desconto, 2))),
        total_gs=Decimal(str(round(total, 2))),
        notas=body.notas,
        status="completed",
        created_by=current_user.id,
    )
    db.add(sale)
    db.flush()  # get sale.id

    for i in body.items:
        item_total = float(i.quantity) * float(i.unit_price_gs) - float(i.discount_gs)
        db.add(PdvSaleItem(
            id=uuid.uuid4(),
            sale_id=sale.id,
            item_id=i.item_id,
            item_name=i.item_name,
            item_sku=i.item_sku,
            item_category=i.item_category,
            item_size=i.item_size,
            item_color=i.item_color,
            quantity=Decimal(str(i.quantity)),
            unit_price_gs=Decimal(str(i.unit_price_gs)),
            original_price_gs=Decimal(str(i.original_price_gs)) if i.original_price_gs else None,
            discount_gs=Decimal(str(i.discount_gs)),
            total_gs=Decimal(str(round(item_total, 2))),
            is_avulso=i.is_avulso,
            location=i.location,
        ))

    for payment in payments:
        db.add(PdvPayment(id=uuid.uuid4(), sale_id=sale.id, **payment))

    db.flush()
    _apply_stock(db, sale, current_user.id, stock_items)
    _update_fiado(db, sale, current_user.id)

    db.commit()
    db.refresh(sale)
    return _sale_to_response(sale)


@router.get("/sales", response_model=List[PdvSaleListItem])
def list_sales(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    status: Optional[str] = None,
    cliente_id: Optional[uuid.UUID] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    q = sales_query(db.query(PdvSale), PdvSale, current_user, pdv=True).filter(PdvSale.deleted_at.is_(None))
    if status:
        q = q.filter(PdvSale.status == status)
    if cliente_id:
        q = q.filter(PdvSale.cliente_id == cliente_id)
    if date_from:
        q = q.filter(PdvSale.created_at >= date_from)
    if date_to:
        q = q.filter(PdvSale.created_at <= date_to)

    sales = q.order_by(desc(PdvSale.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for s in sales:
        result.append(PdvSaleListItem(
            id=s.id,
            cliente_nome=s.cliente_nome,
            total_gs=float(s.total_gs),
            desconto_gs=float(s.desconto_gs),
            status=s.status,
            items_count=len(s.items),
            payment_methods=list({p.method for p in s.payments}),
            created_at=s.created_at,
        ))
    return result


@router.get("/sales/{sale_id}", response_model=PdvSaleResponse)
def get_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    sale = sales_query(db.query(PdvSale), PdvSale, current_user, pdv=True).filter(PdvSale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    if sale.deleted_at and not pdv_management.is_owner(current_user):
        raise HTTPException(404,'Venda não encontrada')
    return _sale_to_response(sale)


@router.post("/sales/{sale_id}/cancel")
def cancel_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    sale = (
        sales_query(db.query(PdvSale), PdvSale, current_user, pdv=True)
        .filter(PdvSale.id == sale_id).populate_existing().with_for_update().first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    pdv_management.owner(current_user)
    if sale.status == "cancelled":
        raise HTTPException(status_code=400, detail="Venda já cancelada")

    command=SaleCommand(operation='cancel',reason='Cancelamento integral pela API do PDV')
    preview=pdv_management.plan(db,sale_id,current_user,command)[-1]
    pdv_management.commit(db,sale_id,current_user,SaleCommit(command=command,plan_token=preview['plan_token'],request_id=uuid.uuid4(),confirm=True))
    return {"ok": True}


# ── PDV Clientes / Fiado ──────────────────────────────────────────────────────

@router.get('/clients/search', response_model=PdvCustomerSearch)
def search_customers(
    q: str = Query('', max_length=120),
    limit: int = Query(20, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return pdv_customers.search(db, q, limit)


@router.post('/clients/select', response_model=PdvClienteResponse)
def select_customer(
    body: PdvCustomerSelection,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    customer = pdv_customers.select(db, body, current_user)
    db.commit()
    return _client_response(customer, current_user)

@router.get("/clients", response_model=List[PdvClienteResponse])
def list_clients(
    search: Optional[str] = None,
    tipo: Optional[str] = None,
    ativo: bool = True,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    q = db.query(PdvCliente).filter(PdvCliente.ativo == ativo)
    if tipo:
        q = q.filter(PdvCliente.tipo == tipo)
    if search:
        term = f"%{search}%"
        q = q.filter(
            PdvCliente.nome.ilike(term) |
            PdvCliente.doc.ilike(term) |
            PdvCliente.telefone.ilike(term)
        )
    return [_client_response(c, current_user) for c in q.order_by(PdvCliente.nome).all()]


@router.post("/clients", response_model=PdvClienteResponse, status_code=201)
def create_client(
    body: PdvClienteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    cliente = PdvCliente(
        id=uuid.uuid4(),
        created_by=current_user.id,
        **body.model_dump(),
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return _client_response(cliente, current_user)


@router.get("/clients/{cliente_id}", response_model=PdvClienteResponse)
def get_client(
    cliente_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    cliente = db.query(PdvCliente).filter(PdvCliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return _client_response(cliente, current_user)


@router.put("/clients/{cliente_id}", response_model=PdvClienteResponse)
def update_client(
    cliente_id: uuid.UUID,
    body: PdvClienteUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    cliente = db.query(PdvCliente).filter(PdvCliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(cliente, k, v)
    db.commit()
    db.refresh(cliente)
    return _client_response(cliente, current_user)


@router.get("/clients/{cliente_id}/fiado", response_model=List[PdvFiadoMovementResponse])
def get_fiado_history(
    cliente_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    require_all_sales(current_user)
    movs = (
        db.query(PdvFiadoMovement)
        .filter(PdvFiadoMovement.cliente_id == cliente_id)
        .order_by(desc(PdvFiadoMovement.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return movs


@router.post("/clients/{cliente_id}/fiado/payment", response_model=PdvFiadoMovementResponse)
def record_fiado_payment(
    cliente_id: uuid.UUID,
    body: PdvFiadoPaymentCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    require_all_sales(current_user)
    cliente = db.query(PdvCliente).filter(PdvCliente.id == cliente_id).with_for_update().populate_existing().first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    value = pdv_management.positive(body.valor_gs)
    if value <= 0 or value > cliente.saldo_fiado_gs:
        raise HTTPException(422, 'O recebimento deve ser positivo e não pode superar o saldo devedor.')
    new_saldo = cliente.saldo_fiado_gs - value
    cliente.saldo_fiado_gs = Decimal(str(new_saldo))

    mv = PdvFiadoMovement(
        id=uuid.uuid4(),
        cliente_id=cliente_id,
        tipo="payment",
        valor_gs=Decimal(str(body.valor_gs)),
        saldo_gs=Decimal(str(new_saldo)),
        notas=body.notas,
        created_by=current_user.id,
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv


# ── Internal serializer ───────────────────────────────────────────────────────

def _sale_to_response(sale: PdvSale) -> PdvSaleResponse:
    from sqlalchemy.orm import object_session
    from sqlalchemy import or_
    db = object_session(sale)
    product_ids = [line.item_id for line in sale.items if line.item_id]
    legacy_skus = [line.item_sku for line in sale.items if not line.item_id and line.item_sku]
    deleted = db.query(Item.id, Item.sku_internal).filter(Item.deleted_at.isnot(None),
        or_(Item.id.in_(product_ids), Item.sku_internal.in_(legacy_skus))).all() if db else []
    deleted_ids, deleted_skus = {r.id for r in deleted}, {r.sku_internal for r in deleted}
    def history_name(line):
        removed = line.item_id in deleted_ids if line.item_id else line.item_sku in deleted_skus
        return f'Produto excluído — {line.item_name}' if removed else line.item_name
    return PdvSaleResponse(
        id=sale.id,
        vendedor_id=sale.vendedor_id,
        cliente_id=sale.cliente_id,
        cliente_nome=sale.cliente_nome,
        subtotal_gs=float(sale.subtotal_gs),
        desconto_gs=float(sale.desconto_gs),
        total_gs=float(sale.total_gs),
        status=sale.status,
        stock_applied=sale.stock_applied,
        notas=sale.notas,
        created_at=sale.created_at,
        items=[
            dict(
                id=i.id, item_id=i.item_id, item_name=history_name(i),
                item_sku=i.item_sku, item_category=i.item_category,
                item_size=i.item_size, item_color=i.item_color,
                quantity=float(i.quantity), unit_price_gs=float(i.unit_price_gs),
                original_price_gs=float(i.original_price_gs) if i.original_price_gs else None,
                discount_gs=float(i.discount_gs), total_gs=float(i.total_gs),
                is_avulso=i.is_avulso, location=i.location,
            )
            for i in sale.items
        ],
        payments=[
            dict(
                id=p.id, method=p.method, currency=p.currency,
                amount_original=float(p.amount_original),
                exchange_rate=float(p.exchange_rate),
                amount_gs=float(p.amount_gs),
                cambista_id=p.cambista_id, reference=p.reference,
                created_at=p.created_at,
            )
            for p in sale.payments
        ],
    )


def _client_response(cliente, user):
    data = PdvClienteResponse.model_validate(cliente)
    if own_sales(user): data.saldo_fiado_gs = None
    return data
