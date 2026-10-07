"""Owner-reviewed catalog removal, or physical deletion without dependencies."""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from ..models.inventory import Item, StockMovement, InventorySessionItem
from ..models.pdv import PdvSaleItem
from .access_policy import is_owner
from .user_audit import bind_actor, record
from .inventory_links import product_sale_link
from ..config import settings


def _review(db, item_id, user):
    if not user.ativo or not is_owner(user):
        raise HTTPException(403, 'Somente Lucas pode excluir produtos definitivamente.')
    item = db.query(Item).filter_by(id=item_id).with_for_update().populate_existing().first()
    if not item or item.deleted_at:
        raise HTTPException(404, 'Produto não encontrado. Atualize a lista de estoque.')
    # PostgreSQL FK checks serialize new sale/count references with this item lock.
    sale_lines = db.query(PdvSaleItem).filter(product_sale_link(item)).order_by(PdvSaleItem.id).all()
    count_lines = db.query(InventorySessionItem).filter_by(item_id=item.id).order_by(InventorySessionItem.id).all()
    sales = len({line.sale_id for line in sale_lines})
    counts = len(count_lines)
    movements = db.query(StockMovement).filter_by(item_id=item.id).order_by(StockMovement.id).all()
    linked_movements = sum(bool((row.reference_type or '').strip() not in ('', 'assistant_action')
                               or (row.reference_id and not (row.reference_type or '').strip())) for row in movements)
    blockers = [{'code': code, 'count': count} for code, count in
                [('sales', sales), ('inventory_counts', counts), ('linked_movements', linked_movements)] if count]
    snapshot = lambda row: {col.name: str(getattr(row, col.name)) for col in row.__table__.columns}
    token = hashlib.sha256(json.dumps({'item': snapshot(item), 'movements': [snapshot(r) for r in movements],
                                      'sales': [snapshot(r) for r in sale_lines], 'counts': [snapshot(r) for r in count_lines]},
                                     sort_keys=True).encode()).hexdigest()
    preview = {'item': {key: getattr(item, key) for key in
               ('id', 'name', 'sku_internal', 'size', 'color', 'current_stock', 'stock_loja', 'stock_deposito')},
               'allowed': not blockers, 'blockers': blockers, 'movement_count': len(movements),
               'plan_token': token if not blockers else None, 'preserve_history_token': token}
    return item, preview


def deletion_preview(db, item_id, user):
    return _review(db, item_id, user)[1]


def delete_from_catalog(db, item_id, user, body):
    item, preview = _review(db, item_id, user)
    if not body.confirm or body.sku != item.sku_internal or body.plan_token != preview['preserve_history_token']:
        raise HTTPException(409, 'O produto mudou ou a confirmação não corresponde. Confira novamente antes de excluir.')
    bind_actor(db, user)
    item.deleted_at = settings.now()
    item.deleted_by = user.id
    item.is_active = False
    item.image_data = None
    record(db, 'item_catalog_deleted', 'inventory', entity='inventory_items', entity_id=str(item.id),
           changes={'name': item.name, 'sku': item.sku_internal, 'history_preserved': True,
                    'stock_at_deletion': {'total': item.current_stock, 'loja': item.stock_loja, 'deposito': item.stock_deposito},
                    'links_at_review': preview['blockers']})
    db.flush()
    return {'deleted': True, 'id': item_id, 'history_preserved': True}


def permanently_delete_item(db, item_id, user, body):
    item, preview = _review(db, item_id, user)
    if not preview['allowed']:
        raise HTTPException(409, 'Produto com vínculos operacionais. A exclusão definitiva não é permitida.')
    if not body.confirm or body.sku != item.sku_internal or body.plan_token != preview['plan_token']:
        raise HTTPException(409, 'O produto mudou ou a confirmação não corresponde. Confira novamente antes de excluir.')
    bind_actor(db, user)
    # Keep the audit tombstone, never the photo or any other operational snapshot.
    record(db, 'item_permanently_deleted', 'inventory', entity='inventory_items', entity_id=str(item.id),
           changes={'name': item.name, 'sku': item.sku_internal, 'size': item.size, 'color': item.color,
                    'stock_removed': {'total': item.current_stock, 'loja': item.stock_loja, 'deposito': item.stock_deposito},
                    'movements_removed': preview['movement_count']})
    try:
        db.execute(delete(StockMovement).where(StockMovement.item_id == item.id))
        db.execute(delete(Item).where(Item.id == item.id))
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Produto com vínculos operacionais. A exclusão definitiva não é permitida.') from None
    return {'deleted': True, 'id': item_id, 'movements_removed': preview['movement_count']}
