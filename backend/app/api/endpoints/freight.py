from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException, Request, Response
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
    auto_print:bool=True
    device_id:UUID|None=None


@router.post('/orders/{key}/pay')
def pay(key:UUID,body:PayInput,user=Depends(manager),db:Session=Depends(get_db)):
    from ...services.freight_labels import watch_label
    row=sf.locked(db,key)
    if row.state not in ('pending','released','posted','delivered'):
        raise HTTPException(409,'Confira o estado do frete antes de prosseguir.')
    watch_label(db,row,auto_print=body.auto_print,device_id=body.device_id)
    row=sf.checkout(db,key,body.expected_price)
    db.commit()
    return sf.summary(row)


@router.post('/orders/{key}/refresh')
def refresh(key:UUID,user=Depends(manager),db:Session=Depends(get_db)):
    row=sf.refresh(db,key)
    if row.state in ('released','posted','delivered') and (not row.label_pdf or row.auto_print and not row.print_job_id):
        from ...models.assistant import utcnow
        row.label_status='ready' if row.label_pdf else 'waiting'
        row.label_check_at=utcnow();row.label_attempts=0
        db.commit()
    return sf.summary(row)


@router.get('/orders/{key}/pdf')
def pdf(key:UUID,user=Depends(manager),db:Session=Depends(get_db)):
    row=db.get(FreightOrder,key)
    if not row or not row.label_pdf:raise HTTPException(404,'PDF ainda em processamento.')
    return Response(row.label_pdf,media_type='application/pdf',headers={
        'Content-Disposition':'inline; filename="etiqueta.pdf"','Cache-Control':'private, no-store'})


class LabelPrintInput(BaseModel):
    device_id:UUID
    request_key:UUID


@router.post('/orders/{key}/print')
def print_label(key:UUID,body:LabelPrintInput,user=Depends(manager),db:Session=Depends(get_db)):
    row=sf.locked(db,key)
    if row.auto_print and not row.print_job_id:
        import uuid
        # A manual click while the automatic job is pending fulfils that same print.
        body.request_key=uuid.uuid5(uuid.NAMESPACE_URL,'eleven:freight:auto-print:'+str(key))
    job=sf.print_label(db,key,body.device_id,body.request_key,user.id)
    if row.auto_print and not row.print_job_id:row.print_job_id=job.id
    db.commit();return {'id':str(job.id),'status':job.status}


@router.post('/webhooks/superfrete')
async def superfrete_webhook(request:Request,db:Session=Depends(get_db)):
    import hashlib,hmac,json
    from ...models.assistant import utcnow
    from .assistant import bounded_body
    from ...services.freight_webhook import signing_secret
    secret=signing_secret(db)
    if not secret:raise HTTPException(503,'Webhook não configurado.')
    body=b''.join([chunk async for chunk in bounded_body(request)])
    signature=request.headers.get('X-ME-Signature','').removeprefix('sha256=')
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):raise HTTPException(403,'Assinatura inválida.')
    try:event=json.loads(body)
    except (ValueError,UnicodeError):raise HTTPException(400,'JSON inválido.')
    if not isinstance(event,dict) or not isinstance(event.get('data'),dict):raise HTTPException(400,'Evento inválido.')
    if event.get('event') not in ('order.generated','order.released','order.cancelled','order.posted','order.delivered'):
        return {'ok':True}
    row=db.query(FreightOrder).filter_by(provider_id=str(event['data'].get('id','')),environment=sf.environment()).with_for_update().first()
    # A signed notification merely schedules an authenticated fetch of an already paid order.
    if row and row.state in ('released','posted','delivered','paying','uncertain'):
        if row.label_status in ('none','failed'):row.label_status='waiting';row.label_attempts=0
        if not row.label_pdf or row.auto_print and not row.print_job_id:row.label_check_at=utcnow()
        db.commit()
    return {'ok':True}
