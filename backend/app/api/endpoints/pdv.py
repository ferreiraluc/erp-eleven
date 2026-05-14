from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from decimal import Decimal
import uuid

from ...database import get_db
from ...dependencies import get_current_active_user
from ...models.usuario import Usuario
from ...models.pdv import PdvCliente, PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement
from ...models.inventory import Item, StockMovement
from ...schemas.pdv import (
    PdvClienteCreate, PdvClienteUpdate, PdvClienteResponse,
    PdvSaleCreate, PdvSaleResponse, PdvSaleListItem,
    PdvFiadoPaymentCreate, PdvFiadoMovementResponse,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _apply_stock(db: Session, sale: PdvSale, created_by_id):
    """Decrement stock for each non-avulso item in the sale."""
    for item in sale.items:
        if item.is_avulso or not item.item_id:
            continue
        inv_item = db.query(Item).filter(Item.id == item.item_id).first()
        if not inv_item:
            continue

        qty = int(item.quantity)
        location = item.location or "loja"

        qty_before = inv_item.current_stock
        inv_item.current_stock = max(0, inv_item.current_stock - qty)

        # Update split stock
        if location == "deposito":
            inv_item.stock_deposito = max(0, (inv_item.stock_deposito or 0) - qty)
        else:
            inv_item.stock_loja = max(0, (inv_item.stock_loja or 0) - qty)

        mv = StockMovement(
            item_id=inv_item.id,
            movement_type="exit",
            quantity=qty,
            quantity_before=qty_before,
            quantity_after=inv_item.current_stock,
            reason="pdv_sale",
            reference_type="pdv_sale",
            reference_id=str(sale.id),
            location_from=location,
            created_by=created_by_id,
        )
        db.add(mv)

    sale.stock_applied = True


def _update_fiado(db: Session, sale: PdvSale, created_by_id):
    """Create fiado debit for the fiado payment portion."""
    fiado_total = sum(
        float(p.amount_gs) for p in sale.payments if p.method == "fiado"
    )
    if fiado_total <= 0 or not sale.cliente_id:
        return

    cliente = db.query(PdvCliente).filter(PdvCliente.id == sale.cliente_id).first()
    if not cliente:
        return

    new_saldo = float(cliente.saldo_fiado_gs) + fiado_total
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

@router.post("/sales", response_model=PdvSaleResponse, status_code=201)
def create_sale(
    body: PdvSaleCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    if not body.items:
        raise HTTPException(status_code=400, detail="A venda deve ter pelo menos 1 item")

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
        cliente_nome=body.cliente_nome,
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

    for p in body.payments:
        db.add(PdvPayment(
            id=uuid.uuid4(),
            sale_id=sale.id,
            method=p.method,
            currency=p.currency,
            amount_original=Decimal(str(p.amount_original)),
            exchange_rate=Decimal(str(p.exchange_rate)),
            amount_gs=Decimal(str(p.amount_gs)),
            cambista_id=p.cambista_id,
            reference=p.reference,
        ))

    _apply_stock(db, sale, current_user.id)
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
    q = db.query(PdvSale)
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
    sale = db.query(PdvSale).filter(PdvSale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    return _sale_to_response(sale)


@router.post("/sales/{sale_id}/cancel")
def cancel_sale(
    sale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    sale = db.query(PdvSale).filter(PdvSale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    if sale.status == "cancelled":
        raise HTTPException(status_code=400, detail="Venda já cancelada")

    sale.status = "cancelled"

    # Reverse stock
    if sale.stock_applied:
        for item in sale.items:
            if item.is_avulso or not item.item_id:
                continue
            inv_item = db.query(Item).filter(Item.id == item.item_id).first()
            if not inv_item:
                continue
            qty = int(item.quantity)
            qty_before = inv_item.current_stock
            inv_item.current_stock += qty
            if item.location == "deposito":
                inv_item.stock_deposito = (inv_item.stock_deposito or 0) + qty
            else:
                inv_item.stock_loja = (inv_item.stock_loja or 0) + qty

            db.add(StockMovement(
                item_id=inv_item.id,
                movement_type="entry",
                quantity=qty,
                quantity_before=qty_before,
                quantity_after=inv_item.current_stock,
                reason="pdv_cancel",
                reference_type="pdv_sale",
                reference_id=str(sale.id),
                location_to=item.location,
                created_by=current_user.id,
            ))
        sale.stock_applied = False

    db.commit()
    return {"ok": True}


# ── PDV Clientes / Fiado ──────────────────────────────────────────────────────

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
    return q.order_by(PdvCliente.nome).all()


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
    return cliente


@router.get("/clients/{cliente_id}", response_model=PdvClienteResponse)
def get_client(
    cliente_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    cliente = db.query(PdvCliente).filter(PdvCliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente


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
    return cliente


@router.get("/clients/{cliente_id}/fiado", response_model=List[PdvFiadoMovementResponse])
def get_fiado_history(
    cliente_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
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
    cliente = db.query(PdvCliente).filter(PdvCliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    new_saldo = max(0.0, float(cliente.saldo_fiado_gs) - float(body.valor_gs))
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
                id=i.id, item_id=i.item_id, item_name=i.item_name,
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
