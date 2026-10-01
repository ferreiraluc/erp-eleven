from sqlalchemy.orm import Session
from sqlalchemy import inspect
from decimal import Decimal
from typing import Optional
import uuid
from ..models.inventory import Item, StockMovement, MovementType, InventorySession, SessionStatus


class StockMovementError(ValueError):
    def __init__(self, message, status_code=422):
        super().__init__(message)
        self.status_code = status_code


def _compute_alert_level(item: Item) -> str:
    if not item.is_active:
        return "inactive"
    if item.current_stock <= 0:
        return "out"
    if item.current_stock < item.min_stock:
        return "low"
    if item.max_stock > 0 and item.current_stock > item.max_stock:
        return "high"
    return "ok"


def create_movement(
    db: Session,
    item_id: uuid.UUID,
    movement_type: str,
    quantity: int,
    created_by: uuid.UUID,
    reason: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    unit_cost: Optional[Decimal] = None,
    location: Optional[str] = "loja",
    location_from: Optional[str] = None,
    location_to: Optional[str] = None,
    notes: Optional[str] = None,
) -> StockMovement:
    item = db.query(Item).filter(Item.id == item_id).with_for_update().first()
    if not item:
        raise ValueError(f"Item {item_id} not found")
    # A prior lookup may have populated this session before the row lock waited.
    # Refresh stock columns explicitly so the identity map cannot supply stale balances.
    refresh_fields = ['current_stock', 'stock_loja', 'stock_deposito']
    if not inspect(item).attrs.cost_price.history.has_changes():
        refresh_fields.append('cost_price')
    db.refresh(item, attribute_names=refresh_fields, with_for_update=True)

    try:
        mv_type = MovementType[movement_type]
    except KeyError:
        raise StockMovementError("Tipo de movimentação inválido.") from None
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0 or (quantity == 0 and mv_type != MovementType.adjustment):
        raise StockMovementError("Informe uma quantidade inteira positiva; ajuste pode ser zero.")
    if quantity > 2_147_483_647:
        raise StockMovementError("Quantidade acima do limite permitido.")
    loc = location or 'loja'
    loc_from = location_from or 'loja'
    loc_to = location_to or 'deposito'
    if loc not in ('loja', 'deposito') or loc_from not in ('loja', 'deposito') or loc_to not in ('loja', 'deposito'):
        raise StockMovementError("Local inválido. Use loja ou deposito.")
    if mv_type == MovementType.transfer and loc_from == loc_to:
        raise StockMovementError("Origem e destino da transferência devem ser diferentes.")
    if unit_cost is not None:
        try:
            unit_cost = Decimal(str(unit_cost))
            if not unit_cost.is_finite() or unit_cost < 0:
                raise ValueError()
        except (ValueError, ArithmeticError):
            raise StockMovementError("Custo unitário deve ser um valor não negativo.") from None
    loja, deposito = item.stock_loja or 0, item.stock_deposito or 0
    if mv_type != MovementType.adjustment and (loja < 0 or deposito < 0 or item.current_stock != loja + deposito):
        raise StockMovementError("O saldo por local diverge do total ou está negativo. Confira o inventário e registre um ajuste antes de movimentar.", 409)
    source = deposito if (loc_from if mv_type == MovementType.transfer else loc) == 'deposito' else loja
    if mv_type in (MovementType.exit, MovementType.transfer) and quantity > source:
        raise StockMovementError(f"Saldo insuficiente no local de origem: disponível {source}, solicitado {quantity}.", 409)
    destination = deposito if (loc_to if mv_type == MovementType.transfer else loc) == 'deposito' else loja
    if mv_type in (MovementType.entry, MovementType.transfer) and destination + quantity > 2_147_483_647:
        raise StockMovementError("O saldo resultante excede o limite permitido.")
    if mv_type == MovementType.entry and loja + deposito + quantity > 2_147_483_647:
        raise StockMovementError("O total resultante excede o limite permitido.")
    if mv_type == MovementType.adjustment and quantity + (deposito if loc == 'loja' else loja) > 2_147_483_647:
        raise StockMovementError("O total resultante excede o limite permitido.")

    quantity_before = item.current_stock

    if mv_type == MovementType.entry:
        # Route to the correct location column
        loc = location or "loja"
        if loc == "deposito":
            item.stock_deposito = (item.stock_deposito or 0) + quantity
        else:
            item.stock_loja = (item.stock_loja or 0) + quantity

    elif mv_type == MovementType.exit:
        loc = location or "loja"
        if loc == "deposito":
            item.stock_deposito = (item.stock_deposito or 0) - quantity
        else:
            item.stock_loja = (item.stock_loja or 0) - quantity

    elif mv_type == MovementType.adjustment:
        # quantity is the new absolute value; adjustment applies to loja by default
        loc = location or "loja"
        if loc == "deposito":
            item.stock_deposito = quantity
        else:
            item.stock_loja = quantity

    elif mv_type == MovementType.transfer:
        # Move stock between columns — no net change to current_stock
        loc_from = location_from or "loja"
        loc_to = location_to or "deposito"
        if loc_from == "deposito":
            item.stock_deposito = (item.stock_deposito or 0) - quantity
            item.stock_loja = (item.stock_loja or 0) + quantity
        else:
            item.stock_loja = (item.stock_loja or 0) - quantity
            item.stock_deposito = (item.stock_deposito or 0) + quantity

    # Always keep current_stock in sync with sum of location stocks
    item.current_stock = (item.stock_loja or 0) + (item.stock_deposito or 0)

    # Recalculate weighted average cost on entries
    if mv_type == MovementType.entry and unit_cost is not None:
        existing_stock = quantity_before if quantity_before > 0 else 0
        existing_cost = item.cost_price or Decimal("0")
        if existing_stock + quantity > 0:
            new_cost = (existing_stock * existing_cost + quantity * unit_cost) / (existing_stock + quantity)
            item.cost_price = new_cost

    movement = StockMovement(
        item_id=item_id,
        movement_type=mv_type,
        quantity=abs(quantity) if mv_type != MovementType.adjustment else quantity,
        quantity_before=quantity_before,
        quantity_after=item.current_stock,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        unit_cost=unit_cost,
        location_from=location_from or (location if mv_type in (MovementType.entry, MovementType.exit, MovementType.adjustment) else None),
        location_to=location_to,
        notes=notes,
        created_by=created_by,
    )

    db.add(movement)
    db.flush()
    return movement


def apply_session(
    db: Session,
    session_id: uuid.UUID,
    created_by: uuid.UUID,
):
    """Apply physical inventory — generate adjustment movements"""
    session = db.query(InventorySession).filter(InventorySession.id == session_id).first()
    if not session:
        raise ValueError("Session not found")

    movements = []
    for session_item in session.session_items:
        if session_item.counted_quantity is not None:
            movement = create_movement(
                db=db,
                item_id=session_item.item_id,
                movement_type="adjustment",
                quantity=session_item.counted_quantity,
                created_by=created_by,
                reason=f"Ajuste de inventário - Sessão {session.name}",
                reference_type="inventory_session",
                reference_id=str(session_id),
                location="loja",
            )
            movements.append(movement)

    session.status = SessionStatus.applied
    from ..config import settings
    session.applied_at = settings.now()
    db.commit()
    return movements
