"""Bot freight workflow: quote, price approval, paid PDF review, print approval."""
import uuid
from pydantic import BaseModel, Field, ConfigDict, model_validator
from fastapi import HTTPException
from ..database import SessionLocal
from ..models.assistant import AssistantAction, utcnow
from ..models.address_book import SavedAddress,FreightOrder
from ..models.printing import PrintSender,PrintDevice
from ..schemas.address_book import AddressData
from .assistant_schedule import may_schedule
from . import superfrete as sf


class BotQuote(BaseModel):
    model_config=ConfigDict(extra='forbid')
    address_id:uuid.UUID|None=None
    endereco:AddressData|None=None
    sender_id:str|None=Field(default=None,max_length=30)
    remetente:AddressData|None=None
    package:sf.Package
    products:list[sf.Product]=Field(min_length=1,max_length=50)
    non_commercial:bool=False
    invoice:str=Field(default='',max_length=44)
    @model_validator(mode='after')
    def destination(self):
        if bool(self.address_id)==bool(self.endereco):raise ValueError('Informe endereço salvo OU dados do endereço.')
        if bool(self.sender_id)==bool(self.remetente):raise ValueError('Informe remetente cadastrado OU dados do remetente.')
        return self


class SelectFreight(BaseModel):
    model_config=ConfigDict(extra='forbid')
    freight_id:uuid.UUID
    service:int


class FreightId(BaseModel):
    model_config=ConfigDict(extra='forbid')
    freight_id:uuid.UUID


def preview(action):
    p=action.payload
    if action.kind=='frete_emitir':
        return (f"Emitir etiqueta para {p['recipient']}, serviço {p['service_name']}, valor R$ {p['price']}. "
                f"Ambiente: {p['environment']}. O valor será debitado do saldo SuperFrete.\n"
                f"Diga ‘confirmo’ para pagar e emitir ou ‘cancela’. Nenhuma compra realizada ainda.\nIdentificador da prévia: {action.id}")
    from .assistant_replies import DocumentReply
    text = (f"Conferiu a etiqueta de {p['recipient']}? Diga ‘confirmo’ para imprimir uma cópia A4 na loja ou ‘cancela’. "
            f"A compra já foi realizada; cancelar aqui cancela apenas a impressão.\nIdentificador da prévia: {action.id}")
    return DocumentReply(text,p["label_url"])


def execute(db,message,identity,name,args):
    if not message.should_reply or not may_schedule(db,message,identity):return {'erro':'Fretes exigem pedido direto de ADMIN/GERENTE habilitado.'}
    try:
        if name=='cotar_superfrete':
            a=BotQuote.model_validate(args)
            previous=db.query(FreightOrder).filter_by(request_key=message.id).first()
            if previous:return sf.summary(previous)
            address_id=a.address_id
            if not address_id:
                saved=SavedAddress(label=a.endereco.nome or 'Endereço do bot',data=a.endereco.model_dump(),created_by=message.user_id)
                db.add(saved);db.flush();address_id=saved.id
            q=sf.QuoteInput(request_key=message.id,address_id=address_id,sender_id=a.sender_id,remetente=a.remetente,package=a.package,products=a.products,non_commercial=a.non_commercial,invoice=a.invoice)
            row=sf.quote_order(db,q,message.user_id)
            return {**sf.summary(row),'instrucao':'Mostre serviços e valores e peça que o usuário escolha. Não emita nesta mensagem.'}
        if name=='preparar_etiqueta':
            a=SelectFreight.model_validate(args)
            previous=db.query(AssistantAction).filter_by(source_message_id=message.id).first()
            if previous:
                from .assistant_schedule import action_preview
                return {'confirmacao':action_preview(previous)}
            # Separate transaction: provider effects must survive outer inbox rollback.
            with SessionLocal() as external:
                order=external.get(FreightOrder,a.freight_id)
                if not order or order.user_id!=message.user_id:return {'erro':'Cotação não disponível para este usuário. Escolha um serviço na próxima mensagem.'}
                row=sf.cart(external,a.freight_id,a.service)
                if row.state!='pending':return sf.summary(row)
                selected=next((r for r in row.rates if r['id']==row.service),{})
                payload={'freight_id':str(row.id),'recipient':row.payload['to']['name'],'price':str(row.price),
                         'service_name':selected.get('name',str(row.service)),'environment':row.environment}
            action=AssistantAction(source_message_id=message.id,user_id=message.user_id,kind='frete_emitir',payload=payload)
            db.add(action);db.flush();return {'confirmacao':preview(action)}
        a=FreightId.model_validate(args)
        with SessionLocal() as external:
            order=external.get(FreightOrder,a.freight_id)
            if not order or order.user_id!=message.user_id:return {'erro':'Frete não encontrado para seu usuário.'}
            row=sf.refresh(external,a.freight_id)
            result=sf.summary(row)
        if name=='consultar_etiqueta':return result
        previous=db.query(AssistantAction).filter_by(source_message_id=message.id).first()
        if previous:
            from .assistant_schedule import action_preview
            return {'confirmacao':action_preview(previous)}
        if result['state'] not in ('released','posted','delivered') or not result['label_url']:return {'erro':'Etiqueta ainda não disponível para conferir e imprimir.'}
        action=AssistantAction(source_message_id=message.id,user_id=message.user_id,kind='frete_imprimir',payload={'freight_id':str(a.freight_id),'recipient':result['recipient'],'label_url':result['label_url']})
        db.add(action);db.flush();return {'confirmacao':preview(action),'pdf':result['label_url']}
    except HTTPException as e:return {'erro':e.detail}


def confirm(db,message,action):
    from decimal import Decimal
    from .assistant_replies import DocumentReply
    key=uuid.UUID(action.payload['freight_id'])
    try:
        if action.kind=='frete_emitir':
            with SessionLocal() as external:
                row=sf.checkout(external,key,Decimal(action.payload['price']))
                if row.state not in ('released','posted','delivered'):
                    return row.error or 'Não foi possível confirmar a emissão. Consulte o frete no gestor.'
                try:row=sf.refresh(external,key)
                except HTTPException:pass
                result=sf.summary(row)
            action.status='executed';action.result_id=key;action.executed_at=utcnow()
            if not result['label_url']:return 'Etiqueta paga. O PDF ainda não foi disponibilizado; peça para consultar a etiqueta '+str(key)+'. Não pague novamente.'
            next_action=AssistantAction(source_message_id=message.id,user_id=message.user_id,kind='frete_imprimir',payload={'freight_id':str(key),'recipient':result['recipient'],'label_url':result['label_url']})
            db.add(next_action);db.flush()
            return DocumentReply('Etiqueta emitida. '+preview(next_action),result['label_url'])
        devices=db.query(PrintDevice).filter_by(active=True).limit(2).all()
        if len(devices)!=1:return 'Configure uma única impressora ativa no ERP.'
        # Printing is read-only externally; queue and confirmation commit together.
        job=sf.print_label(db,key,devices[0].id,action.id,message.user_id)
        action.status='executed';action.result_id=job.id;action.executed_at=utcnow()
        return 'Etiqueta enviada à fila da loja: uma cópia A4. Confira a saída na impressora.'
    except HTTPException as e:return str(e.detail)
