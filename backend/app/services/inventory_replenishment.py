"""Confirmed depot-to-store movements and their labels in one transaction."""
from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import load_only

from ..models.inventory import Item, MovementType, StockMovement
from . import product_labels as labels
from .inventory_search import build_search
from .inventory_history import timestamp
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


def store_history(db, candidates):
    """Aggregate only real store activity, before pagination, without reading images.

    Movement before/after quantities are combined stock, not store balances. For
    currently empty stores, the latest store exit/transfer (or real adjustment to
    zero) is the relevant depletion. A depot entry, repeated zero count or repair
    of an inconsistent combined total must not make an older depletion look recent.
    Zero adjustments require explicit local balances. Missing legacy locations stay unknown
    except the two import paths that explicitly initialized all stock in the store.
    """
    move = StockMovement
    positive = move.quantity > 0
    store_exit = and_(move.movement_type == MovementType.exit, positive,
                      move.location_from == 'loja')
    transfer_out = and_(move.movement_type == MovementType.transfer, positive,
                       move.location_from == 'loja',
                       or_(move.location_to == 'deposito', move.location_to.is_(None)))
    store_adjustment = and_(move.movement_type == MovementType.adjustment,
                            move.location_from == 'loja')
    adjustment_to_zero = and_(store_adjustment, move.quantity == 0,
                              move.stock_loja_before > 0, move.stock_loja_after == 0)
    depletion = or_(store_exit, transfer_out, adjustment_to_zero)
    store_entry = and_(move.movement_type == MovementType.entry, positive, or_(
        move.location_from == 'loja', move.location_to == 'loja',
        and_(move.location_from.is_(None), move.location_to.is_(None),
             move.reason.in_(['Importação CSV', 'Importação NF-e']))))
    transfer_in = and_(move.movement_type == MovementType.transfer, positive,
                      move.location_to == 'loja',
                      or_(move.location_from == 'deposito', move.location_from.is_(None)))
    store_activity = or_(depletion, store_entry, transfer_in,
                         and_(store_adjustment, positive))
    return (db.query(move.item_id.label('item_id'),
                     func.max(case((depletion, move.created_at))).label('last_store_exit_at'))
            .filter(move.item_id.in_(candidates.with_entities(Item.id)), store_activity)
            .group_by(move.item_id).subquery())


def list_items(db, *, q='', page=1):
    query = labels.items_query(db).filter(Item.stock_loja == 0, Item.stock_deposito > 0)
    search = build_search(db, q) if q.strip() else None
    if search:
        query = query.filter(search.condition)
    total = query.with_entities(Item.id).count()
    history = store_history(db, query)
    has_history = history.c.item_id.isnot(None)
    order = [history.c.last_store_exit_at.desc().nullslast(), has_history.desc(),
             func.lower(Item.name), Item.id]
    if search:
        order.insert(0, search.rank)
    fields = (*labels.FIELDS, Item.brand, Item.location, Item.updated_at)
    rows = (query.outerjoin(history, history.c.item_id == Item.id)
            .options(load_only(*fields, raiseload=True))
            .add_columns((Item.image_data.isnot(None) & (Item.image_data != '')).label('has_image'),
                         history.c.last_store_exit_at, has_history)
            .order_by(*order).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all())
    return dict(items=[dict(labels.item_view(item), brand=item.brand, location=item.location,
                            updated_at=item.updated_at, has_image=bool(has_image),
                            blocked_reason=blocked_reason(item),
                            last_store_exit_at=timestamp(last_store_exit_at),
                            has_store_history=bool(has_store_history))
                       for item, has_image, last_store_exit_at, has_store_history in rows],
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
