"""Reviewed editable copies, isolated from the original item's balances and history."""
import hashlib
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text
from ..models.inventory import Item, Supplier
from .inventory_variants import source_item, source_version, normalized
from .inventory_service import create_movement
from .inventory_taxonomy import key as taxonomy_key


def lock(db, key):
    if db.bind.dialect.name == 'postgresql':
        value = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'big', signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': value})


def duplicate_item(db, item_id, request, user_id):
    # Stable identity + payload fingerprint allow safe retries after a lost response.
    identity = uuid.uuid5(uuid.NAMESPACE_URL, f'eleven:duplicate:{user_id}:{item_id}:{request.request_id}')
    fingerprint = hashlib.sha256(json.dumps(request.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    sku = 'INV-DUP-' + fingerprint[:40]
    try:
        lock(db, f'inventory-copy:{identity}')
        prior = db.get(Item, identity)
        if prior:
            if prior.sku_internal != sku or prior.deleted_at is not None:
                raise HTTPException(409, 'Esta confirmação já foi utilizada. Reabra o cadastro para continuar.')
            db.commit()
            return prior
        source = source_item(db, item_id)
        group = source.group_key
        # Share the lock namespace with the existing Add grade operation.
        lock(db, f'inventory-variants:{group or item_id}')
        members = db.query(Item).filter(Item.deleted_at.is_(None))
        members = members.filter(Item.group_key == group) if group else members.filter(Item.id == item_id)
        members = members.order_by(Item.id).with_for_update().populate_existing().all()
        source = next((row for row in members if row.id == item_id), None)
        if source is None or not source.is_active or source.group_key != group or source_version(source) != request.source_version:
            raise HTTPException(409, 'Os dados do produto mudaram. Reabra a prévia e confira novamente.')
        data = request.item.model_dump(exclude={'group_key'})
        data['size'] = ' '.join((data['size'] or '').split()).upper() or None
        if data['supplier_id'] and not db.get(Supplier, data['supplier_id']):
            raise HTTPException(422, 'Fornecedor não encontrado.')
        if data['max_stock'] and data['min_stock'] > data['max_stock']:
            raise HTTPException(422, 'Mínimo não pode ser maior que máximo')
        if request.keep_group:
            if any(normalized(row.size) == normalized(data['size']) and taxonomy_key(row.color, 'color') == taxonomy_key(data['color'], 'color') for row in members):
                raise HTTPException(409, 'Este tamanho e cor já existem na grade. Escolha outra variação ou crie um produto independente.')
            source.group_key = group or f'grade-{uuid.uuid4()}'
            data['group_key'] = source.group_key
        row = Item(**data, id=identity, sku_internal=sku, created_by=user_id,
                   current_stock=0, stock_loja=0, stock_deposito=0)
        db.add(row)
        db.flush()
        if request.initial_stock:
            create_movement(db, row.id, 'entry', request.initial_stock, user_id,
                            reason='Estoque inicial — cópia de produto conferida', reference_type='inventory_duplicate',
                            reference_id=str(item_id), location=request.stock_location)
        db.commit()
        return row
    except Exception:
        db.rollback()
        raise
