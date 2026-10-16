"""Reviewed receiving collections, bounded metadata reads and explicit membership."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from hashlib import sha256
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only
from ...database import get_db
from ...dependencies import get_current_active_user, require_role
from ...models.usuario import Usuario
from ...models.inventory import Item
from ...models.inventory_receiving import ReceivingLot, ReceivingLotItem
from ...services.inventory_duplicate import lock

router = APIRouter()
MAX_ITEMS = 1000


class LotDetails(BaseModel):
    model_config = {'extra': 'forbid'}
    name: str = Field(min_length=2, max_length=160)
    notes: str = Field(default='', max_length=2000)
    received_on: date

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Informe o nome do lote.')
        return value


class LotMembers(BaseModel):
    model_config = {'extra': 'forbid'}
    item_ids: list[UUID] = Field(min_length=1, max_length=MAX_ITEMS)


class LotCreate(LotDetails, LotMembers):
    request_id: UUID
    confirm: bool


class LotAttach(LotMembers):
    confirm: bool


def lot_filter(lot_id):
    return Item.id.in_(
        select(ReceivingLotItem.item_id).where(ReceivingLotItem.lot_id == lot_id))


def details(lot, count=0):
    return dict(id=lot.id, name=lot.name, notes=lot.notes, received_on=lot.received_on,
                created_at=lot.created_at, item_count=count)


def get_lot(db, lot_id, for_update=False):
    query = db.query(ReceivingLot).filter(ReceivingLot.id == lot_id)
    row = (query.with_for_update() if for_update else query).first()
    if row is None:
        raise HTTPException(404, 'Lote de recebimento não encontrado.')
    return row


def add_members(db, lot, ids, user_id):
    ids = set(ids)
    rows = db.query(Item).options(load_only(Item.id, Item.name, Item.sku_internal, raiseload=True)).filter(
        Item.id.in_(ids), Item.deleted_at.is_(None)).order_by(Item.id).with_for_update().all()
    if len(rows) != len(ids):
        raise HTTPException(409, 'Um produto foi excluído. Atualize a seleção antes de continuar.')
    present = set(value for value, in db.query(ReceivingLotItem.item_id).filter(ReceivingLotItem.lot_id == lot.id))
    for row in rows:
        if row.id not in present:
            db.add(ReceivingLotItem(lot_id=lot.id, item_id=row.id, item_name=row.name,
                                   item_sku=row.sku_internal, created_by=user_id))


@router.get('/receiving-lots')
def list_lots(page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100),
              db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    total = db.query(ReceivingLot).count()
    rows = db.query(ReceivingLot, func.count(ReceivingLotItem.id)).outerjoin(
        ReceivingLotItem, ReceivingLotItem.lot_id == ReceivingLot.id).group_by(ReceivingLot.id).order_by(
        ReceivingLot.received_on.desc(), ReceivingLot.created_at.desc(), ReceivingLot.id).offset((page-1)*page_size).limit(page_size).all()
    return dict(items=[details(lot, count) for lot, count in rows], total=total)


@router.get('/receiving-candidates')
def candidates(date_from: date, date_to: date, db: Session = Depends(get_db),
               user: Usuario = Depends(get_current_active_user)):
    if date_to < date_from or (date_to-date_from).days > 92:
        raise HTTPException(422, 'Escolha um período de até 93 dias, em ordem crescente.')
    # PostgreSQL stores these legacy naive timestamps in UTC (the write session's
    # timezone); SQLite strips the offset from settings.now() and stores local time.
    # Convert bounds, not the indexed column, so a midnight arrival keeps its day.
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to + timedelta(days=1), time.min)
    if db.bind.dialect.name == 'postgresql':
        zone = ZoneInfo('America/Sao_Paulo')
        start = start.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
        end = end.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    query = db.query(Item).filter(Item.deleted_at.is_(None), Item.created_at >= start, Item.created_at < end)
    count = query.count()
    if count > MAX_ITEMS:
        raise HTTPException(422, 'Mais de 1000 produtos neste período. Selecione um intervalo menor.')
    rows = query.with_entities(Item.id, Item.name, Item.sku_internal, Item.size, Item.color, Item.created_at).order_by(Item.created_at, Item.id).all()
    return dict(items=[dict(row._mapping) for row in rows], total=count)


@router.post('/receiving-lots', status_code=201)
def create_lot(body: LotCreate, db: Session = Depends(get_db),
               user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    if not body.confirm:
        raise HTTPException(422, 'Confira os produtos antes de criar o lote.')
    fingerprint = sha256(json.dumps({**body.model_dump(mode='json'),
        'item_ids': sorted(set(str(i) for i in body.item_ids))}, sort_keys=True).encode()).hexdigest()
    try:
        lock(db, f'receiving:{body.request_id}')
        previous = db.get(ReceivingLot, body.request_id)
        if previous:
            if previous.created_by != user.id or previous.request_fingerprint != fingerprint:
                raise HTTPException(409, 'Esta confirmação já foi utilizada. Reabra o lote.')
            result = details(previous, db.query(ReceivingLotItem).filter_by(lot_id=previous.id).count())
        else:
            lot = ReceivingLot(id=body.request_id, name=body.name, notes=body.notes,
                received_on=body.received_on, created_by=user.id, request_fingerprint=fingerprint)
            db.add(lot); db.flush()
            add_members(db, lot, body.item_ids, user.id)
            result = details(lot, len(set(body.item_ids)))
        db.commit()
        return result
    except Exception:
        db.rollback(); raise


@router.patch('/receiving-lots/{lot_id}')
def edit_lot(lot_id: UUID, body: LotDetails, db: Session = Depends(get_db),
             user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    lot = get_lot(db, lot_id, True)
    for key, value in body.model_dump().items(): setattr(lot, key, value)
    db.commit()
    return details(lot, db.query(ReceivingLotItem).filter_by(lot_id=lot_id).count())


@router.post('/receiving-lots/{lot_id}/items')
def attach(lot_id: UUID, body: LotAttach, db: Session = Depends(get_db),
           user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    if not body.confirm: raise HTTPException(422, 'Confira os produtos antes de vincular.')
    try:
        lot = get_lot(db, lot_id, True)
        add_members(db, lot, body.item_ids, user.id)
        db.commit()
        return details(lot, db.query(ReceivingLotItem).filter_by(lot_id=lot_id).count())
    except Exception:
        db.rollback(); raise


@router.get('/receiving-lots/{lot_id}/items')
def members(lot_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
            db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    lot = get_lot(db, lot_id)
    query = db.query(ReceivingLotItem, Item.name, Item.deleted_at, Item.size, Item.color).outerjoin(Item, Item.id == ReceivingLotItem.item_id).filter(ReceivingLotItem.lot_id == lot_id)
    return dict(lot=details(lot, query.count()), items=[dict(id=row.id, item_id=row.item_id,
        name=name or row.item_name, sku_internal=row.item_sku, size=size, color=color,
        deleted=deleted_at is not None or name is None)
        for row, name, deleted_at, size, color in query.order_by(ReceivingLotItem.created_at, ReceivingLotItem.id).offset((page-1)*page_size).limit(page_size)])


@router.delete('/receiving-lots/{lot_id}/items/{member_id}', status_code=204)
def detach(lot_id: UUID, member_id: UUID, db: Session = Depends(get_db),
           user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    get_lot(db, lot_id, True)
    row = db.query(ReceivingLotItem).filter_by(lot_id=lot_id, id=member_id).first()
    if row: db.delete(row)
    db.commit()
