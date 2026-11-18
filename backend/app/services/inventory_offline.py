"""Bounded, read-only inventory snapshots. No photos, costs or personal records."""
from datetime import datetime, timezone

from ..models.inventory import Item
from sqlalchemy import func


def catalog_page(db, user, after_id=None, limit=500):
    # Read only the same shared inventory attributes visible to employees and
    # the reseller. Never materialize Item (which would load original photos).
    columns = [Item.id, Item.name, Item.inventory_code, Item.sku_internal, Item.barcode,
               Item.brand, Item.category, Item.size, Item.color, Item.group_key,
               Item.location, Item.unit, Item.sale_price, Item.sale_currency,
               Item.is_active, Item.created_at, Item.updated_at, Item.min_stock,
               Item.max_stock, Item.current_stock, Item.stock_loja, Item.stock_deposito,
               Item.reserved_loja, Item.reserved_deposito,
               func.substr(Item.description, 1, 512).label('description'),
               (Item.image_data.isnot(None) & (Item.image_data != '')).label('has_image')]
    query = db.query(*columns).filter(Item.deleted_at.is_(None))
    if after_id:
        query = query.filter(Item.id > after_id)
    rows = query.order_by(Item.id).limit(limit + 1).all()
    observed = datetime.now(timezone.utc).isoformat()
    items = []
    for row in rows[:limit]:
        data = dict(row._mapping)
        total, loja, deposito = (data[key] for key in ('current_stock', 'stock_loja', 'stock_deposito'))
        held_l, held_d = data['reserved_loja'], data['reserved_deposito']
        consistent = (all(isinstance(n, int) and not isinstance(n, bool) and abs(n) <= 2_147_483_647
                          for n in (total, loja, deposito, held_l, held_d))
                      and total == loja + deposito and 0 <= held_l <= max(0, loja)
                      and 0 <= held_d <= max(0, deposito))
        data.update(stock_confirmed=consistent, snapshot_at=observed,
                    available_loja=loja - held_l if consistent else None,
                    available_deposito=deposito - held_d if consistent else None,
                    available_stock=total - held_l - held_d if consistent else None)
        if not consistent:
            for name in ('current_stock', 'stock_loja', 'stock_deposito', 'reserved_loja', 'reserved_deposito'):
                data[name] = None
        items.append(data)
    return {'schema': 1, 'owner_id': str(user.id), 'observed_at': observed, 'items': items,
            'next_cursor': str(rows[limit - 1].id) if len(rows) > limit else None}
