"""Explicit source-based variants. Never infer product identity from a barcode."""
import hashlib
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.inventory import Item
from ..schemas.inventory_variants import VariantCreateRequest
from .inventory_service import create_movement

COPY_FIELDS = ('description', 'category', 'color', 'brand', 'unit', 'location',
               'supplier_id', 'cost_price', 'sale_price', 'currency', 'cost_currency',
               'sale_currency', 'min_stock', 'max_stock', 'image_data')


def normalized(value):
    return ' '.join((value or '').split()).casefold()


def source_version(source):
    # Group membership and stock can legitimately change after the first request.
    # Excluding them makes retries safe without copying old balances or history.
    data = {key: getattr(source, key) for key in (*COPY_FIELDS, 'id', 'name', 'size', 'barcode', 'is_active', 'deleted_at')}
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def source_item(db, item_id):
    source = db.query(Item).filter(Item.id == item_id, Item.deleted_at.is_(None)).first()
    if source is None:
        raise HTTPException(404, 'Produto não encontrado. Atualize a lista de estoque.')
    if not source.is_active:
        raise HTTPException(409, 'Ative o produto antes de criar outros tamanhos.')
    return source


def same_color_members(db, source):
    rows = db.query(Item).filter(Item.deleted_at.is_(None), Item.group_key == source.group_key).order_by(Item.id).all() if source.group_key else [source]
    return [row for row in rows if normalized(row.color) == normalized(source.color)]


def variant_context(db, item_id):
    source = source_item(db, item_id)
    name = source.name.strip()
    suffix = f' {source.size.strip()}' if source.size else ''
    if suffix and name.casefold().endswith(suffix.casefold()) and len(name) > len(suffix) + 1:
        name = name[:-len(suffix)]
    return dict(source=source, source_version=source_version(source), model_name=name,
                existing=same_color_members(db, source))


def create_variants(db: Session, item_id, request: VariantCreateRequest, user_id):
    try:
        source = source_item(db, item_id)
        original_group = source.group_key
        if db.bind.dialect.name == 'postgresql':
            # Different source sizes of the same group serialize the missing-size check.
            lock = int.from_bytes(hashlib.sha256(f'inventory-variants:{original_group or item_id}'.encode()).digest()[:8], 'big', signed=True)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
        query = db.query(Item).filter(Item.deleted_at.is_(None))
        query = query.filter(Item.group_key == original_group) if original_group else query.filter(Item.id == item_id)
        members = query.order_by(Item.id).with_for_update().populate_existing().all()
        source = next((row for row in members if row.id == item_id), None)
        if source is None or source.group_key != original_group or not source.is_active:
            raise HTTPException(409, 'O produto ou sua grade mudou. Reabra a prévia antes de continuar.')
        if request.source_version != source_version(source):
            raise HTTPException(409, 'Os dados do produto mudaram. Reabra a prévia e confira novamente.')
        matching = [row for row in members if normalized(row.color) == normalized(source.color)]
        wanted = {normalized(s) for s in request.sizes}
        existing = [row for row in matching if normalized(row.size) in wanted]
        present = {normalized(row.size) for row in matching}
        missing = [size for size in request.sizes if normalized(size) not in present]
        created = []
        if missing:
            source.group_key = original_group or f'grade-{uuid.uuid4()}'
            for size in missing:
                # New identity and zero balances: no source SKU, sale or movement is copied.
                row = Item(**{key: getattr(source, key) for key in COPY_FIELDS},
                           name=f'{request.model_name} {size}', size=size,
                           barcode=f'{request.base_barcode.strip()}{size}' if request.base_barcode and request.base_barcode.strip() else None,
                           sku_internal=f'INV-{uuid.uuid4().hex.upper()}', group_key=source.group_key,
                           current_stock=0, stock_loja=0, stock_deposito=0,
                           is_active=True, created_by=user_id)
                db.add(row); created.append(row)
            db.flush()
            if request.initial_stock:
                for row in created:
                    create_movement(db, row.id, 'entry', request.initial_stock, user_id,
                                    reason='Estoque inicial — novo tamanho de produto existente',
                                    reference_type='inventory_variant', reference_id=str(item_id),
                                    location=request.stock_location)
        result = dict(group_key=source.group_key, created=created, existing=existing)
        # Creation, grouping and initial stock are one transaction. A repeated
        # size/color is returned as existing and never receives stock twice.
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
