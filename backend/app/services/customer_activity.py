"""Batch directory activity through explicit links, with scoped PDV aggregates.

Queue jobs are requests, not proof of a physical print or shipment. Purchases are
PDV sales only; order values, BI rows and fiado balances never become revenue here.
"""
from datetime import timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased

from ..config import settings
from ..models.address_book import SavedAddress
from ..models.cliente import Cliente
from ..models.pdv import PdvCliente, PdvSale
from ..models.pedido import Pedido
from ..models.printing import PrintJob
from ..models.rastreamento import Rastreamento
from .access_policy import own_sales, sales_query


def _purchases(db, user, customer_ids=None):
    query = sales_query(db.query(PdvSale), PdvSale, user, pdv=True).join(
        PdvCliente, PdvCliente.id == PdvSale.cliente_id,
    ).filter(
        PdvCliente.cadastro_cliente_id.is_not(None),
        PdvSale.deleted_at.is_(None), PdvSale.status != 'cancelled',
    )
    if customer_ids is not None:
        query = query.filter(PdvCliente.cadastro_cliente_id.in_(customer_ids))
    return query.with_entities(
        PdvCliente.cadastro_cliente_id.label('customer_id'),
        func.count(PdvSale.id).label('purchase_count'),
        func.max(PdvSale.created_at).label('last_purchase_at'),
    ).group_by(PdvCliente.cadastro_cliente_id).subquery()


def _address_owners(customer_ids=None):
    # Print jobs keep their original address ID after consolidation. Starting at
    # linked roots, follow all historical aliases, including multi-step merges.
    roots = select(
        SavedAddress.id.label('address_id'),
        SavedAddress.cliente_id.label('customer_id'),
    ).where(SavedAddress.merged_into_id.is_(None), SavedAddress.cliente_id.is_not(None))
    if customer_ids is not None:
        roots = roots.where(SavedAddress.cliente_id.in_(customer_ids))
    owners = roots.cte('customer_address_owners', recursive=True)
    child = aliased(SavedAddress)
    return owners.union(select(child.id, owners.c.customer_id).join(
        owners, child.merged_into_id == owners.c.address_id,
    ))


def _prints(db, customer_ids=None):
    owners = _address_owners(customer_ids)
    return db.query(
        owners.c.customer_id,
        func.count(PrintJob.id).label('print_count'),
        func.sum(case((PrintJob.status == 'submitted', 1), else_=0)).label('submitted_print_count'),
        func.sum(case((PrintJob.status.in_(('pending', 'claimed')), 1), else_=0)).label('pending_print_count'),
        func.sum(case((PrintJob.status == 'uncertain', 1), else_=0)).label('uncertain_print_count'),
        func.max(PrintJob.created_at).label('last_print_at'),
    ).join(PrintJob, PrintJob.address_id == owners.c.address_id).filter(
        PrintJob.source != 'bot_pdf_ephemeral',
    ).group_by(owners.c.customer_id).subquery()


def order_customer_directory(query, db, user, sort):
    """Sort the filtered directory before pagination, never by hidden sales."""
    if sort == 'ultima_compra':
        rollup = _purchases(db, user)
        query = query.outerjoin(rollup, rollup.c.customer_id == Cliente.id)
        return query.order_by(rollup.c.last_purchase_at.desc().nullslast(), Cliente.nome, Cliente.id)
    if sort == 'ultima_impressao':
        rollup = _prints(db)
        query = query.outerjoin(rollup, rollup.c.customer_id == Cliente.id)
        return query.order_by(rollup.c.last_print_at.desc().nullslast(), Cliente.nome, Cliente.id)
    return query.order_by(Cliente.nome, Cliente.id)


def customer_activity(db, customer_ids, user):
    """One batch SELECT for a whole page, without PDFs or per-client queries."""
    if not customer_ids:
        return {}
    purchases = _purchases(db, user, customer_ids)
    prints = _prints(db, customer_ids)
    shipment_owner = func.coalesce(Rastreamento.cliente_id, Pedido.cliente_id)
    shipments = db.query(
        shipment_owner.label('customer_id'), func.count(Rastreamento.id).label('shipment_count'),
    ).outerjoin(Pedido, Pedido.id == Rastreamento.pedido_id).filter(
        shipment_owner.in_(customer_ids),
    ).group_by(shipment_owner).subquery()
    orders = db.query(
        Pedido.cliente_id.label('customer_id'), func.count(Pedido.id).label('order_count'),
    ).filter(Pedido.cliente_id.in_(customer_ids)).group_by(Pedido.cliente_id).subquery()
    columns = [
        purchases.c.purchase_count, orders.c.order_count, shipments.c.shipment_count,
        prints.c.print_count, prints.c.submitted_print_count,
        prints.c.pending_print_count, prints.c.uncertain_print_count,
    ]
    query = db.query(Cliente.id, *(func.coalesce(column, 0).label(column.key) for column in columns),
                     purchases.c.last_purchase_at, prints.c.last_print_at).filter(Cliente.id.in_(customer_ids))
    for rollup in (purchases, orders, shipments, prints):
        query = query.outerjoin(rollup, rollup.c.customer_id == Cliente.id)
    result = {}
    for row in query.all():
        values = dict(row._mapping)
        customer_id = values.pop('id')
        for field, tz in (('last_purchase_at', settings.tz), ('last_print_at', timezone.utc)):
            value = values[field]
            if value is not None and value.tzinfo is None:
                values[field] = value.replace(tzinfo=tz)
        values['own_sales_only'] = own_sales(user)
        result[customer_id] = values
    return result
