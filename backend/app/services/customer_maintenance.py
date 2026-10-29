"""Explicit pair consolidation: preserve old identities, snapshots and audited links."""
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, text

from ..models.cliente import Cliente
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento
from ..models.address_book import SavedAddress
from ..models.pdv import PdvCliente
from .address_book import lock_addresses
from .customer_identity import name_key, phone_key, document_key
from .customer_documents import customer_documents, documents_conflict
from .user_audit import record


def resolve_customer(db, customer_id):
    row = db.get(Cliente, customer_id) if customer_id else None
    seen = set()
    while row and row.merged_into_id:
        if row.id in seen:
            raise HTTPException(409, 'Referência de cliente inválida. Confira os cadastros.')
        seen.add(row.id)
        row = db.get(Cliente, row.merged_into_id)
    return row


def _snapshot(row):
    return {c.name: str(getattr(row, c.name)) for c in row.__table__.columns}


def merge_customers(db, target_id, source_id, *, apply=False, expected_plan=None, reviewed_conflicts=False):
    if target_id == source_id:
        raise HTTPException(409, 'Escolha dois clientes diferentes.')
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
    lock_addresses(db)
    if db.bind.dialect.name == 'postgresql':
        # Short maintenance transaction. Readers continue; parallel writes cannot
        # change the reviewed relationships while the pair is consolidated.
        db.execute(text('LOCK TABLE clientes, pedidos, rastreamentos, saved_addresses, pdv_clientes IN SHARE ROW EXCLUSIVE MODE'))
    pair = db.query(Cliente).filter(Cliente.id.in_([target_id, source_id])).order_by(Cliente.id).with_for_update().populate_existing().all()
    by_id = {row.id: row for row in pair}
    target, source = by_id.get(target_id), by_id.get(source_id)
    if not target or not source:
        raise HTTPException(404, 'Cliente não encontrado.')
    if target.merged_into_id:
        raise HTTPException(409, 'O destino já foi consolidado. Use o cliente principal.')
    if source.merged_into_id:
        principal = resolve_customer(db, source.id)
        if principal and principal.id == target.id:
            return {'state': 'already_merged', 'target_id': str(target.id), 'source_id': str(source.id)}
        raise HTTPException(409, 'A origem já foi consolidada em outro cliente.')
    target_name, source_name = set(name_key(target.nome).split()), set(name_key(source.nome).split())
    if not target_name or not source_name or not (target_name <= source_name or source_name <= target_name):
        raise HTTPException(409, 'Os nomes não correspondem. Revise a identidade antes de consolidar.')
    conflicts = []
    for field, normalize in [('cpf', document_key), ('telefone', phone_key), ('email', lambda v: str(v or '').strip().casefold())]:
        a, b = normalize(getattr(target, field)), normalize(getattr(source, field))
        if a and b and a != b:
            conflicts.append(field)
    if 'cpf' not in conflicts and documents_conflict(customer_documents(target), customer_documents(source)):
        conflicts.append('documentos')
    orders = db.query(Pedido).filter(Pedido.cliente_id.in_([target.id, source.id])).order_by(Pedido.id).with_for_update().all()
    order_ids = [row.id for row in orders]
    shipments = db.query(Rastreamento).filter(or_(Rastreamento.cliente_id.in_([target.id, source.id]),
        Rastreamento.pedido_id.in_(order_ids))).order_by(Rastreamento.id).with_for_update().all()
    orders_by_id = {row.id: row for row in orders}
    for shipment in shipments:
        parent = orders_by_id.get(shipment.pedido_id) or (db.get(Pedido, shipment.pedido_id) if shipment.pedido_id else None)
        if shipment.cliente_id and shipment.cliente_id not in by_id:
            raise HTTPException(409, 'Um pedido possui rastreio vinculado a outro cliente fora do par.')
        if parent and parent.cliente_id and parent.cliente_id not in by_id:
            raise HTTPException(409, 'Um rastreio pertence a pedido de outro cliente fora do par.')
    addresses = db.query(SavedAddress).filter(SavedAddress.cliente_id.in_([target.id, source.id])).order_by(SavedAddress.id).with_for_update().all()
    pdv_customers = db.query(PdvCliente).filter(PdvCliente.cadastro_cliente_id.in_([target.id, source.id])).order_by(PdvCliente.id).with_for_update().all()
    token = hashlib.sha256(json.dumps({'customers': [_snapshot(r) for r in pair],
        'orders': [_snapshot(r) for r in orders], 'shipments': [_snapshot(r) for r in shipments],
        'addresses': [_snapshot(r) for r in addresses], 'pdv_customers': [_snapshot(r) for r in pdv_customers]}, sort_keys=True).encode()).hexdigest()
    added = [field for field in ('telefone', 'email', 'cpf', 'endereco') if not getattr(target, field) and getattr(source, field)]
    moved = {'orders': sum(r.cliente_id == source.id for r in orders),
             'tracking': sum(r.cliente_id != target.id for r in shipments),
             'addresses': sum(r.cliente_id == source.id for r in addresses)}
    if pdv_customers:
        moved['pdv_customers'] = sum(r.cadastro_cliente_id == source.id for r in pdv_customers)
    result = {'state': 'review_conflicts' if conflicts and not reviewed_conflicts else 'ready',
        'target_id': str(target.id), 'source_id': str(source.id), 'plan_token': token,
        'conflicting_fields': conflicts, 'fields_added': added, 'links_to_move': moved,
        'history': {'orders': len(orders), 'tracking': len(shipments), 'addresses': len(addresses)}}
    if not apply:
        return result
    if not expected_plan or expected_plan != token:
        raise HTTPException(409, 'Os cadastros ou vínculos mudaram. Gere uma nova simulação.')
    if conflicts and not reviewed_conflicts:
        raise HTTPException(409, 'Documentos ou contatos divergem. Confirme qual cadastro contém os dados corretos antes de unir.')
    # Source remains intact for traceability. A unique CPF must not be copied while
    # still owned by the historical row; choose that row as target instead.
    if 'cpf' in added:
        raise HTTPException(409, 'Escolha como principal o cadastro que já possui CPF para preservar o documento único.')
    for field in added:
        setattr(target, field, getattr(source, field))
    for row in orders:
        row.cliente_id = target.id
    for row in shipments:
        row.cliente_id = target.id
    for row in addresses:
        if row.cliente_id != target.id:
            row.cliente_id = target.id
            row.version += 1
    # Preserve distinct PDV accounts, sale snapshots and fiado balances. A
    # directory consolidation only moves their explicit directory link.
    for row in pdv_customers:
        row.cadastro_cliente_id = target.id
    target.ativo = bool(target.ativo or source.ativo)
    source.ativo = False
    source.merged_into_id = target.id
    record(db, 'customer_merged', 'clientes', entity='clientes', entity_id=str(target.id),
           changes={'source_id': str(source.id), 'target_id': str(target.id), 'fields_added': added,
                    'reviewed_conflicts': conflicts if reviewed_conflicts else [], 'links_moved': moved})
    db.flush()
    return {**result, 'state': 'merged'}


def _selection_ids(target_id, source_ids):
    """A selection is an unordered group with an explicitly chosen principal."""
    try:
        target = UUID(str(target_id))
        sources = [UUID(str(value)) for value in source_ids]
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Selecione clientes válidos.')
    if not 1 <= len(sources) <= 19 or len(set(sources)) != len(sources) or target in sources:
        raise HTTPException(422, 'Selecione de 2 a 20 clientes diferentes, incluindo o principal.')
    return target, sorted(sources, key=str)


def _selection_description(row, documents=None):
    from .customer_documents import customer_documents
    return {
        'id': str(row.id), 'name': row.nome,
        'details': ' · '.join(value for value in (row.telefone, row.email, row.cpf, row.endereco) if value),
        'cpf': row.cpf, 'telefone': row.telefone, 'email': row.email, 'endereco': row.endereco,
        'documents': customer_documents(row) if documents is None else documents,
    }


def _selection_identity_members(db, customers):
    """Follow every confirmed alias under the same maintenance/table locks."""
    members = {row.id: [row] for row in customers}
    owners = {row.id: row.id for row in customers}
    frontier = list(owners)
    while frontier:
        aliases = db.query(Cliente).filter(Cliente.merged_into_id.in_(frontier)).order_by(Cliente.id).with_for_update().populate_existing().all()
        following = []
        for alias in aliases:
            if alias.id in owners:
                raise HTTPException(409, 'Referência de cliente inválida. Confira os cadastros.')
            owner_id = owners[alias.merged_into_id]
            owners[alias.id] = owner_id
            members[owner_id].append(alias)
            following.append(alias.id)
        frontier = following
    return members, owners


def merge_customer_selection(db, target_id, source_ids, *, apply=False, expected_plan=None,
                             reviewed_conflicts=False):
    """Owner-reviewed group consolidation, one locked transaction and one preview.

    A human may confirm spelling errors and different names. Divergent populated
    identities are shown separately and require a second explicit acknowledgement.
    Original rows retain their documents (including unique CPF) and snapshots;
    only directory relationships move, never PDV accounts or financial balances.
    """
    from .customer_documents import customer_documents, unique_documents

    target_id, source_ids = _selection_ids(target_id, source_ids)
    selected_ids = [target_id, *source_ids]
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
    lock_addresses(db)
    if db.bind.dialect.name == 'postgresql':
        # Use the same order as the existing pair maintenance and identity writers.
        db.execute(text('LOCK TABLE clientes, pedidos, rastreamentos, saved_addresses, pdv_clientes IN SHARE ROW EXCLUSIVE MODE'))
    customers = db.query(Cliente).filter(Cliente.id.in_(selected_ids)).order_by(Cliente.id).with_for_update().populate_existing().all()
    by_id = {row.id: row for row in customers}
    if len(by_id) != len(selected_ids):
        raise HTTPException(404, 'Um dos clientes não foi encontrado. Atualize a seleção.')
    target = by_id[target_id]
    sources = [by_id[source_id] for source_id in source_ids]
    if target.merged_into_id:
        raise HTTPException(409, 'O principal já foi unificado. Atualize a seleção.')
    aliases = [source for source in sources if source.merged_into_id]
    if aliases:
        principals = [resolve_customer(db, row.id) for row in aliases]
        if len(aliases) == len(sources) and all(principal and principal.id == target.id for principal in principals):
            return {'state': 'already_merged', 'target_id': str(target.id), 'source_ids': [str(value) for value in source_ids]}
        raise HTTPException(409, 'A seleção contém um cliente já unificado. Atualize a seleção e confira uma nova prévia.')

    members, identity_owners = _selection_identity_members(db, customers)
    identity_ids = list(identity_owners)
    existing_aliases = sorted((row for rows in members.values() for row in rows if row.id not in by_id), key=lambda row: str(row.id))
    identity_documents = {key: unique_documents(document for row in rows for document in customer_documents(row))
                          for key, rows in members.items()}

    # Include all links, not just counts: adding/reassigning a row invalidates the
    # preview even when another row happens to leave and the total stays equal.
    orders = db.query(Pedido).filter(Pedido.cliente_id.in_(identity_ids)).order_by(Pedido.id).with_for_update().all()
    order_ids = [row.id for row in orders]
    shipments = db.query(Rastreamento).filter(or_(Rastreamento.cliente_id.in_(identity_ids),
        Rastreamento.pedido_id.in_(order_ids))).order_by(Rastreamento.id).with_for_update().all()
    orders_by_id = {row.id: row for row in orders}
    for shipment in shipments:
        parent = orders_by_id.get(shipment.pedido_id) or (db.get(Pedido, shipment.pedido_id) if shipment.pedido_id else None)
        if shipment.cliente_id and shipment.cliente_id not in identity_owners:
            raise HTTPException(409, 'Um pedido possui rastreio vinculado a outro cliente fora da seleção.')
        if parent and parent.cliente_id and parent.cliente_id not in identity_owners:
            raise HTTPException(409, 'Um rastreio pertence a pedido de outro cliente fora da seleção.')
    addresses = db.query(SavedAddress).filter(SavedAddress.cliente_id.in_(identity_ids)).order_by(SavedAddress.id).with_for_update().all()
    pdv_customers = db.query(PdvCliente).filter(PdvCliente.cadastro_cliente_id.in_(identity_ids)).order_by(PdvCliente.id).with_for_update().all()
    token = hashlib.sha256(json.dumps({
        'target_id': str(target_id), 'source_ids': [str(value) for value in source_ids],
        'customers': [_snapshot(row) for row in customers], 'orders': [_snapshot(row) for row in orders],
        'aliases': [_snapshot(row) for row in existing_aliases],
        'shipments': [_snapshot(row) for row in shipments], 'addresses': [_snapshot(row) for row in addresses],
        'pdv_customers': [_snapshot(row) for row in pdv_customers],
    }, sort_keys=True).encode()).hexdigest()

    normalizers = {'telefone': phone_key, 'email': lambda value: str(value or '').strip().casefold()}
    conflicts_by_source = {row.id: set() for row in sources}
    for source in sources:
        if name_key(source.nome) != name_key(target.nome):
            conflicts_by_source[source.id].add('nome')
    # Conflicts also include two sources with different values while the chosen
    # target has no value. Choosing an empty principal must not hide divergence.
    for field, normalize in normalizers.items():
        values = {normalize(getattr(row, field)) for row in [target, *sources] if normalize(getattr(row, field))}
        if len(values) > 1:
            for source in sources:
                if normalize(getattr(source, field)):
                    conflicts_by_source[source.id].add(field)
    documents_by_kind = {}
    for row in [target, *sources]:
        for document in identity_documents[row.id]:
            key = (document['tipo'], document['pais'], document.get('emissor', ''))
            documents_by_kind.setdefault(key, set()).add(document['numero'])
    for source in sources:
        for document in identity_documents[source.id]:
            key = (document['tipo'], document['pais'], document.get('emissor', ''))
            if len(documents_by_kind[key]) > 1:
                conflicts_by_source[source.id].add('cpf' if document['tipo'] == 'CPF' else 'documentos')
    conflicts = [{'source_id': str(row.id), 'fields': sorted(conflicts_by_source[row.id])}
                 for row in sources if conflicts_by_source[row.id]]
    conflicting_fields = sorted({field for row in conflicts for field in row['fields']})
    # Unique CPF is deliberately never copied from a historical alias. Identity
    # resolution recognizes its retained, owner-confirmed document on the alias.
    additions = {field: next((getattr(row, field) for row in sources if getattr(row, field)), None)
                 for field in ('telefone', 'email', 'endereco') if not getattr(target, field)}
    additions = {field: value for field, value in additions.items() if value}
    moved = {
        'orders': sum(row.cliente_id != target.id for row in orders),
        'tracking': sum(row.cliente_id != target.id for row in shipments),
        'addresses': sum(row.cliente_id != target.id for row in addresses),
        'pdv_customers': sum(row.cadastro_cliente_id != target.id for row in pdv_customers),
    }
    result = {
        'state': 'review_conflicts' if conflicts else 'ready', 'target_id': str(target.id),
        'source_ids': [str(value) for value in source_ids], 'plan_token': token,
        'customers': [_selection_description(row, identity_documents[row.id]) for row in [target, *sources]],
        'conflicting_fields': conflicting_fields, 'conflicts': conflicts,
        'requires_reviewed_conflicts': bool(conflicts), 'fields_added': sorted(additions),
        'links_to_move': moved,
        'history': {'orders': len(orders), 'tracking': len(shipments), 'addresses': len(addresses), 'pdv_customers': len(pdv_customers)},
    }
    if not apply:
        return result
    if not expected_plan or expected_plan != token:
        raise HTTPException(409, 'Os cadastros ou vínculos mudaram. Confira uma nova prévia.')
    if conflicts and not reviewed_conflicts:
        raise HTTPException(409, 'Nomes, documentos ou contatos divergem. Confirme expressamente que os cadastros são da mesma pessoa.')
    for field, value in additions.items():
        setattr(target, field, value)
    for row in orders:
        row.cliente_id = target.id
    for row in shipments:
        row.cliente_id = target.id
    for row in addresses:
        if row.cliente_id != target.id:
            row.cliente_id = target.id
            row.version += 1
    for row in pdv_customers:
        row.cadastro_cliente_id = target.id
    target.ativo = bool(target.ativo or any(source.ativo for source in sources))
    for source in sources:
        source.ativo = False
        source.merged_into_id = target.id
    record(db, 'customers_merged', 'clientes', entity='clientes', entity_id=str(target.id),
           changes={'source_ids': [str(value) for value in source_ids], 'target_id': str(target.id),
                    'fields_added': sorted(additions), 'reviewed_conflicts': conflicting_fields if reviewed_conflicts else [],
                    'links_moved': moved})
    db.flush()
    return {**result, 'state': 'merged'}
