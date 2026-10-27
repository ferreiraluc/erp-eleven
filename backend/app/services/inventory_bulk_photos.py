"""Bounded set-based gallery appends under the mass editor's product row locks."""
from fastapi import HTTPException
from sqlalchemy import JSON, case, cast, func, literal
from sqlalchemy.dialects.postgresql import JSONB

from ..models.inventory import Item
from .user_audit import record


def _gallery_expression(db):
    kind = func.json_typeof if db.get_bind().dialect.name == 'postgresql' else func.json_type
    is_array = kind(Item.additional_images) == 'array'
    empty = cast(literal('[]'), JSON) if db.get_bind().dialect.name == 'postgresql' else literal('[]')
    return case((is_array, Item.additional_images), else_=empty)


def validate_photo_additions(db, groups):
    ids = [identity for group in groups if group.operation == 'add' for identity in group.item_ids]
    if not ids:
        return {}
    # Read counts only; never bring originals or every variant's gallery into RAM.
    rows = db.query(Item.id, (Item.image_data.isnot(None) & (Item.image_data != '')).label('has_primary'),
                    func.json_array_length(_gallery_expression(db)).label('extra_count')).filter(Item.id.in_(ids)).all()
    primary = {}
    for identity, has_primary, extra_count in rows:
        if extra_count > 4 or (has_primary and extra_count >= 4):
            raise HTTPException(422, 'Um dos produtos já tem 5 fotos. Nenhuma alteração foi salva. Substitua a foto principal ou remova uma foto na edição do produto antes de adicionar.')
        primary[identity] = has_primary
    return primary


def apply_photo_groups(db, groups, primary):
    for group in groups:
        if group.operation == 'add':
            existing = Item.image_data.isnot(None) & (Item.image_data != '')
            gallery = _gallery_expression(db)
            if db.get_bind().dialect.name == 'postgresql':
                appended = cast(cast(gallery, JSONB).op('||')(literal([group.image_data], type_=JSONB)), JSON)
            else:
                appended = func.json_insert(gallery, '$[#]', group.image_data)
            values = {
                Item.image_data: case((existing, Item.image_data), else_=group.image_data),
                Item.additional_images: case((existing, appended), else_=Item.additional_images),
                Item.thumbnail_data: case((existing, Item.thumbnail_data), else_=None),
                Item.thumbnail_ready: case((existing, Item.thumbnail_ready), else_=False),
            }
        else:
            values = {Item.image_data: group.image_data, Item.thumbnail_data: None, Item.thumbnail_ready: False}
        db.query(Item).filter(Item.id.in_(group.item_ids)).update(values, synchronize_session=False)
        if db.info.get('audit_enabled') and db.info.get('audit_actor'):
            for identity in group.item_ids:
                field = 'additional_images' if group.operation == 'add' and primary[identity] else 'image_data'
                record(db, 'update', 'inventory', entity='inventory_items', entity_id=str(identity),
                       changes={field: {'changed': True}})
