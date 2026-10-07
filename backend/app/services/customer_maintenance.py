"""Explicit pair consolidation: preserve old identities, snapshots and audited links."""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import or_, text

from ..models.cliente import Cliente
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento
from ..models.address_book import SavedAddress
from .address_book import lock_addresses
from .customer_identity import name_key, phone_key, document_key
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
        db.execute(text('LOCK TABLE clientes, pedidos, rastreamentos, saved_addresses IN SHARE ROW EXCLUSIVE MODE'))
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
    token = hashlib.sha256(json.dumps({'customers': [_snapshot(r) for r in pair],
        'orders': [_snapshot(r) for r in orders], 'shipments': [_snapshot(r) for r in shipments],
        'addresses': [_snapshot(r) for r in addresses]}, sort_keys=True).encode()).hexdigest()
    added = [field for field in ('telefone', 'email', 'cpf', 'endereco') if not getattr(target, field) and getattr(source, field)]
    moved = {'orders': sum(r.cliente_id == source.id for r in orders),
             'tracking': sum(r.cliente_id != target.id for r in shipments),
             'addresses': sum(r.cliente_id == source.id for r in addresses)}
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
    target.ativo = bool(target.ativo or source.ativo)
    source.ativo = False
    source.merged_into_id = target.id
    record(db, 'customer_merged', 'clientes', entity='clientes', entity_id=str(target.id),
           changes={'source_id': str(source.id), 'target_id': str(target.id), 'fields_added': added,
                    'reviewed_conflicts': conflicts if reviewed_conflicts else [], 'links_moved': moved})
    db.flush()
    return {**result, 'state': 'merged'}
