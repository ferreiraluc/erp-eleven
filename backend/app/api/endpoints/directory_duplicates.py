"""Owner-only, reviewed directory cleanup using the existing identity rules."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_owner
from ...services.directory_duplicates import candidates, merge_pair
from ...services.customer_maintenance import merge_customer_selection
from ...services.user_audit import bind_actor

router = APIRouter(prefix='/maintenance')


class Pair(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['customers', 'addresses']
    target_id: UUID
    source_id: UUID


class ConfirmedPair(Pair):
    plan_token: str = Field(min_length=64, max_length=64)
    confirm: Literal[True]


class CustomerSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target_id: UUID
    source_ids: list[UUID] = Field(min_length=1, max_length=19)

    @model_validator(mode='after')
    def distinct_customers(self):
        if len(set(self.source_ids)) != len(self.source_ids) or self.target_id in self.source_ids:
            raise ValueError('Selecione de 2 a 20 clientes diferentes, incluindo o principal.')
        return self


class ConfirmedCustomerSelection(CustomerSelection):
    plan_token: str = Field(min_length=64, max_length=64)
    confirm: Literal[True]
    reviewed_conflicts: bool = False


@router.get('/duplicates')
def list_duplicates(kind: Literal['customers', 'addresses'], q: str = Query('', max_length=100),
                    db: Session = Depends(get_db), user=Depends(require_owner)):
    return candidates(db, kind, q.strip())


@router.post('/duplicates/preview')
def preview(body: Pair, db: Session = Depends(get_db), user=Depends(require_owner)):
    result = merge_pair(db, body.kind, body.target_id, body.source_id)
    db.rollback()
    return result


@router.post('/duplicates/confirm')
def confirm(body: ConfirmedPair, db: Session = Depends(get_db), user=Depends(require_owner)):
    bind_actor(db, user)
    result = merge_pair(db, body.kind, body.target_id, body.source_id, apply=True, expected_plan=body.plan_token)
    db.commit()
    return result


@router.post('/customers/preview')
def preview_customers(body: CustomerSelection, db: Session = Depends(get_db), user=Depends(require_owner)):
    try:
        result = merge_customer_selection(db, body.target_id, body.source_ids)
        db.rollback()
        return result
    except Exception:
        db.rollback()
        raise


@router.post('/customers/confirm')
def confirm_customers(body: ConfirmedCustomerSelection, db: Session = Depends(get_db), user=Depends(require_owner)):
    bind_actor(db, user)
    try:
        result = merge_customer_selection(db, body.target_id, body.source_ids, apply=True,
                                         expected_plan=body.plan_token, reviewed_conflicts=body.reviewed_conflicts)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
