"""Explicit source-based variants. Never infer product identity from a barcode."""
import hashlib
import json
import uuid
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, defer, load_only, undefer

from ..models.inventory import Item
from ..schemas.inventory_variants import VariantCreateRequest, VariantSummary
from .inventory_service import create_movement
from .inventory_taxonomy import key as taxonomy_key, canonical_size

COPY_FIELDS = ('description', 'category', 'color', 'brand', 'unit', 'location',
               'supplier_id', 'cost_price', 'sale_price', 'currency', 'cost_currency',
               'sale_currency', 'min_stock', 'max_stock', 'image_data', 'additional_images')


def normalized(value):
    return canonical_size(value or '').casefold()


def source_version(source):
    # Group membership and stock can legitimately change after the first request.
    # Excluding them makes retries safe without copying old balances or history.
    data = {key: getattr(source, key) for key in (*COPY_FIELDS, 'id', 'name', 'size', 'barcode', 'is_active', 'deleted_at')}
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def source_item(db, item_id):
    source = db.query(Item).options(undefer(Item.additional_images)).filter(Item.id == item_id, Item.deleted_at.is_(None)).first()
    if source is None:
        raise HTTPException(404, 'Produto não encontrado. Atualize a lista de estoque.')
    if not source.is_active:
        raise HTTPException(409, 'Ative o produto antes de criar outros tamanhos.')
    return source


def same_color_members(db, source, all_colors=False):
    # The preview only displays each sibling's identity, size and color. Keep
    # originals/prices/balances out of this read; the source remains fully loaded
    # for its reviewed photo and version token. Raiseload prevents an accidental
    # response-field change from turning this into one query per sibling.
    rows = (db.query(Item).options(load_only(
        *(getattr(Item, field) for field in VariantSummary.model_fields), raiseload=True))
        .filter(Item.deleted_at.is_(None), Item.group_key == source.group_key)
        .order_by(Item.id).all()) if source.group_key else [source]
    return rows if all_colors else [row for row in rows if taxonomy_key(row.color, 'color') == taxonomy_key(source.color, 'color')]


def variant_context(db, item_id, all_colors=False):
    source = source_item(db, item_id)
    name = source.name.strip()
    suffix = f' {source.size.strip()}' if source.size else ''
    if suffix and name.casefold().endswith(suffix.casefold()) and len(name) > len(suffix) + 1:
        name = name[:-len(suffix)]
    return dict(source=source, source_version=source_version(source), model_name=name,
                existing=same_color_members(db, source, all_colors))


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
        members = query.options(defer(Item.image_data, raiseload=True)).order_by(Item.id).with_for_update().populate_existing().all()
        source = next((row for row in members if row.id == item_id), None)
        if source is None or source.group_key != original_group or not source.is_active:
            raise HTTPException(409, 'O produto ou sua grade mudou. Reabra a prévia antes de continuar.')
        # All the same rows are locked in the same order. Only the chosen
        # source needs its original, reread after waiting for those locks.
        db.refresh(source, attribute_names=['image_data', 'additional_images'])
        if request.source_version != source_version(source):
            raise HTTPException(409, 'Os dados do produto mudaram. Reabra a prévia e confira novamente.')
        combinations = [(v.size, v.color, v.quantity) for v in request.variants] if request.variants else [
            (size, source.color, request.initial_stock) for size in request.sizes]
        identity = lambda size, color: (normalized(size), taxonomy_key(color, 'color'))
        wanted = {identity(size, color) for size, color, quantity in combinations}
        existing = [row for row in members if identity(row.size, row.color) in wanted]
        present = {identity(row.size, row.color) for row in members}
        missing = [(size, color, quantity) for size, color, quantity in combinations if identity(size, color) not in present]
        created = []
        if missing:
            source.group_key = original_group or f'grade-{uuid.uuid4()}'
            for size, color, quantity in missing:
                row = Item(**{key: getattr(source, key) for key in COPY_FIELDS if key not in ('color', 'additional_images')},
                           name=f'{request.model_name} {size}'.strip(), size=size or None, color=color,
                           barcode=f'{request.base_barcode.strip()}{size}' if request.base_barcode and request.base_barcode.strip() else None,
                           sku_internal=f'INV-{uuid.uuid4().hex.upper()}', group_key=source.group_key,
                           current_stock=0, stock_loja=0, stock_deposito=0,
                           is_active=True, created_by=user_id)
                db.add(row); created.append(row)
            db.flush()
            if source.additional_images:
                db.query(Item).filter(Item.id.in_([row.id for row in created])).update(
                    {Item.additional_images: source.additional_images, Item.updated_at: Item.updated_at},
                    synchronize_session=False)
            for row, (_, _, quantity) in zip(created, missing):
                if quantity:
                    create_movement(db, row.id, 'entry', quantity, user_id,
                                    reason='Estoque inicial — nova variação de produto existente',
                                    reference_type='inventory_variant', reference_id=str(item_id),
                                    location=request.stock_location)
        # Commit expires ORM rows. Freeze the already-loaded response fields so
        # serialization does not reread every sibling (including its photo).
        result = dict(group_key=source.group_key,
                      created=[VariantSummary.model_validate(row) for row in created],
                      existing=[VariantSummary.model_validate(row) for row in existing])
        # Creation, grouping and initial stock are one transaction. A repeated
        # size/color is returned as existing and never receives stock twice.
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
