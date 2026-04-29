from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from typing import List, Optional
import uuid
from ..models.inventory import Item, StockMovement, MovementType, InventorySession, InventorySessionItem, SessionStatus


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
    location_from: Optional[str] = None,
    location_to: Optional[str] = None,
    notes: Optional[str] = None,
) -> StockMovement:
    item = db.query(Item).filter(Item.id == item_id).with_for_update().first()
    if not item:
        raise ValueError(f"Item {item_id} not found")

    quantity_before = item.current_stock
    mv_type = MovementType[movement_type]

    if mv_type == MovementType.entry:
        delta = quantity
    elif mv_type == MovementType.exit:
        delta = -quantity
    elif mv_type == MovementType.adjustment:
        # quantity is the new absolute value
        delta = quantity - item.current_stock
    elif mv_type == MovementType.transfer:
        delta = 0  # stock stays the same, just changes location
    else:
        delta = quantity

    quantity_after = quantity_before + delta

    # Recalculate weighted average cost on entries
    if mv_type == MovementType.entry and unit_cost is not None:
        existing_stock = item.current_stock if item.current_stock > 0 else 0
        existing_cost = item.cost_price or Decimal("0")
        if existing_stock + quantity > 0:
            new_cost = (existing_stock * existing_cost + quantity * unit_cost) / (existing_stock + quantity)
            item.cost_price = new_cost

    item.current_stock = quantity_after

    movement = StockMovement(
        item_id=item_id,
        movement_type=mv_type,
        quantity=abs(quantity) if mv_type != MovementType.adjustment else quantity,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        unit_cost=unit_cost,
        location_from=location_from,
        location_to=location_to,
        notes=notes,
        created_by=created_by,
    )

    db.add(movement)
    db.flush()
    return movement


def apply_sale_exit(
    db: Session,
    sale_id: str,
    items: List[dict],
    created_by: uuid.UUID,
):
    """Hook for sales integration — creates exit movements in batch"""
    movements = []
    for item_data in items:
        movement = create_movement(
            db=db,
            item_id=item_data["item_id"],
            movement_type="exit",
            quantity=item_data["quantity"],
            created_by=created_by,
            reason="Venda",
            reference_type="venda",
            reference_id=sale_id,
        )
        movements.append(movement)
    db.commit()
    return movements


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
            )
            movements.append(movement)

    session.status = SessionStatus.applied
    from sqlalchemy.sql import func
    session.applied_at = func.current_timestamp()
    db.commit()
    return movements
