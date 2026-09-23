from .sender_addresses import sender_lines
import hashlib
from datetime import timedelta
from fastapi import HTTPException
from ..models.printing import PrintJob, PrintDevice, PrintSender
from ..models.address_book import PrintLayout, SavedAddress
from ..models.assistant import utcnow
from ..schemas.address_book import LayoutConfig


def get_layout(db, country):
    row = db.get(PrintLayout, country.lower())
    return LayoutConfig.model_validate(row.config).model_dump() if row else LayoutConfig().model_dump()


def compose(db, body):
    from .assistant_printing import AddressArgs
    data = body.data.model_dump()
    data['endereco'] = ', '.join(x for x in [data['endereco'],data['numero'],data['bairro'],data['complemento']] if x)
    args = AddressArgs.model_validate({k:v for k,v in data.items() if k in AddressArgs.model_fields} | {'remetente':body.sender_id})
    sender = None
    if args.pais=='BR':
        row = db.get(PrintSender,body.sender_id)
        if not row or not row.active: raise HTTPException(400,'Escolha um remetente ativo.')
        sender = {'nome':row.name,'linhas':sender_lines(row)}
    return {'endereco':args.model_dump(),'remetente':sender,'layout':get_layout(db,args.pais),'editor':body.data.model_dump(),'sender_id':body.sender_id}


def enqueue_address(db, body, user_id):
    from .assistant_printing import render_address
    device=db.query(PrintDevice).filter_by(id=body.device_id,active=True).with_for_update().first()
    if not device: raise HTTPException(404,'Impressora não encontrada.')
    previous=db.query(PrintJob).filter_by(request_key=body.request_key).first()
    if previous:
        if previous.user_id!=user_id or previous.device_id!=body.device_id or previous.address_id!=body.address_id or previous.parent_id!=body.parent_id or (previous.snapshot or {}).get('editor')!=body.data.model_dump() or (previous.snapshot or {}).get('sender_id')!=body.sender_id:
            raise HTTPException(409,'Identificador já utilizado para outra impressão. Atualize antes de enviar.')
        return previous
    if body.address_id:
        address=db.get(SavedAddress,body.address_id)
        if not address or not address.active:raise HTTPException(404,'Endereço não encontrado.')
    if body.parent_id and not db.get(PrintJob,body.parent_id):raise HTTPException(404,'Impressão original não encontrada.')
    snapshot=compose(db,body)
    pdf=render_address(snapshot)
    job=PrintJob(device_id=device.id,user_id=user_id,request_key=body.request_key,pdf=pdf,
                 sha256=hashlib.sha256(pdf).hexdigest(),expires_at=utcnow()+timedelta(hours=24),
                 snapshot=snapshot,address_id=body.address_id,parent_id=body.parent_id,source='erp')
    db.add(job);db.flush()
    return job
