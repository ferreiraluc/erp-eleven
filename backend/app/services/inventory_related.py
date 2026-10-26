"""Small, paginated suggestions for the PDV. Relationships never imply identity."""
from fastapi import HTTPException
from sqlalchemy import and_, false, or_, func

from ..models.inventory import Item
from .inventory_images import catalog_query, catalog_response
from .inventory_taxonomy import facet_filters


def related_products(db, item_id, *, limit=12, after_rank=None, after_id=None):
    source = db.query(Item.id, Item.group_key, Item.brand, Item.category, Item.color).filter(
        Item.id == item_id, Item.is_active.is_(True), Item.deleted_at.is_(None)).first()
    if source is None:
        raise HTTPException(404, 'Produto não encontrado ou inativo.')
    if (after_rank is None) != (after_id is None):
        raise HTTPException(422, 'Informe os dois campos de continuação.')

    # Canonical facets and explicit grades already have indexes. Avoid fuzzy
    # searches, COUNTs and photo reads across the catalog on the scan path.
    group = Item.group_key == source.group_key if source.group_key else false()
    brand = Item.brand == source.brand if source.brand else false()
    category = Item.category == source.category if source.category else false()
    color = func.coalesce(facet_filters(db)(Item.color, source.color), False) if source.color else false()
    outside_group = or_(Item.group_key.is_(None), Item.group_key != source.group_key) if source.group_key else True
    outside_brand = or_(Item.brand.is_(None), Item.brand != source.brand) if source.brand else True
    outside_category = or_(Item.category.is_(None), Item.category != source.category) if source.category else True
    tiers = [
        ('family', and_(group, color)),
        ('family', and_(group, ~color)),
        ('brand_category', and_(outside_group, brand, category, color)),
        ('brand_category', and_(outside_group, brand, category, ~color)),
        ('brand', and_(outside_group, brand, outside_category)),
        ('category', and_(outside_group, outside_brand, category)),
    ]
    selected = []
    for rank, (relation, condition) in enumerate(tiers):
        if not source.color and rank in (0, 2):
            continue  # No empty color query; keep cursor tier numbers stable.
        if after_rank is not None and rank < after_rank:
            continue
        query = db.query(Item.id).filter(Item.is_active.is_(True), Item.deleted_at.is_(None),
                                        Item.id != item_id, condition)
        if rank == after_rank:
            query = query.filter(Item.id > after_id)
        # One extra ID indicates a next page, without loading its metadata/photo.
        ids = query.order_by(Item.id).limit(limit + 1 - len(selected)).all()
        selected.extend((row.id, rank, relation) for row in ids)
        if len(selected) > limit:
            break
    page = selected[:limit]
    if not page:
        return {'items': [], 'next_cursor': None}
    rows = catalog_query(db.query(Item).filter(Item.id.in_([row[0] for row in page]),
        Item.is_active.is_(True), Item.deleted_at.is_(None)), False).all()
    items = {item.id: catalog_response(item, has_image, False) for item, has_image in rows}
    return {
        'items': [{'item': items[id], 'relation': relation} for id, _, relation in page if id in items],
        'next_cursor': {'after_rank': page[-1][1], 'after_id': page[-1][0]} if len(selected) > limit else None,
    }
