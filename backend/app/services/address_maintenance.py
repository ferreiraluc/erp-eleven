"""Explicit, reviewable address consolidation; never scans for automatic merges."""
import hashlib
import json

from fastapi import HTTPException

from ..models.address_book import SavedAddress
from ..models.assistant import utcnow
from .address_book import address_family, compatible, lock_addresses, resolve_address
from .address_identity import equivalent
from .address_usage import usage_stats


def _snapshot(row):
    return {'id': str(row.id), 'version': row.version, 'data': row.data, 'label': row.label,
            'active': row.active, 'cliente_id': str(row.cliente_id) if row.cliente_id else None,
            'pdv_cliente_id': str(row.pdv_cliente_id) if row.pdv_cliente_id else None}


def merge_addresses(db, target_id, source_id, *, additional_source_ids=(), apply=False, expected_plan=None):
    """Plan or apply an explicit group, preserving IDs and historical snapshots.

    Applying requires the exact token returned by a prior dry-run. The caller
    owns commit/rollback. A stale plan, incompatible document/customer or an
    unreviewed compatible root outside the group fails before any write.
    """
    source_ids = [source_id, *sorted(additional_source_ids, key=str)]
    if target_id in source_ids or len(set(source_ids)) != len(source_ids):
        raise HTTPException(409, 'Escolha dois cadastros de endereço diferentes.')
    if len(source_ids) > 20:
        raise HTTPException(409, 'Revise no máximo 20 duplicatas por consolidação.')
    lock_addresses(db)
    rows = db.query(SavedAddress).filter(SavedAddress.id.in_([target_id, *source_ids])).order_by(
        SavedAddress.id).with_for_update().populate_existing().all()
    by_id = {row.id: row for row in rows}
    target = by_id.get(target_id)
    sources = [by_id.get(key) for key in source_ids]
    if not target or any(source is None for source in sources):
        raise HTTPException(404, 'Endereço não encontrado.')
    source = sources[0]
    if target.merged_into_id:
        raise HTTPException(409, 'O destino já foi consolidado. Escolha o cadastro principal atual.')
    if any(row.merged_into_id for row in sources):
        resolved = [resolve_address(db, row.id) for row in sources]
        if all(row and row.id == target.id for row in resolved):
            return {'state': 'already_merged', 'target_id': str(target.id), 'source_id': str(source.id),
                    'source_ids': [str(key) for key in source_ids]}
        raise HTTPException(409, 'Uma origem já foi consolidada. Revise o grupo antes de continuar.')
    # Require pairwise agreement: a missing document, phone or abbreviated
    # reference in one row must not bridge two conflicting destinations.
    group = [target, *sources]
    for index, left in enumerate(group):
        for right in group[index + 1:]:
            if not equivalent(left.data, right.data):
                raise HTTPException(409, 'Os cadastros não representam o mesmo destinatário e local de entrega.')
            compatible(left, right.data, right.cliente_id, right.pdv_cliente_id)
    data = dict(target.data)
    added = set()
    for row in sources:
        for field, value in row.data.items():
            if value and not data.get(field):
                data[field] = value
                added.add(field)
    for other in db.query(SavedAddress).filter(
        SavedAddress.merged_into_id.is_(None), SavedAddress.id.notin_([target_id, *source_ids]),
    ).with_for_update():
        if equivalent(data, other.data) or any(equivalent(row.data, other.data) for row in group):
            raise HTTPException(409, 'Há outro endereço compatível fora do grupo escolhido. Revise os cadastros antes de consolidar.')
    token = hashlib.sha256(json.dumps(
        {'target': _snapshot(target), 'sources': [_snapshot(row) for row in sources]},
        ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    family = set().union(*(address_family(db, row) for row in group))
    history = usage_stats(db, family)
    result = {'state': 'ready', 'target_id': str(target.id), 'source_id': str(source.id),
              'source_ids': [str(key) for key in source_ids],
              'sources': [{'id': str(row.id), 'version': row.version, 'has_document': bool(row.data.get('cpf'))}
                          for row in sources],
              'target_version': target.version, 'source_version': source.version,
              'fields_added': sorted(added), 'plan_token': token,
              'target_has_document': bool(target.data.get('cpf')), 'source_has_document': bool(source.data.get('cpf')),
              'history_total': history['total'], 'history_prints': history['prints'], 'history_quotes': history['quotes']}
    if not apply:
        return result
    if not expected_plan or expected_plan != token:
        raise HTTPException(409, 'O plano não foi confirmado ou os cadastros mudaram. Execute a simulação novamente.')

    # Clear source keys before enriching the target. Existing links and all
    # older aliases continue resolving through the chain, without deleting data.
    active = any(row.active for row in group)
    for row in sources:
        row.merged_into_id = target.id
        row.active = False
        row.version += 1
        row.updated_at = utcnow()
    db.flush()
    target.data = data
    for row in sources:
        if not target.cliente_id and not target.pdv_cliente_id:
            target.cliente_id, target.pdv_cliente_id = row.cliente_id, row.pdv_cliente_id
    target.active = active
    target.version += 1
    target.updated_at = utcnow()
    db.flush()
    if db.info.get('audit_actor'):
        from .user_audit import record
        for row in sources:
            record(db, 'address_merged', 'enderecos', entity='saved_addresses', entity_id=str(target.id),
                   changes={'source_id': str(row.id), 'target_id': str(target.id), 'fields_added': sorted(added),
                            'history_total': history['total']})
    return {**result, 'state': 'merged', 'target_version': target.version, 'source_version': source.version}
