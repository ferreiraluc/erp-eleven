"""Audited reconciliation of explicit links and unique, corroborated identities."""
from fastapi import HTTPException
from ..models.cliente import Cliente
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento
from ..models.address_book import SavedAddress
from .address_book import lock_addresses
from .customer_identity import ensure_customer, match_recipient
from .customer_links import validate_order_customer, inherit_order_customer, validate_tracking_links
from .user_audit import record


def auto_link_tracking(db, row):
    if row.cliente_id: return False
    order = db.get(Pedido, row.pedido_id) if row.pedido_id else None
    customer = db.get(Cliente, order.cliente_id) if order and order.cliente_id else match_recipient(db, row.destinatario)
    if not customer: return False
    validate_tracking_links(db, pedido_id=row.pedido_id, cliente_id=customer.id, allow_inactive_customer=True)
    row.cliente_id = customer.id
    return True


def reconcile(db):
    lock_addresses(db)
    before = db.query(Cliente).count()
    tracking_before = db.query(Rastreamento).filter_by(cliente_id=None).count()
    result = {'addresses_linked': 0, 'orders_linked': 0, 'tracking_linked': 0, 'customers_created': 0,
              'address_reviews': [], 'unmatched_tracking': [], 'order_reviews': []}
    for row in db.query(SavedAddress).filter_by(merged_into_id=None).order_by(SavedAddress.id).with_for_update():
        if ensure_customer(db, row):
            row.version += 1
            result['addresses_linked'] += 1
        if row.customer_link_review:
            result['address_reviews'].append({'id': str(row.id), 'reason': row.customer_link_reason})
    db.flush()
    for row in db.query(Pedido).order_by(Pedido.id).with_for_update():
        if not row.cliente_id:
            customer = match_recipient(db, row.cliente_nome, row.cliente_telefone, row.cliente_email)
            if customer:
                try: validate_order_customer(db, row, customer.id)
                except HTTPException:
                    result['order_reviews'].append(str(row.id)); continue
                row.cliente_id = customer.id; result['orders_linked'] += 1
        if row.cliente_id:
            try: inherit_order_customer(db, row)
            except HTTPException: result['order_reviews'].append(str(row.id))
    db.flush()
    for row in db.query(Rastreamento).filter_by(cliente_id=None).order_by(Rastreamento.id).with_for_update():
        auto_link_tracking(db, row)
        if row.cliente_id:
            result['tracking_linked'] += 1
            if db.info.get('audit_actor'):
                record(db, 'tracking_customer_reconciled', 'clientes', entity='rastreamentos', entity_id=str(row.id),
                       changes={'cliente_id': str(row.cliente_id), 'rule': 'explicit_order_or_unique_full_name'})
        else:
            result['unmatched_tracking'].append({'id': str(row.id), 'name': row.destinatario,
                                                 'code': row.codigo_rastreio, 'reason': 'identity_not_unique_or_unknown'})
    db.flush()
    result['tracking_linked'] = tracking_before - db.query(Rastreamento).filter_by(cliente_id=None).count()
    result['customers_created'] = db.query(Cliente).count() - before
    return result
