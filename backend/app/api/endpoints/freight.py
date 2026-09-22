from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ...database import get_db
from ...config import settings
from ...models.address_book import FreightOrder
from ...services import superfrete as sf
from .address_manager import manager
router=APIRouter()


@router.get('/status')
def status(user=Depends(manager)):
    return {'configured':bool(settings.SUPERFRETE_TOKEN and settings.SUPERFRETE_CONTACT_EMAIL),'environment':sf.environment()}


@router.get('/orders')
def orders(offset:int=Query(0,ge=0),user=Depends(manager),db:Session=Depends(get_db)):
    q=db.query(FreightOrder)
    return {'total':q.count(),'items':[sf.summary(r) for r in q.order_by(FreightOrder.created_at.desc()).offset(offset).limit(30)]}


@router.post('/quotes')
def quote(body:sf.QuoteInput,user=Depends(manager),db:Session=Depends(get_db)):
    row=sf.quote_order(db,body,user.id);db.commit();return sf.summary(row)


class CartInput(BaseModel):
    service:int


@router.post('/orders/{key}/cart')
def cart(key:UUID,body:CartInput,user=Depends(manager),db:Session=Depends(get_db)):
    return sf.summary(sf.cart(db,key,body.service))


class PayInput(BaseModel):
    expected_price:Decimal=Field(ge=0,max_digits=12,decimal_places=2)


@router.post('/orders/{key}/pay')
def pay(key:UUID,body:PayInput,user=Depends(manager),db:Session=Depends(get_db)):
    row=sf.checkout(db,key,body.expected_price)
    if row.state in ('released','posted','delivered'):
        try:row=sf.refresh(db,key)
        except HTTPException:pass
    return sf.summary(row)


@router.post('/orders/{key}/refresh')
def refresh(key:UUID,user=Depends(manager),db:Session=Depends(get_db)):
    return sf.summary(sf.refresh(db,key))


class LabelPrintInput(BaseModel):
    device_id:UUID
    request_key:UUID


@router.post('/orders/{key}/print')
def print_label(key:UUID,body:LabelPrintInput,user=Depends(manager),db:Session=Depends(get_db)):
    job=sf.print_label(db,key,body.device_id,body.request_key,user.id)
    db.commit();return {'id':str(job.id),'status':job.status}
