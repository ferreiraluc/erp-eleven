"""Owner-only, reviewed directory cleanup using the existing identity rules."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_owner
from ...services.directory_duplicates import candidates, merge_pair
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
