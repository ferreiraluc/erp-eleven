"""Replenishment confirmation shares the existing stock and Zebra safeguards."""
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_active_user, require_role
from ...services import inventory_replenishment as replenishment
from .inventory_labels import BatchInput, LabelLine

router = APIRouter()
operator = require_role(['ADMIN', 'GERENTE'])


class ReplenishmentLine(LabelLine):
    sale_price: Decimal = Field(ge=0)
    sale_currency: str = Field(min_length=1, max_length=10)
    expected_stock_loja: int = Field(ge=0, le=2_147_483_647, strict=True)
    expected_stock_deposito: int = Field(ge=0, le=2_147_483_647, strict=True)
    expected_current_stock: int = Field(ge=0, le=2_147_483_647, strict=True)


class ReplenishmentInput(BatchInput):
    items: list[ReplenishmentLine] = Field(min_length=1, max_length=replenishment.MAX_ITEMS)


@router.get('/items')
def items(response: Response, q: str = Query('', max_length=150), page: int = Query(1, ge=1, le=20000),
          db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    response.headers['Cache-Control'] = 'no-store'
    return replenishment.list_items(db, q=q, page=page)


@router.post('/confirm')
def confirm(body: ReplenishmentInput, response: Response,
            db: Session = Depends(get_db), user=Depends(operator)):
    response.headers['Cache-Control'] = 'no-store'
    return replenishment.confirm_replenishment(db, user, body)
