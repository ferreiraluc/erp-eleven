"""Explicit, reviewable address consolidation; never scans for automatic merges."""
import hashlib
import json

from fastapi import HTTPException

from ..models.address_book import SavedAddress
from ..models.assistant import utcnow
from .address_book import address_family, compatible, lock_addresses, resolve_address
from .address_identity import fingerprint, matches_known_variants, matches_optional_district
from .address_usage import usage_stats


def equivalent(left, right):
    key = fingerprint(left)
    return bool(key and key == fingerprint(right)) or matches_optional_district(left, right) or matches_known_variants(left, right)


def _snapshot(row):
    return {'id': str(row.id), 'version': row.version, 'data': row.data, 'label': row.label,
            'active': row.active, 'cliente_id': str(row.cliente_id) if row.cliente_id else None,
            'pdv_cliente_id': str(row.pdv_cliente_id) if row.pdv_cliente_id else None}


def merge_addresses(db, target_id, source_id, *, apply=False, expected_plan=None):
    """Plan or apply one explicit pair, preserving IDs and historical snapshots.

    Applying requires the exact token returned by a prior dry-run. The caller
    owns commit/rollback. A stale plan, incompatible document/customer or a third
    compatible root fails before any write.
    """
    if target_id == source_id:
        raise HTTPException(409, 'Escolha dois cadastros de endereço diferentes.')
    lock_addresses(db)
    rows = db.query(SavedAddress).filter(SavedAddress.id.in_([target_id, source_id])).order_by(
        SavedAddress.id).with_for_update().populate_existing().all()
    by_id = {row.id: row for row in rows}
    target, source = by_id.get(target_id), by_id.get(source_id)
    if not target or not source:
        raise HTTPException(404, 'Endereço não encontrado.')
    if target.merged_into_id:
        raise HTTPException(409, 'O destino já foi consolidado. Escolha o cadastro principal atual.')
    if source.merged_into_id:
        resolved = resolve_address(db, source.id)
        if resolved and resolved.id == target.id:
            return {'state': 'already_merged', 'target_id': str(target.id), 'source_id': str(source.id)}
        raise HTTPException(409, 'A origem já foi consolidada em outro endereço.')
    if not equivalent(target.data, source.data):
        raise HTTPException(409, 'Os cadastros não representam o mesmo destinatário e local de entrega.')
    compatible(target, source.data, source.cliente_id, source.pdv_cliente_id)
    data = dict(target.data)
    added = []
    for field, value in source.data.items():
        if value and not data.get(field):
            data[field] = value
            added.append(field)
    for other in db.query(SavedAddress).filter(
        SavedAddress.merged_into_id.is_(None), SavedAddress.id.notin_([target.id, source.id]),
    ).with_for_update():
        if equivalent(data, other.data):
            raise HTTPException(409, 'Há outro endereço compatível fora do par escolhido. Revise os cadastros antes de consolidar.')
    token = hashlib.sha256(json.dumps(
        {'target': _snapshot(target), 'source': _snapshot(source)},
        ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    history = usage_stats(db, address_family(db, target) | address_family(db, source))
    result = {'state': 'ready', 'target_id': str(target.id), 'source_id': str(source.id),
              'target_version': target.version, 'source_version': source.version,
              'fields_added': sorted(added), 'plan_token': token,
              'target_has_document': bool(target.data.get('cpf')), 'source_has_document': bool(source.data.get('cpf')),
              'history_total': history['total'], 'history_prints': history['prints'], 'history_quotes': history['quotes']}
    if not apply:
        return result
    if not expected_plan or expected_plan != token:
        raise HTTPException(409, 'O plano não foi confirmado ou os cadastros mudaram. Execute a simulação novamente.')

    # Clear the source's unique key before enriching the target. Existing links
    # to the source and its older aliases continue resolving through the chain.
    active = target.active or source.active
    source.merged_into_id = target.id
    source.active = False
    source.version += 1
    source.updated_at = utcnow()
    db.flush()
    target.data = data
    if not target.cliente_id and not target.pdv_cliente_id:
        target.cliente_id, target.pdv_cliente_id = source.cliente_id, source.pdv_cliente_id
    target.active = active
    target.version += 1
    target.updated_at = utcnow()
    db.flush()
    return {**result, 'state': 'merged', 'target_version': target.version, 'source_version': source.version}
