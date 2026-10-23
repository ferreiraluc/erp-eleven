"""Internal product labels, isolated from shipping labels and sale receipts."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_active_user, require_role, require_owner
from ...models.inventory import Item
from ...models.inventory_receiving import ReceivingLot, ReceivingLotItem
from ...models.printing import PrintJob
from ...models.assistant import utcnow
from ...services import product_labels as labels
from ...services import product_label_layouts as layouts
from ...schemas.product_label_layout import DesignPreview, LayoutInput
from ...services.inventory_search import build_search

router = APIRouter()
operator = require_role(['ADMIN', 'GERENTE'])


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirm: bool = False


class Configuration(Confirmation):
    rotate: bool = False


@router.get('/device')
def device(db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    return dict(device=labels.device_view(labels.destination(db)))


@router.post('/device')
def configure(body: Configuration, response: Response, db: Session = Depends(get_db), user=Depends(require_owner)):
    response.headers['Cache-Control'] = 'no-store'
    return labels.configure(db, user, body.confirm, body.rotate)


@router.get('/catalog')
def catalog(mode: Literal['products', 'grades', 'lots'] = 'products', q: str = Query('', max_length=150),
            page: int = Query(1, ge=1, le=20000), db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    if mode == 'lots':
        query = db.query(ReceivingLot.id, ReceivingLot.name, ReceivingLot.notes, ReceivingLot.received_on)
        if q.strip():
            query = query.filter(ReceivingLot.name.ilike('%'+q.strip().replace('%', '\\%').replace('_', '\\_')+'%', escape='\\'))
        return dict(total=query.count(), items=[dict(row._mapping) for row in query.order_by(
            ReceivingLot.received_on.desc(), ReceivingLot.id).offset((page-1)*30).limit(30)])
    query = labels.items_query(db)
    if q.strip():
        query = query.filter(build_search(db, q).condition)
    if mode == 'grades':
        groups = query.with_entities(Item.group_key, func.min(Item.name).label('name'),
                                     func.count(Item.id).label('count')).filter(
            Item.group_key.isnot(None), Item.group_key != '').group_by(Item.group_key)
        return dict(total=groups.count(), items=[dict(row._mapping) for row in groups.order_by(
            Item.group_key).offset((page-1)*30).limit(30)])
    return dict(total=query.count(), items=[labels.item_view(item) for item in query.order_by(
        Item.created_at.desc(), Item.id).offset((page-1)*30).limit(30)])


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_ids: list[UUID] = Field(default_factory=list, max_length=labels.MAX_ITEMS)
    group_keys: list[str] = Field(default_factory=list, max_length=50)
    lot_ids: list[UUID] = Field(default_factory=list, max_length=50)


@router.post('/selection')
def selection(body: Selection, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    if not (body.item_ids or body.group_keys or body.lot_ids):
        return dict(items=[])
    query = labels.items_query(db).filter(or_(Item.id.in_(body.item_ids), Item.group_key.in_(body.group_keys),
        Item.id.in_(select(ReceivingLotItem.item_id).where(ReceivingLotItem.lot_id.in_(body.lot_ids)))))
    items = query.order_by(Item.group_key, Item.color, Item.name, Item.size, Item.id).limit(labels.MAX_ITEMS+1).all()
    if len(items) > labels.MAX_ITEMS:
        raise HTTPException(422, f'Selecione até {labels.MAX_ITEMS} produtos por vez.')
    missing = set(body.item_ids) - {i.id for i in items}
    if missing:
        raise HTTPException(409, 'Um produto foi excluído ou desativado. Atualize a seleção no estoque.')
    return dict(items=[labels.item_view(item) for item in items])


@router.get('/preview/{item_id}')
def preview(item_id: UUID, layout_id: str | None = Query(None, max_length=30),
            layout_revision: int | None = Query(None, ge=1),
            db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    item = labels.items_query(db).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, 'Produto não encontrado.')
    if bool(layout_id) != bool(layout_revision):
        raise HTTPException(422, 'Informe o modelo e sua versão para conferir a etiqueta.')
    design = layouts.view(layouts.find(db, layout_id, layout_revision)) if layout_id else None
    return Response(labels.preview_png(item, design), media_type='image/png', headers={'Cache-Control': 'no-store'})


@router.get('/layouts')
def label_layouts(response: Response, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    response.headers['Cache-Control'] = 'no-store'
    return layouts.listing(db)


@router.post('/layouts/preview')
def design_preview(body: DesignPreview, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    if body.item_id:
        item = labels.items_query(db).filter(Item.id == body.item_id).first()
        if not item:
            raise HTTPException(404, 'Produto não encontrado.')
    else:
        from types import SimpleNamespace
        item = SimpleNamespace(id=UUID(int=0), name='Camiseta ELEVEN', inventory_code='INV-A7K4P2',
                               size='L', color='Navy', barcode='7891234567890',
                               sale_price=Decimal('72'), sale_currency='USD')
    try:
        image = labels.preview_png(item, dict(config=body.config.model_dump()))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return Response(image, media_type='image/png', headers={'Cache-Control': 'no-store'})


@router.put('/layouts/{key}')
def save_design(key: str, body: LayoutInput, db: Session = Depends(get_db), user=Depends(operator)):
    return layouts.save(db, key, body)


@router.delete('/layouts/{key}')
def delete_design(key: str, version: int = Query(ge=1), db: Session = Depends(get_db), user=Depends(operator)):
    return layouts.delete(db, key, version)


class LabelLine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: UUID
    copies: int = Field(ge=1, le=labels.MAX_COPIES, strict=True)
    code: str = Field(max_length=10)
    name: str = Field(min_length=1, max_length=200)
    size: str | None = Field(default=None, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    sale_price: Decimal | None = Field(default=None, ge=0)
    sale_currency: str | None = Field(default=None, max_length=10)


class BatchInput(Confirmation):
    request_key: UUID
    items: list[LabelLine] = Field(min_length=1, max_length=labels.MAX_ITEMS)
    layout_id: str | None = Field(default=None, pattern=r'^product-[a-f0-9]{20}$')
    layout_revision: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode='after')
    def layout_reference(self):
        if bool(self.layout_id) != bool(self.layout_revision):
            raise ValueError('Informe o modelo e sua versão para conferir a etiqueta.')
        return self


@router.post('/batches')
def enqueue(body: BatchInput, db: Session = Depends(get_db), user=Depends(operator)):
    return labels.enqueue(db, user, body)


def owned_batch(db, user, batch_id):
    from ...services.access_policy import is_owner
    root = db.query(PrintJob).filter_by(id=batch_id, source=labels.PURPOSE, parent_id=None).first()
    if not root or (root.user_id != user.id and not is_owner(user)):
        raise HTTPException(404, 'Impressão não encontrada.')
    return root


@router.get('/batches')
def history(db: Session = Depends(get_db), user=Depends(operator)):
    from ...services.access_policy import is_owner
    query = db.query(PrintJob).filter_by(source=labels.PURPOSE, parent_id=None)
    if not is_owner(user):
        query = query.filter(PrintJob.user_id == user.id)
    return [dict(id=str(j.id), created_at=j.created_at, name=j.snapshot.get('name'))
            for j in query.order_by(PrintJob.created_at.desc()).limit(20)]


@router.get('/batches/{batch_id}')
def batch(batch_id: UUID, db: Session = Depends(get_db), user=Depends(operator)):
    return labels.batch_view(db, owned_batch(db, user, batch_id))


@router.post('/batches/{batch_id}/cancel')
def cancel(batch_id: UUID, body: Confirmation, db: Session = Depends(get_db), user=Depends(operator)):
    if not body.confirm:
        raise HTTPException(422, 'Confirme o cancelamento das etiquetas ainda não enviadas.')
    # Serialize against claim before changing pending jobs. Claimed jobs cannot be recalled.
    labels.destination(db, lock=True)
    root = owned_batch(db, user, batch_id)
    for job in db.query(PrintJob).filter(PrintJob.source == labels.PURPOSE,
            or_(PrintJob.id == root.id, PrintJob.parent_id == root.id), PrintJob.status == 'pending').all():
        job.status, job.finished_at = 'cancelled', utcnow()
    db.commit()
    return labels.batch_view(db, root)
