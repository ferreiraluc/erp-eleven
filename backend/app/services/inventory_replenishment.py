"""Confirmed depot-to-store movements and their labels in one transaction."""
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import load_only

from ..models.inventory import Item
from . import product_labels as labels
from .inventory_search import build_search
from .inventory_service import StockMovementError, create_movement

OPERATION = 'inventory_replenishment'
PAGE_SIZE = 40
MAX_ITEMS = 100


def blocked_reason(item):
    balances = (item.current_stock, item.stock_loja, item.stock_deposito)
    if any(value is None for value in balances):
        return 'Saldo desconhecido. Confira o estoque antes de repor.'
    if (any(value < 0 for value in balances) or
            item.current_stock != item.stock_loja + item.stock_deposito):
        return 'O saldo por local diverge do total. Confira o estoque antes de repor.'
    if not labels.CODE.fullmatch(item.inventory_code or ''):
        return 'O produto precisa de um código interno válido para imprimir a etiqueta.'
    return None


def list_items(db, *, q='', page=1):
    query = labels.items_query(db).filter(Item.stock_loja == 0, Item.stock_deposito > 0)
    search = build_search(db, q) if q.strip() else None
    if search:
        query = query.filter(search.condition)
    total = query.with_entities(Item.id).count()
    order = [func.lower(Item.name), Item.id]
    if search:
        order.insert(0, search.rank)
    fields = (*labels.FIELDS, Item.brand, Item.location, Item.updated_at)
    rows = (query.options(load_only(*fields, raiseload=True))
            .add_columns((Item.image_data.isnot(None) & (Item.image_data != '')).label('has_image'))
            .order_by(*order).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all())
    return dict(items=[dict(labels.item_view(item), brand=item.brand, location=item.location,
                            updated_at=item.updated_at, has_image=bool(has_image),
                            blocked_reason=blocked_reason(item)) for item, has_image in rows],
                total=total, page=page, page_size=PAGE_SIZE)


def replenishment_view(db, root):
    result = (root.snapshot or {}).get('replenishment')
    if not result:
        # A committed confirmation must contain the complete atomic result.
        raise HTTPException(409, 'Esta confirmação não contém uma reposição concluída. Confira o histórico.')
    return dict(labels.batch_view(db, root), replenished_items=result['replenished_items'],
                movements=result['movements'], created_at=root.created_at)


def confirm_replenishment(db, user, body):
    try:
        root, products, created = labels.prepare_batch(db, user, body, operation=OPERATION)
        if not created:
            return replenishment_view(db, root)

        # All item locks are already held in stable UUID order. Check the entire
        # reviewed selection before changing the first balance.
        for line in body.items:
            item = products[line.item_id]
            if (item.stock_loja, item.stock_deposito, item.current_stock) != (
                    line.expected_stock_loja, line.expected_stock_deposito, line.expected_current_stock):
                raise HTTPException(409, 'O estoque mudou durante a conferência. Atualize a reposição antes de confirmar.')
            reason = blocked_reason(item)
            if reason:
                raise HTTPException(409, reason)
            if item.stock_loja != 0 or item.stock_deposito <= 0:
                raise HTTPException(409, 'Este produto já foi reposto ou não tem saldo no depósito. Atualize a lista.')
            if line.copies > item.stock_deposito:
                raise HTTPException(409, 'A quantidade para repor excede o saldo no depósito. Atualize a lista.')

        movements = {}
        for line in sorted(body.items, key=lambda row: str(row.item_id)):
            movement = create_movement(db, line.item_id, 'transfer', line.copies, user.id,
                reason='Reposição da loja — etiquetas de produtos', reference_type=OPERATION,
                reference_id=str(root.id), location_from='deposito', location_to='loja')
            item = products[line.item_id]
            movements[line.item_id] = dict(id=str(movement.id), item_id=str(item.id),
                quantity=line.copies, stock_loja=item.stock_loja, stock_deposito=item.stock_deposito,
                current_stock=item.current_stock)

        # Keep the confirmed balances, not a future product read, for retries.
        # Metadata is outside the label artwork fields and does not change ZPL.
        root.snapshot = {**root.snapshot, 'replenishment': dict(
            replenished_items=len(body.items), movements=[movements[line.item_id] for line in body.items])}
        db.commit()
        return replenishment_view(db, root)
    except StockMovementError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from None
    except Exception:
        db.rollback()
        raise
