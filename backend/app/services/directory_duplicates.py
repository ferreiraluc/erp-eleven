"""Explicit duplicate review, never automatic identity/financial consolidation."""
from collections import defaultdict
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import text
from ..models.cliente import Cliente
from ..models.address_book import SavedAddress
from .customer_identity import name_key, full_name
from .address_identity import equivalent
from .address_book import lock_addresses, compatible
from .customer_maintenance import merge_customers
from .user_audit import record


def candidates(db, kind, search='', limit=25):
    model = Cliente if kind == 'customers' else SavedAddress
    query = db.query(model).filter(model.merged_into_id.is_(None))
    if search:
        pattern = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter((Cliente.nome if kind == 'customers' else SavedAddress.label).ilike(pattern, escape='\\'))
    # An on-demand maintenance read, bounded independently of the live catalog.
    rows = query.order_by(model.id).limit(10001).all()
    groups, output = defaultdict(list), []
    incomplete = len(rows) > 10000
    for row in rows[:10000]:
        name = row.nome if kind == 'customers' else row.data.get('nome')
        if not full_name(name):
            continue
        group = name_key(name)
        if kind == 'addresses':
            group += '|' + name_key(row.data.get('pais')) + '|' + name_key(row.data.get('cidade'))
        previous = groups[group]
        if len(previous) >= 20:
            incomplete = True
            continue
        for other in previous:
            if kind == 'addresses' and not equivalent(row.data, other.data):
                continue
            if len(output) >= limit:
                return {'items': output, 'incomplete': True}
            output.append({'target': describe(other, kind), 'source': describe(row, kind)})
        previous.append(row)
    return {'items': output, 'incomplete': incomplete}


def describe(row, kind):
    if kind == 'customers':
        return {'id': str(row.id), 'name': row.nome,
                'details': ' · '.join(v for v in (row.telefone, row.email, row.cpf, row.endereco) if v)}
    return {'id': str(row.id), 'name': row.label,
            'details': ' · '.join(str(row.data.get(k)) for k in ('nome','endereco','numero','complemento','cidade','cep','telefone','cpf') if row.data.get(k))}


def merge_pair(db, kind, target_id, source_id, *, apply=False, expected_plan=None):
    if kind == 'customers':
        # Existing owner-reviewed operation validates tokens, conflicts and links.
        return merge_customers(db, target_id, source_id, apply=apply, expected_plan=expected_plan)
    if target_id == source_id:
        raise HTTPException(409, 'Escolha dois endereços diferentes.')
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
    lock_addresses(db)
    pair = db.query(SavedAddress).filter(SavedAddress.id.in_([target_id, source_id])).order_by(SavedAddress.id).with_for_update().populate_existing().all()
    by_id = {row.id: row for row in pair}
    target, source = by_id.get(target_id), by_id.get(source_id)
    if not target or not source:
        raise HTTPException(404, 'Endereço não encontrado.')
    if source.merged_into_id == target.id and not target.merged_into_id:
        return {'state': 'already_merged'}
    if target.merged_into_id or source.merged_into_id:
        raise HTTPException(409, 'Um dos endereços já foi consolidado. Atualize a revisão.')
    if not equivalent(target.data, source.data):
        raise HTTPException(409, 'Os destinatários ou locais são diferentes. Nenhum endereço foi unido.')
    compatible(target, source.data, source.cliente_id, source.pdv_cliente_id)
    compatible(source, target.data, target.cliente_id, target.pdv_cliente_id)
    token = hashlib.sha256(json.dumps([{c.name: str(getattr(row,c.name)) for c in row.__table__.columns} for row in pair], sort_keys=True).encode()).hexdigest()
    result = {'state': 'ready', 'plan_token': token, 'target_id': str(target.id), 'source_id': str(source.id),
              'conflicting_fields': [], 'links_to_move': {}, 'fields_added': []}
    if not apply:
        return result
    if not expected_plan or expected_plan != token:
        raise HTTPException(409, 'Os endereços mudaram. Confira uma nova prévia.')
    target.active = bool(target.active or source.active)
    source.merged_into_id = target.id
    source.dedup_key = None
    source.active = False
    source.version += 1
    # Snapshots/jobs/freight remain on their original IDs. History follows aliases.
    if not target.cliente_id and not target.pdv_cliente_id:
        target.cliente_id, target.pdv_cliente_id = source.cliente_id, source.pdv_cliente_id
    target.version += 1
    record(db, 'address_merged', 'clientes', entity='saved_addresses', entity_id=str(target.id),
           changes={'source_id': str(source.id), 'target_id': str(target.id)})
    db.flush()
    return {**result, 'state': 'merged'}
