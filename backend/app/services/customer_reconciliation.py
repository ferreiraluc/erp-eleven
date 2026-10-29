"""Audited reconciliation of explicit links and unique, corroborated identities."""
import hashlib
import hmac
import json

from fastapi import HTTPException
from sqlalchemy import or_
from ..models.cliente import Cliente
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento
from ..models.address_book import SavedAddress
from .address_book import lock_addresses
from .customer_identity import (ensure_customer, match_recipient, find_customer, name_key,
                                corroboration, full_name, ensure_pdv_customer, pdv_identity_data)
from .customer_links import validate_order_customer, inherit_order_customer, validate_tracking_links
from .user_audit import record


def auto_link_tracking(db, row, *, customers=None):
    if row.cliente_id: return False
    order = db.get(Pedido, row.pedido_id) if row.pedido_id else None
    customer = db.get(Cliente, order.cliente_id) if order and order.cliente_id else match_recipient(
        db, row.destinatario, address=row.destino, customers=customers)
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
    customers = db.query(Cliente).all()
    for row in db.query(Pedido).order_by(Pedido.id).with_for_update():
        if not row.cliente_id:
            customer = match_recipient(db, row.cliente_nome, row.cliente_telefone, row.cliente_email,
                address=row.endereco_entrega, customers=customers)
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
        auto_link_tracking(db, row, customers=customers)
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


LINK_KINDS = {'address': 'addresses', 'order': 'orders', 'tracking': 'tracking', 'pdv_account': 'pdv_accounts'}
CUSTOMER_REVIEW_LIMIT = 10_000


def auto_link_pdv_customer(db, row):
    """A selected PDV account may acquire a directory link, never a balance merge."""
    return ensure_pdv_customer(db, row)


def _identity_snapshot(row):
    # Used only in the opaque digest. Never returned, logged or sent to AI.
    return {column.name: str(getattr(row, column.name)) for column in row.__table__.columns}


def _customer_link_plan(db, customer, limit=200):
    from sqlalchemy.orm import selectinload
    from ..models.pdv import PdvCliente
    from .pdv_customers import normalizer, key

    limit = min(200, max(1, int(limit)))
    customers = db.query(Cliente).order_by(Cliente.id).limit(CUSTOMER_REVIEW_LIMIT + 1).populate_existing().all()
    if customer.merged_into_id or not customer.ativo:
        raise HTTPException(409, 'Selecione o cadastro principal e ativo antes de associar o histórico.')
    counts = dict.fromkeys(LINK_KINDS.values(), 0)
    public = {'counts': counts, 'items': [], 'limited': len(customers) > CUSTOMER_REVIEW_LIMIT,
              'scanned': 0, 'limit': limit}
    planned = []
    inspected = []
    # A truncated identity directory cannot prove that a name has no homonym.
    # Refuse automatic candidates rather than linking through incomplete evidence.
    if len(customers) <= CUSTOMER_REVIEW_LIMIT:
        by_id = {row.id: row for row in customers}
        names = {name_key(customer.nome)}
        for alias in customers:
            current, seen = alias, set()
            while current and current.merged_into_id and current.id not in seen:
                seen.add(current.id)
                current = by_id.get(current.merged_into_id)
            if current and current.id == customer.id:
                names.add(name_key(alias.nome))
        names = {name for name in names if full_name(name)}
        normalize = normalizer(db)
        sql_names = [key(name) for name in sorted(names)]

        def eligible(data):
            if name_key(data.get('nome')) not in names:
                return None
            matched, _, _ = find_customer(db, data, customers=customers)
            return corroboration(customer, data) if matched and matched.id == customer.id else None

        def inspect_rows(kind, query):
            nonlocal public
            rows = query.order_by(query.column_descriptions[0]['entity'].id).limit(limit + 1).populate_existing().all()
            if len(rows) > limit:
                public['limited'] = True
            rows = rows[:limit]
            public['scanned'] += len(rows)
            inspected.extend(_identity_snapshot(row) for row in rows)
            return rows

        def add(kind, row, label, reason):
            planned.append((kind, row, reason))
            counts[LINK_KINDS[kind]] += 1
            public['items'].append({'kind': kind, 'id': str(row.id), 'label': label or 'Cadastro sem nome', 'reason': reason})

        addresses = inspect_rows('address', db.query(SavedAddress).filter(
            SavedAddress.merged_into_id.is_(None), SavedAddress.cliente_id.is_(None),
            SavedAddress.pdv_cliente_id.is_(None), normalize(SavedAddress.data['nome'].as_string()).in_(sql_names)))
        for row in addresses:
            reason = eligible(row.data)
            if reason:
                add('address', row, row.label, reason)

        orders = inspect_rows('order', db.query(Pedido).filter(Pedido.cliente_id.is_(None),
            normalize(Pedido.cliente_nome).in_(sql_names)))
        for row in orders:
            reason = eligible({'nome': row.cliente_nome, 'telefone': row.cliente_telefone,
                'email': row.cliente_email, 'endereco_livre': row.endereco_entrega})
            if not reason:
                continue
            try:
                validate_order_customer(db, row, customer.id)
            except HTTPException:
                continue
            add('order', row, row.numero_pedido, reason)
        planned_orders = {row.id for kind, row, _ in planned if kind == 'order'}

        parcels = inspect_rows('tracking', db.query(Rastreamento).options(selectinload(Rastreamento.pedido)).outerjoin(Pedido, Pedido.id == Rastreamento.pedido_id).filter(
            Rastreamento.cliente_id.is_(None), or_(normalize(Rastreamento.destinatario).in_(sql_names),
                Pedido.cliente_id == customer.id, Rastreamento.pedido_id.in_(planned_orders))))
        for row in parcels:
            parent = db.get(Pedido, row.pedido_id) if row.pedido_id else None
            if parent and parent.cliente_id and parent.cliente_id != customer.id:
                continue
            if parent and (parent.cliente_id == customer.id or parent.id in planned_orders):
                reason = 'explicit_order'
            else:
                if parent and full_name(parent.cliente_nome) and name_key(parent.cliente_nome) not in names:
                    continue
                reason = eligible({'nome': row.destinatario, 'endereco_livre': row.destino})
            if reason:
                add('tracking', row, row.codigo_rastreio, reason)

        accounts = inspect_rows('pdv_account', db.query(PdvCliente).filter(
            PdvCliente.cadastro_cliente_id.is_(None), normalize(PdvCliente.nome).in_(sql_names)))
        for row in accounts:
            reason = eligible(pdv_identity_data(row))
            if reason:
                add('pdv_account', row, row.nome, reason)

    digest = {'customer_id': str(customer.id), 'identities': [_identity_snapshot(row) for row in customers],
              'inspected': inspected, 'items': public['items'], 'limit': limit, 'limited': public['limited']}
    public['token'] = hashlib.sha256(json.dumps(digest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return public, planned


def preview_customer_links(db, customer, limit=200):
    """Bounded, read-only evidence for one customer's historical associations."""
    return _customer_link_plan(db, customer, limit)[0]


def apply_customer_links(db, customer, expected_token, actor, limit=200):
    """Apply exactly the reviewed plan once; caller commits the transaction."""
    from ..models.pdv import PdvCliente
    from ..models.access import AuditEvent

    if not expected_token or len(expected_token) != 64:
        raise HTTPException(409, 'Confira a prévia antes de associar o histórico.')
    lock_addresses(db)
    customer = db.query(Cliente).filter(Cliente.id == customer.id).populate_existing().with_for_update().first()
    if not customer or customer.merged_into_id or not customer.ativo:
        raise HTTPException(409, 'O cliente mudou. Atualize o cadastro antes de continuar.')
    previous = db.query(AuditEvent).filter(AuditEvent.action == 'customer_history_reconciled',
        AuditEvent.entity_id == str(customer.id), AuditEvent.changes['preview_token'].as_string() == expected_token).first()
    if previous:
        return {'linked': previous.changes['linked'], 'already_applied': True,
                'limited': bool(previous.changes.get('limited'))}
    preview, planned = _customer_link_plan(db, customer, limit)
    if not hmac.compare_digest(preview['token'], expected_token):
        raise HTTPException(409, 'Os cadastros ou vínculos mudaram. Gere uma nova prévia.')
    # Follow the existing lock order: addresses, parent orders, then parcels.
    parents = {row.pedido_id for kind, row, _ in planned if kind == 'tracking' and row.pedido_id}
    parents.update(row.id for kind, row, _ in planned if kind == 'order')
    if parents:
        db.query(Pedido).filter(Pedido.id.in_(parents)).order_by(Pedido.id).populate_existing().with_for_update().all()
    for kind, model in [('address', SavedAddress), ('pdv_account', PdvCliente), ('tracking', Rastreamento)]:
        ids = [row.id for row_kind, row, _ in planned if row_kind == kind]
        if ids:
            db.query(model).filter(model.id.in_(ids)).order_by(model.id).populate_existing().with_for_update().all()
    preview, planned = _customer_link_plan(db, customer, limit)
    if not hmac.compare_digest(preview['token'], expected_token):
        raise HTTPException(409, 'Os cadastros ou vínculos mudaram. Gere uma nova prévia.')
    for kind, row, reason in planned:
        if kind == 'pdv_account':
            row.cadastro_cliente_id = customer.id
        else:
            row.cliente_id = customer.id
        if kind == 'address':
            row.customer_link_review = False
            row.customer_link_reason = reason
            row.version += 1
    record(db, 'customer_history_reconciled', 'clientes', entity='clientes', entity_id=str(customer.id),
        user_id=actor.id, actor_name=actor.nome,
        changes={'preview_token': expected_token, 'linked': preview['counts'], 'limited': preview['limited'],
                 'links': [{'kind': kind, 'id': str(row.id), 'reason': reason} for kind, row, reason in planned]})
    db.flush()
    return {'linked': preview['counts'], 'already_applied': False, 'limited': preview['limited']}
