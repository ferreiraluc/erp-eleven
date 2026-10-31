"""Audited reconciliation of explicit links and unique, corroborated identities."""
import hashlib
import hmac
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from ..models.cliente import Cliente
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento
from ..models.address_book import FreightOrder, SavedAddress
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


def _freight_recipient(payload):
    recipient = payload.get('to') if isinstance(payload, dict) else None
    if not isinstance(recipient, dict):
        return None
    fields = {'name': 'nome', 'document': 'cpf', 'address': 'endereco', 'number': 'numero',
              'district': 'bairro', 'complement': 'complemento', 'city': 'cidade',
              'state_abbr': 'estado', 'postal_code': 'cep'}
    return {'pais': 'BR', **{field: recipient.get(key) or '' for key, field in fields.items()}}


def _freight_tracking_evidence(db, parcels, customer, customers, eligible, limit, public, inspected):
    """Bounded historical proof, including every dependency in the reviewed token."""
    from ..models.pdv import PdvCliente
    from .address_identity import equivalent, normalized
    from .customer_documents import customer_documents, documents_conflict, input_documents, unique_documents
    from .customer_identity import compatible_name, customer_identity_groups
    from .tracking_codes import normalize_tracking_code, tracking_code_expression

    dependencies = {FreightOrder: set(), SavedAddress: set(), PdvCliente: set()}
    if not parcels:
        return {}, dependencies
    codes = {normalize_tracking_code(row.codigo_rastreio) for row in parcels}
    rows = db.query(FreightOrder).filter(FreightOrder.environment == 'production',
        FreightOrder.state.in_(('released', 'posted', 'delivered')),
        tracking_code_expression(FreightOrder.tracking).in_(codes),
    ).order_by(FreightOrder.id).limit(limit + 1).populate_existing().all()
    complete = len(rows) <= limit
    rows = rows[:limit]
    public['scanned'] += len(rows)
    dependencies[FreightOrder].update(row.id for row in rows)
    # Do not read PDFs while producing a digest of identity evidence.
    inspected.extend({'freight_id': str(row.id), 'address_id': str(row.address_id),
        'environment': row.environment, 'state': row.state, 'tracking': row.tracking,
        'payload': row.payload} for row in rows)

    addresses = {}
    pending = {row.address_id for row in rows if row.address_id}
    while pending and len(addresses) < limit:
        found = db.query(SavedAddress).filter(SavedAddress.id.in_(pending)).order_by(SavedAddress.id).limit(
            limit - len(addresses) + 1).populate_existing().all()
        if len(found) > limit - len(addresses):
            complete = False
        found = found[:limit - len(addresses)]
        addresses.update((row.id, row) for row in found)
        public['scanned'] += len(found)
        inspected.extend(_identity_snapshot(row) for row in found)
        pending = {row.merged_into_id for row in found if row.merged_into_id and row.merged_into_id not in addresses}
    if pending:
        complete = False
    dependencies[SavedAddress].update(addresses)
    account_ids = {row.pdv_cliente_id for row in addresses.values() if row.pdv_cliente_id}
    accounts = db.query(PdvCliente).filter(PdvCliente.id.in_(account_ids)).order_by(PdvCliente.id).limit(limit + 1).populate_existing().all() if account_ids else []
    if len(accounts) > limit:
        complete = False
    accounts = {row.id: row for row in accounts[:limit]}
    public['scanned'] += len(accounts)
    inspected.extend(_identity_snapshot(row) for row in accounts.values())
    dependencies[PdvCliente].update(accounts)
    if not complete:
        public['limited'] = True
        return {code: None for code in codes}, dependencies

    _, groups = customer_identity_groups(customers)
    owners = {row.id: owner for owner, members in groups.items() for row in members}
    identities = groups[customer.id]
    documents = unique_documents(doc for row in identities for doc in customer_documents(row))

    def valid_identity(data):
        return bool(data and any(compatible_name(data.get('nome'), row.nome) for row in identities)
                    and not documents_conflict(documents, input_documents(data)))

    def one_freight(row):
        data = _freight_recipient(row.payload)
        if not valid_identity(data):
            return None
        explicit = False
        location_proof = False
        captured = row.payload.get('_customer_id')
        if captured is not None:
            try:
                owner = owners.get(UUID(str(captured)))
            except (ValueError, TypeError):
                return None
            if owner != customer.id:
                return None
            explicit = True
        address = addresses.get(row.address_id) if row.address_id else None
        if row.address_id and not address:
            return None
        seen = set()
        while address and address.merged_into_id:
            if address.id in seen:
                return None
            seen.add(address.id)
            address = addresses.get(address.merged_into_id)
            if not address:
                return None
        if address:
            if not valid_identity(address.data) or documents_conflict(input_documents(address.data), input_documents(data)):
                return None
            direct = owners.get(address.cliente_id) if address.cliente_id else None
            account = accounts.get(address.pdv_cliente_id) if address.pdv_cliente_id else None
            linked = owners.get(account.cadastro_cliente_id) if account and account.cadastro_cliente_id else None
            if (address.cliente_id and direct != customer.id) or (address.pdv_cliente_id and not account):
                return None
            if account and ((account.cadastro_cliente_id and linked != customer.id) or
                            documents_conflict(documents, input_documents(pdv_identity_data(account)))):
                return None
            explicit = explicit or direct == customer.id or linked == customer.id
            # Complete snapshots must agree with the saved delivery location.
            # For older partial snapshots, every supplied shared field must agree.
            if data.get('endereco') and data.get('numero'):
                if not equivalent({**data, 'nome': address.data.get('nome')}, address.data):
                    return None
                location_proof = True
            elif any(data.get(field) and address.data.get(field) and
                     normalized(data[field]) != normalized(address.data[field])
                     for field in ('endereco', 'numero', 'complemento', 'cidade', 'estado', 'cep')):
                return None
        reason = eligible(data)
        if '_customer_id' in row.payload and captured is None and not reason and not (explicit and location_proof):
            return None
        if explicit:
            return 'explicit_freight_customer'
        return 'freight_' + reason if reason else None

    evidence = {}
    for row in rows:
        code = normalize_tracking_code(row.tracking)
        reason = one_freight(row)
        # Two providers' records for one code must not let one positive match
        # hide contradictory evidence. A missing/invalid proof blocks that code.
        if code not in evidence:
            evidence[code] = reason
        elif not reason:
            evidence[code] = None
    return evidence, dependencies


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
    dependencies = {}
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
        from .tracking_codes import normalize_tracking_code
        freight_evidence, dependencies = _freight_tracking_evidence(db,
            [row for row in parcels if name_key(row.destinatario) in names],
            customer, customers, eligible, limit, public, inspected)
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
            code = normalize_tracking_code(row.codigo_rastreio)
            if code in freight_evidence:
                reason = freight_evidence[code]
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
    return public, planned, dependencies


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
    preview, planned, dependencies = _customer_link_plan(db, customer, limit)
    if not hmac.compare_digest(preview['token'], expected_token):
        raise HTTPException(409, 'Os cadastros ou vínculos mudaram. Gere uma nova prévia.')
    # Provider refreshes lock a freight before its parent/parcel. Preserve that
    # order while protecting the snapshots used as proof by this confirmation.
    freight_ids = dependencies.get(FreightOrder, set())
    if freight_ids:
        db.query(FreightOrder).filter(FreightOrder.id.in_(freight_ids)).order_by(FreightOrder.id).populate_existing().with_for_update().all()
    # Follow the existing lock order: addresses, parent orders, then parcels.
    parents = {row.pedido_id for kind, row, _ in planned if kind == 'tracking' and row.pedido_id}
    parents.update(row.id for kind, row, _ in planned if kind == 'order')
    if parents:
        db.query(Pedido).filter(Pedido.id.in_(parents)).order_by(Pedido.id).populate_existing().with_for_update().all()
    for kind, model in [('address', SavedAddress), ('pdv_account', PdvCliente), ('tracking', Rastreamento)]:
        ids = {row.id for row_kind, row, _ in planned if row_kind == kind} | dependencies.get(model, set())
        if ids:
            db.query(model).filter(model.id.in_(ids)).order_by(model.id).populate_existing().with_for_update().all()
    preview, planned, _ = _customer_link_plan(db, customer, limit)
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
