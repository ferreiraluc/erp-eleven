"""Address manager, customer links and printer history. No device credentials accepted."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import or_, cast, String, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ...database import get_db
from ...dependencies import require_role
from ...models.address_book import SavedAddress, PrintLayout
from ...models.printing import PrintJob, PrintDevice, PrintSender
from ...models.cliente import Cliente
from ...models.pdv import PdvCliente
from ...models.usuario import Usuario
from ...models.assistant import utcnow
from ...schemas.address_book import AddressInput, SenderInput, LayoutInput, LayoutConfig, PrintInput
from ...services.address_manager import compose, enqueue_address
from ...services.assistant_printing import render_address
from ...services.sender_addresses import sender_address

router=APIRouter()
manager=require_role(['ADMIN','GERENTE'])


def item(row):
    return {'id':str(row.id),'label':row.label,'cliente_id':str(row.cliente_id) if row.cliente_id else None,
            'pdv_cliente_id':str(row.pdv_cliente_id) if row.pdv_cliente_id else None,
            'data':row.data,'active':row.active,'version':row.version,'updated_at':row.updated_at}


def pattern(q):
    return '%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'


def validate_customer(db,body):
    for model,key in [(Cliente,body.cliente_id),(PdvCliente,body.pdv_cliente_id)]:
        if key and not db.query(model).filter_by(id=key,ativo=True).first():raise HTTPException(400,'Cliente não encontrado ou inativo.')


@router.get('/customers')
def customers(q:str=Query('',max_length=100),user=Depends(manager),db:Session=Depends(get_db)):
    output=[]
    for model,kind,document in [(Cliente,'pedidos',Cliente.cpf),(PdvCliente,'pdv',PdvCliente.doc)]:
        rows=db.query(model).filter(model.ativo.is_(True),or_(model.nome.ilike(pattern(q),escape='\\'),model.telefone.ilike(pattern(q),escape='\\'),document.ilike(pattern(q),escape='\\'))).order_by(model.nome).limit(20).all()
        output += [{'id':str(r.id),'kind':kind,'nome':r.nome,'telefone':r.telefone,'cpf':getattr(r,'cpf',getattr(r,'doc',None)),'endereco':getattr(r,'endereco','')} for r in rows]
    return output


@router.get('/addresses')
def addresses(q:str=Query('',max_length=100),country:str='',customer_id:uuid.UUID|None=None,active:bool=True,
              offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),user=Depends(manager),db:Session=Depends(get_db)):
    query=db.query(SavedAddress).filter(SavedAddress.active==active)
    if q:query=query.filter(or_(SavedAddress.label.ilike(pattern(q),escape='\\'),cast(SavedAddress.data,String).ilike(pattern(q),escape='\\')))
    if country:query=query.filter(SavedAddress.data['pais'].as_string()==country)
    if customer_id:query=query.filter(or_(SavedAddress.cliente_id==customer_id,SavedAddress.pdv_cliente_id==customer_id))
    return {'total':query.count(),'items':[item(r) for r in query.order_by(SavedAddress.updated_at.desc(),SavedAddress.id).offset(offset).limit(limit)]}


@router.post('/addresses')
def create_address(body:AddressInput,user=Depends(manager),db:Session=Depends(get_db)):
    validate_customer(db,body)
    row=SavedAddress(label=body.label,data=body.data.model_dump(),cliente_id=body.cliente_id,pdv_cliente_id=body.pdv_cliente_id,created_by=user.id,active=body.active)
    db.add(row);db.commit();return item(row)


@router.put('/addresses/{key}')
def update_address(key:uuid.UUID,body:AddressInput,user=Depends(manager),db:Session=Depends(get_db)):
    row=db.query(SavedAddress).filter_by(id=key).with_for_update().first()
    if not row:raise HTTPException(404,'Endereço não encontrado.')
    if row.version!=body.version:raise HTTPException(409,'Endereço alterado por outra pessoa. Atualize antes de salvar.')
    validate_customer(db,body)
    for attr in ['label','cliente_id','pdv_cliente_id','active']:setattr(row,attr,getattr(body,attr))
    row.data=body.data.model_dump();row.version+=1;row.updated_at=utcnow()
    db.commit();return item(row)


@router.get('/senders')
def senders(user=Depends(manager),db:Session=Depends(get_db)):
    return [{'id':r.id,'name':r.name,'lines':r.lines,'data':sender_address(r),'active':r.active,'version':r.version} for r in db.query(PrintSender).order_by(PrintSender.name)]


@router.post('/senders')
def create_sender(body:SenderInput,user=Depends(manager),db:Session=Depends(get_db)):
    row=PrintSender(id=uuid.uuid4().hex[:24],name=body.name,lines=body.lines,data=body.data.model_dump() if body.data else None,active=body.active)
    db.add(row);db.commit();return {'id':row.id}


@router.put('/senders/{key}')
def update_sender(key:str,body:SenderInput,user=Depends(manager),db:Session=Depends(get_db)):
    row=db.query(PrintSender).filter_by(id=key).with_for_update().first()
    if not row:raise HTTPException(404,'Remetente não encontrado.')
    if row.version!=body.version:raise HTTPException(409,'Remetente alterado por outra pessoa. Atualize.')
    row.name=body.name;row.lines=body.lines;row.data=body.data.model_dump() if body.data else None;row.active=body.active;row.version+=1
    db.commit();return {'id':row.id,'version':row.version}


@router.get('/layouts')
def layouts(user=Depends(manager),db:Session=Depends(get_db)):
    result=[]
    for key,name in [('br','Endereço Brasil'),('py','Endereço Paraguai')]:
        row=db.get(PrintLayout,key)
        result.append({'id':key,'name':row.name if row else name,'config':row.config if row else LayoutConfig().model_dump(),'version':row.version if row else 0})
    return result


@router.put('/layouts/{key}')
def save_layout(key:str,body:LayoutInput,user=Depends(manager),db:Session=Depends(get_db)):
    if key not in ['br','py']:raise HTTPException(400,'Modelo inválido.')
    row=db.query(PrintLayout).filter_by(id=key).with_for_update().first()
    if row and row.version!=body.version:raise HTTPException(409,'Modelo alterado. Atualize antes de salvar.')
    if not row:
        if body.version!=0:raise HTTPException(409,'Modelo alterado. Atualize antes de salvar.')
        row=PrintLayout(id=key,version=0);db.add(row)
    row.name=body.name;row.config=body.config.model_dump();row.version+=1;row.updated_at=utcnow()
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Modelo alterado. Atualize antes de salvar.') from None
    return {'version':row.version}


@router.get('/overview')
def overview(user=Depends(manager),db:Session=Depends(get_db)):
    return {'addresses':db.query(SavedAddress).filter_by(active=True).count(),
            'statuses':dict(db.query(PrintJob.status,func.count(PrintJob.id)).group_by(PrintJob.status).all()),
            'devices':[{'id':str(d.id),'name':d.name,'active':d.active,'last_seen_at':d.last_seen_at} for d in db.query(PrintDevice).order_by(PrintDevice.created_at)]}


def job_info(j,name=None):
    snapshot=j.snapshot or {}
    return {'id':str(j.id),'status':j.status,'source':j.source,'created_at':j.created_at,'finished_at':j.finished_at,
            'user':name,'recipient':snapshot.get('endereco',{}).get('nome','Arquivo PDF'),
            'country':snapshot.get('endereco',{}).get('pais',''),'editable':bool(j.snapshot) and j.source!='superfrete','pdf_available':bool(j.snapshot or j.pdf),
            'address_id':str(j.address_id) if j.address_id else None,'parent_id':str(j.parent_id) if j.parent_id else None}


@router.get('/history')
def history(q:str=Query('',max_length=100),status:str='',offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),user=Depends(manager),db:Session=Depends(get_db)):
    query=db.query(PrintJob,Usuario.nome).join(Usuario,Usuario.id==PrintJob.user_id)
    if status:query=query.filter(PrintJob.status==status)
    if q:query=query.filter(cast(PrintJob.snapshot,String).ilike(pattern(q),escape='\\'))
    return {'total':query.count(),'items':[job_info(j,n) for j,n in query.order_by(PrintJob.created_at.desc(),PrintJob.id).offset(offset).limit(limit)]}


@router.get('/history/{key}')
def detail(key:uuid.UUID,user=Depends(manager),db:Session=Depends(get_db)):
    row=db.get(PrintJob,key)
    if not row:raise HTTPException(404,'Impressão não encontrada.')
    return {**job_info(row),'snapshot':row.snapshot,'device_id':str(row.device_id)}


@router.get('/history/{key}/pdf')
def pdf(key:uuid.UUID,user=Depends(manager),db:Session=Depends(get_db)):
    row=db.get(PrintJob,key)
    if not row:raise HTTPException(404,'Impressão não encontrada.')
    data=row.pdf
    if not data and row.snapshot:
        if row.source=='superfrete':
            from ...services.superfrete import label_pdf
            data=label_pdf(row.snapshot.get('label_url'))
        else:data=render_address(row.snapshot)
    if not data:raise HTTPException(410,'O arquivo antigo não está mais disponível.')
    return Response(data,media_type='application/pdf',headers={'Cache-Control':'no-store','Content-Disposition':'inline; filename="endereco.pdf"'})


@router.post('/history/{key}/cancel')
def cancel(key:uuid.UUID,user=Depends(manager),db:Session=Depends(get_db)):
    row=db.query(PrintJob).filter_by(id=key).with_for_update().first()
    if not row:raise HTTPException(404,'Impressão não encontrada.')
    if row.status!='pending':raise HTTPException(409,'Já retirado pelo agente ou finalizado. Não é possível cancelar no servidor.')
    row.status='cancelled';row.pdf=b'';row.finished_at=utcnow();db.commit();return {'status':row.status}


@router.post('/preview')
def preview(body:PrintInput,user=Depends(manager),db:Session=Depends(get_db)):
    try:data=render_address(compose(db,body))
    except (ValueError,ValidationError) as exc:raise HTTPException(400,str(exc)) from None
    return Response(data,media_type='application/pdf',headers={'Cache-Control':'no-store'})


@router.post('/print')
def print_address(body:PrintInput,user=Depends(manager),db:Session=Depends(get_db)):
    try:row=enqueue_address(db,body,user.id)
    except (ValueError,ValidationError) as exc:raise HTTPException(400,str(exc)) from None
    db.commit();return job_info(row)
