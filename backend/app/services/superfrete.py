"""Official SuperFrete v0. Never retry a charge with an uncertain outcome."""
import re
from decimal import Decimal
from datetime import timedelta
from urllib.parse import quote, urlparse
import requests
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from uuid import UUID
from ..config import settings
from ..models.address_book import SavedAddress, FreightOrder
from ..models.printing import PrintSender
from ..schemas.address_book import AddressData
from ..models.assistant import utcnow


class Package(BaseModel):
    model_config=ConfigDict(extra='forbid')
    weight:float=Field(gt=0,le=120)
    height:float=Field(gt=0,le=200)
    width:float=Field(gt=0,le=200)
    length:float=Field(gt=0,le=200)


class Product(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=100)
    quantity:int=Field(ge=1,le=10000)
    unitary_value:Decimal=Field(ge=0,max_digits=12,decimal_places=2)


class QuoteInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:UUID
    address_id:UUID
    sender_id:str|None=Field(default=None,max_length=30)
    remetente:AddressData|None=None
    package:Package
    products:list[Product]=Field(min_length=1,max_length=50)
    non_commercial:bool=False
    invoice:str=Field(default='',max_length=44)
    @model_validator(mode='after')
    def fiscal(self):
        if not self.sender_id and not self.remetente:
            raise ValueError('Informe o remetente cadastrado ou seus dados nesta conversa.')
        if not self.non_commercial and not re.fullmatch(r'[0-9]{44}',self.invoice):
            raise ValueError('Informe a chave de nota fiscal (44 dígitos) ou selecione declaração de conteúdo para envio não comercial.')
        return self


def environment():return 'sandbox' if settings.SUPERFRETE_SANDBOX else 'production'


def call(method,path,body=None):
    if not settings.SUPERFRETE_TOKEN or not settings.SUPERFRETE_CONTACT_EMAIL:
        raise HTTPException(503,'Configure token e e-mail de contato técnico da SuperFrete no servidor.')
    base='https://sandbox.superfrete.com' if settings.SUPERFRETE_SANDBOX else 'https://api.superfrete.com'
    try:
        r=requests.request(method,base+'/api/v0/'+path,json=body,headers={
            'Authorization':'Bearer '+settings.SUPERFRETE_TOKEN,'User-Agent':f'ERP Eleven 1.0 ({settings.SUPERFRETE_CONTACT_EMAIL})'},timeout=(5,35),allow_redirects=False)
        if not 200<=r.status_code<300:
            if r.status_code in (400,422):
                try:fields=r.json().get('errors',{})
                except (ValueError,AttributeError):fields={}
                labels={'origin_postcode':'CEP de origem','destination_postcode':'CEP de destino',
                        'weight':'peso','height':'altura','width':'largura','length':'comprimento',
                        'document':'CPF/CNPJ','postal_code':'CEP','district':'bairro','address':'rua'}
                invalid=sorted({label for field in fields for key,label in labels.items() if key in field}) if isinstance(fields,dict) else []
                if invalid:raise HTTPException(400,'SuperFrete: confira '+', '.join(invalid)+'.')
            raise HTTPException(502,f'SuperFrete recusou a solicitação (HTTP {r.status_code}). Confira os dados e a conta.')
        return r.json()
    except (requests.RequestException,ValueError):raise HTTPException(502,'Não foi possível confirmar a resposta da SuperFrete.') from None


def party(data,recipient=False):
    if data.get('pais')!='BR':raise HTTPException(400,'SuperFrete exige endereço no Brasil.')
    names={'nome':'name','endereco':'address','numero':'number','bairro':'district','complemento':'complement','cidade':'city','estado':'state_abbr','cep':'postal_code','cpf':'document'}
    p={dst:str(data.get(src) or '').strip() for src,dst in names.items()}
    p['postal_code']=re.sub(r'\D','',p['postal_code']);p['document']=re.sub(r'\D','',p['document']);p['state_abbr']=p['state_abbr'].upper()
    limits={'name':50,'address':50,'number':10,'district':50,'complement':20,'city':50}
    if any(len(p[k])>n for k,n in limits.items()):raise HTTPException(400,'Endereço excede limites da transportadora (nome/rua/cidade: 50; complemento: 20).')
    missing=[label for key,label in [('name','nome'),('address','rua'),('district','bairro'),('city','cidade')] if not p[key]]
    if len(p['postal_code'])!=8:missing.append('CEP válido com 8 dígitos')
    if p['state_abbr'] not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():missing.append('UF válida')
    if missing:
        who='destinatário' if recipient else 'remetente'
        raise HTTPException(400,f'Complete no {who}: '+', '.join(missing)+'.')
    if recipient and (len(p['document']) not in (11,14) or len(set(p['document']))==1):raise HTTPException(400,'A emissão SuperFrete exige CPF/CNPJ do destinatário.')
    return p


def quote_order(db,body,user_id):
    previous=db.query(FreightOrder).filter_by(request_key=body.request_key).first()
    if previous:
        if previous.user_id!=user_id or previous.payload.get('_request')!=body.model_dump(mode='json',exclude={'request_key'}):raise HTTPException(409,'Identificador já utilizado com outros dados.')
        return previous
    from .address_book import resolve_address
    address=resolve_address(db,body.address_id)
    if not address or not address.active:raise HTTPException(400,'Escolha um endereço ativo.')
    if body.sender_id:
        sender=db.get(PrintSender,body.sender_id)
        if not sender or not sender.active:raise HTTPException(400,'Escolha um remetente ativo.')
        from .sender_addresses import sender_address
        sender_data=sender_address(sender)
        if body.remetente:sender_data.update(body.remetente.model_dump(exclude_unset=True))
    else:
        sender_data=body.remetente.model_dump()
    origin=party(sender_data);destination=party(address.data,True)
    payload={'from':origin,'to':destination,'volumes':body.package.model_dump(),
             'products':[{'name':p.name,'quantity':p.quantity,'unitary_value':float(p.unitary_value)} for p in body.products],
             'options':{'non_commercial':body.non_commercial,'own_hand':False,'receipt':False},'platform':'ERP Eleven',
             '_request':body.model_dump(mode='json',exclude={'request_key'})}
    if not body.non_commercial:payload['options']['invoice']={'number':body.invoice}
    rates=call('POST','calculator',{'from':{'postal_code':origin['postal_code']},'to':{'postal_code':destination['postal_code']},
             'services':'1,2,17','options':{'own_hand':False,'receipt':False,'use_insurance_value':False},'package':body.package.model_dump()})
    if not isinstance(rates,list):raise HTTPException(502,'Resposta de cotação inesperada.')
    rates=[r for r in rates if not r.get('has_error') and r.get('price') is not None and int(r.get('id',0)) in (1,2,17)]
    if not rates:raise HTTPException(400,'Nenhum serviço disponível para este pacote.')
    row=FreightOrder(request_key=body.request_key,user_id=user_id,address_id=address.id,environment=environment(),payload=payload,rates=rates)
    db.add(row);db.flush();return row


def summary(r):
    return {'id':str(r.id),'state':r.state,'environment':r.environment,'recipient':r.payload.get('to',{}).get('name'),
            'provider_id':r.provider_id,'service':r.service,'price':str(r.price) if r.price is not None else None,
            'tracking':r.tracking,'label_url':r.label_url,'label_status':r.label_status,'pdf_available':r.label_status=='ready','label_error':r.label_error,'auto_print':r.auto_print,'print_job_id':str(r.print_job_id) if r.print_job_id else None,'error':r.error,'created_at':r.created_at.isoformat() if r.created_at else None,
            'rates':[{'id':v['id'],'name':v.get('name'),'price':str(v['price']),'delivery_time':v.get('delivery_time')} for v in r.rates]}


def locked(db,key):
    row=db.query(FreightOrder).filter_by(id=key).populate_existing().with_for_update().first()
    if not row:raise HTTPException(404,'Frete não encontrado.')
    if row.environment!=environment():raise HTTPException(409,'Este frete pertence a outro ambiente SuperFrete.')
    return row


def cart(db,key,service):
    row=locked(db,key)
    if row.provider_id:return row
    if row.state!='quoted':raise HTTPException(409,'Operação já iniciada. Confira no SuperFrete antes de criar outro frete.')
    created=row.created_at.replace(tzinfo=utcnow().tzinfo) if row.created_at.tzinfo is None else row.created_at
    if utcnow()-created>timedelta(minutes=30):raise HTTPException(409,'Cotação expirada. Faça uma nova cotação.')
    rate=next((v for v in row.rates if v['id']==service),None)
    if not rate:raise HTTPException(400,'Serviço não pertence à cotação.')
    payload={k:v for k,v in row.payload.items() if not k.startswith('_')};payload['service']=service
    packages=rate.get('packages',[])
    if len(packages)==1 and packages[0].get('dimensions'):
        payload['volumes']={**packages[0]['dimensions'],'weight':packages[0]['weight']}
    row.service=service;row.state='creating';row.updated_at=utcnow();db.commit()  # durable before external effect
    try:
        result=call('POST','cart',payload)
        if not result.get('id') or result.get('price') is None:raise HTTPException(502,'Resposta incompleta ao criar frete.')
        row.provider_id=str(result['id']);row.price=Decimal(str(result['price']));row.state='pending'
    except (HTTPException,ValueError,TypeError):
        row.state='uncertain';row.error='Criação sem confirmação. Confira no painel SuperFrete; não repita automaticamente.'
    db.commit();return row


def checkout(db,key,expected_price):
    row=locked(db,key)
    if row.state in ('released','posted','delivered'):return row
    if row.state!='pending' or not row.provider_id:raise HTTPException(409,'Frete não está pronto para pagamento.')
    if row.price!=expected_price:raise HTTPException(409,'Valor mudou. Confira e confirme o valor atual.')
    row.state='paying';row.updated_at=utcnow();db.commit()
    try:
        result=call('POST','checkout',{'orders':[row.provider_id]})
        orders=result.get('purchase',{}).get('orders',[])
        order=next((o for o in orders if str(o.get('id'))==row.provider_id),None)
        if not result.get('success') or not order:raise HTTPException(502,'Pagamento não confirmado.')
        row.state='released';row.tracking=order.get('tracking');row.label_url=safe_label(order.get('print',{}).get('url'))
        row.error=None
    except (HTTPException,ValueError,TypeError):
        row.state='uncertain';row.error='Pagamento sem confirmação. Consulte o estado; não efetue outro pagamento.'
    db.commit();return row


def safe_label(url):
    if not url:return None
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in {'api.superfrete.com','sandbox.superfrete.com','web.superfrete.com','etiqueta.superfrete.com','storage.googleapis.com'} or parsed.username or parsed.password:return None
    return url


def refresh(db,key):
    row=locked(db,key)
    if not row.provider_id:raise HTTPException(409,'Sem identificador confirmado. Confira a criação no painel SuperFrete.')
    updated=row.updated_at.replace(tzinfo=utcnow().tzinfo) if row.updated_at.tzinfo is None else row.updated_at
    if row.state in ('creating','paying'):
        if utcnow()-updated<timedelta(minutes=2):raise HTTPException(409,'Operação em andamento; aguarde antes de consultar.')
        row.state='uncertain'
    result=call('GET','order/info/'+quote(row.provider_id,safe=''))
    if str(result.get('id'))!=row.provider_id:raise HTTPException(502,'Identificador retornado não confere.')
    state=result.get('status')
    if state=='generated':state='released'
    if state in ('pending','released','posted','delivered','cancelled'):
        # Do not re-enable payment after an uncertain charge until manually reconciled.
        if not (row.state=='uncertain' and state=='pending'):row.state=state;row.error=None
    row.tracking=result.get('tracking') or row.tracking
    sync_tracking(db,row)
    if row.state in ('released','posted','delivered') and not row.label_pdf:
        if row.label_status=='none':row.label_status='waiting';row.label_check_at=utcnow()
        row.updated_at=utcnow();db.commit()  # preserve confirmed payment/tracking even while the PDF is pending
        try:
            label=call('POST','tag/print',{'orders':[row.provider_id]})
            row.label_url=safe_label(label.get('url')) or row.label_url
        except HTTPException:
            row.label_error='Aguardando a SuperFrete liberar o PDF. A consulta será repetida automaticamente.'
    row.updated_at=utcnow();db.commit();return row


def sync_tracking(db,row):
    if row.environment!='production' or not row.tracking:return
    from ..models.rastreamento import Rastreamento
    if db.query(Rastreamento).filter_by(codigo_rastreio=row.tracking).first():return
    db.add(Rastreamento(codigo_rastreio=row.tracking,destinatario=row.payload['to']['name'],
           origem=row.payload['from']['city'],destino=row.payload['to']['city'],servico_provedor='SuperFrete',
           custo_emissao=row.price,created_by=row.user_id,descricao='Etiqueta emitida pelo gestor de endereços'))
    db.flush()


def label_pdf(url):
    url=safe_label(url)
    if not url:raise HTTPException(400,'URL de etiqueta indisponível ou não autorizada.')
    try:
        with requests.get(url,timeout=(5,30),stream=True,allow_redirects=False) as r:
            if r.status_code!=200:raise HTTPException(502,f'SuperFrete retornou HTTP {r.status_code} ao baixar o PDF. Nova tentativa automática; não pague novamente.')
            data=bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data)>5*1024*1024:raise HTTPException(400,'Etiqueta excede 5 MB.')
            if not data.startswith(b'%PDF-'):raise HTTPException(502,'Provedor não retornou um PDF.')
            return bytes(data)
    except requests.RequestException:raise HTTPException(502,'Falha ao baixar etiqueta.') from None


def print_label(db,key,device_id,request_key,user_id):
    import hashlib
    from ..models.printing import PrintDevice,PrintJob
    row=locked(db,key)
    if row.state not in ('released','posted','delivered') or not (row.label_url or row.label_pdf):raise HTTPException(400,'Consulte a etiqueta emitida antes de imprimir.')
    device=db.query(PrintDevice).filter_by(id=device_id,active=True).with_for_update().first()
    if not device:raise HTTPException(404,'Impressora não encontrada.')
    old=db.query(PrintJob).filter_by(request_key=request_key).first()
    if old:
        if old.user_id!=user_id or old.device_id!=device_id or (old.snapshot or {}).get('freight_id')!=str(key):raise HTTPException(409,'Identificador já utilizado.')
        return old
    pdf=row.label_pdf or label_pdf(row.label_url)
    job=PrintJob(user_id=user_id,device_id=device_id,request_key=request_key,pdf=pdf,sha256=hashlib.sha256(pdf).hexdigest(),
                 source='superfrete',address_id=row.address_id,
                 snapshot={'freight_id':str(key),'label_url':row.label_url,'endereco':{'nome':row.payload['to']['name'],'pais':'BR'}},
                 expires_at=utcnow()+timedelta(hours=24))
    db.add(job);db.flush();return job
