"""Project movement reads without exposing sale metadata or mutating ORM rows."""
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.inventory import StockMovement
from ..models.pdv import PdvSale
from ..models.usuario import Usuario
from ..schemas.inventory import MovementResponse
from .access_policy import is_owner, own_sales, sales_query

PRIVATE_SALE_FIELDS = ('reference_id', 'reason', 'notes', 'created_by', 'unit_cost')


def restricted_movement_ids(db: Session, rows: Sequence[StockMovement], user: Usuario) -> set[UUID]:
    """Authorize the supplied page in one query, preserving operational stock facts."""
    owner = is_owner(user)
    if owner and not own_sales(user):
        return set()
    refs = {}
    for row in rows:
        if row.reference_type == 'pdv_sale':
            try:
                refs[row.reference_id] = UUID(row.reference_id or '')
            except ValueError:
                pass
    allowed = set()
    if refs:
        query = sales_query(db.query(PdvSale.id).filter(PdvSale.id.in_(set(refs.values()))), PdvSale, user, pdv=True)
        if not owner:
            query = query.filter(PdvSale.deleted_at.is_(None))
        allowed = {sid for (sid,) in query}
    return {row.id for row in rows if row.reference_type == 'pdv_sale' and refs.get(row.reference_id) not in allowed}


def movement_read_responses(db: Session, rows: Sequence[StockMovement], user: Usuario) -> list[MovementResponse]:
    """Rows already include the item name; redact copies, never persistent values."""
    restricted = restricted_movement_ids(db, rows, user)
    result = []
    for row in rows:
        response = MovementResponse.model_validate(row)
        if row.id in restricted:
            response = response.model_copy(update={field: None for field in PRIVATE_SALE_FIELDS})
        result.append(response)
    return result
