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
        if not self.sender_id and not self.remetente:raise ValueError('Informe remetente cadastrado ou dados do remetente.')
        return self


class SelectFreight(BaseModel):
    model_config=ConfigDict(extra='forbid')
    freight_id:uuid.UUID
    service:int


class FreightId(BaseModel):
    model_config=ConfigDict(extra='forbid')
    freight_id:uuid.UUID


def preview(action):
    from .assistant_controls import preview_reply
    p=action.payload
    if action.kind=='frete_emitir':
        return preview_reply(action, (f"Emitir etiqueta para {p['recipient']}, serviço {p['service_name']}, valor R$ {p['price']}. "
                f"Ambiente: {p['environment']}. O valor será debitado do saldo SuperFrete.\n"
                f"Ao confirmar, o PDF será enviado ao Telegram e impresso automaticamente quando liberado.\nDiga ‘confirmo’ para pagar e emitir ou ‘cancela’. Nenhuma compra realizada ainda.\nIdentificador da prévia: {action.id}"))
    from .assistant_replies import DocumentReply
    text = (f"Conferiu a etiqueta de {p['recipient']}? Diga ‘confirmo’ para imprimir uma cópia A4 na loja ou ‘cancela’. "
            f"A compra já foi realizada; cancelar aqui cancela apenas a impressão.\nIdentificador da prévia: {action.id}")
    return preview_reply(action,text,p["label_url"])


def execute(db,message,identity,name,args):
    if not message.should_reply or not may_schedule(db,message,identity):return {'erro':'Fretes exigem pedido direto de ADMIN/GERENTE habilitado.'}
    try:
        if name=='cotar_superfrete':
            a=BotQuote.model_validate(args)
            previous=db.query(FreightOrder).filter_by(request_key=message.id).first()
            if previous:return sf.summary(previous)
            address_id=a.address_id
            if not address_id:
                from .address_book import save_or_reuse
                saved,_=save_or_reuse(db,a.endereco.model_dump(),message.user_id)
                address_id=saved.id
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
            from .freight_labels import watch_label
            with SessionLocal() as external:
                row=sf.locked(external,key)
                watch_label(external,row,auto_print=True,message=message)
                row=sf.checkout(external,key,Decimal(action.payload['price']))
                external.commit()
                if row.state not in ('released','posted','delivered'):
                    return row.error or 'Não foi possível confirmar a emissão. Consulte o frete no gestor.'
            action.status='executed';action.result_id=key;action.executed_at=utcnow()
            return 'Etiqueta paga. Vou buscar o PDF automaticamente, enviá-lo aqui e colocar uma cópia A4 na fila da loja assim que a SuperFrete liberar. O PDF também aparecerá no gestor. Não é necessário pagar novamente.'
        devices=db.query(PrintDevice).filter_by(active=True).limit(2).all()
        if len(devices)!=1:return 'Configure uma única impressora ativa no ERP.'
        # Printing is read-only externally; queue and confirmation commit together.
        job=sf.print_label(db,key,devices[0].id,action.id,message.user_id)
        action.status='executed';action.result_id=job.id;action.executed_at=utcnow()
        return 'Etiqueta enviada à fila da loja: uma cópia A4. Confira a saída na impressora.'
    except HTTPException as e:return str(e.detail)


def quote_preview(order):
    """Stable option order and quote identity, persisted with the bot response."""
    lines=[f"Cotação para {order.payload['to']['name']}, remetente {order.payload['from']['name']}:"]
    for index,rate in enumerate(order.rates,1):
        price=f"{float(rate['price']):.2f}".replace('.',',')
        days=rate.get('delivery_time')
        lines.append(f"{index}. {rate.get('name',rate['id'])} — R$ {price}"+(f" — prazo estimado {days} dias" if days is not None else ''))
    lines += ['Responda com o número ou nome do serviço. Depois mostrarei o valor final para você confirmar o pagamento.',f'Cotação: {order.id}']
    from .assistant_controls import InteractiveReply, button
    return InteractiveReply('\n'.join(lines[:-1]), [[button(f"{r.get('name',r['id'])} · R$ {float(r['price']):.2f}", f"q:{order.id.hex}:{r['id']}")] for r in order.rates])


def service_choice(db,message,identity,content):
    import re
    from datetime import timedelta
    from ..models.assistant import AssistantMessage
    match=re.fullmatch(r'(?:(?:opção|opcao|quero|escolho)\s+)?(\d{1,2}|sedex|pac|mini\s*envios)[.! ]*',content,re.I)
    callback=re.fullmatch(r'/servico ([0-9a-f]{32}):(\d{1,3})',content)
    if not (match or callback) or not message.should_reply or not may_schedule(db,message,identity):return None
    query=db.query(FreightOrder).join(AssistantMessage,AssistantMessage.id==FreightOrder.request_key).filter(
        FreightOrder.user_id==message.user_id,
        AssistantMessage.channel==message.channel,
        AssistantMessage.conversation_id==message.conversation_id,
        AssistantMessage.created_at<=message.created_at,
    )
    if callback:query=query.filter(FreightOrder.id==uuid.UUID(callback[1]))
    else:
        # A short "2" answers the quote just shown, never an older customer's
        # order after a failed/new request. Callback buttons already carry an ID.
        latest=db.query(AssistantMessage).filter(AssistantMessage.user_id==message.user_id,
            AssistantMessage.channel==message.channel,AssistantMessage.conversation_id==message.conversation_id,
            AssistantMessage.created_at<=message.created_at,AssistantMessage.id!=message.id,
            AssistantMessage.status=='done',AssistantMessage.response.isnot(None)).order_by(AssistantMessage.created_at.desc()).first()
        if not latest:return None
        query=query.filter(FreightOrder.request_key==latest.id)
    order=query.order_by(FreightOrder.created_at.desc()).first()
    if not order:return 'Cotação indisponível para seu usuário nesta conversa.' if callback else None
    if order.state not in ('quoted','pending'):
        return 'Esta cotação já avançou ou precisa de conferência. Consulte a etiqueta existente antes de emitir outra.'
    created=order.created_at.replace(tzinfo=utcnow().tzinfo) if order.created_at.tzinfo is None else order.created_at
    if order.state=='quoted' and utcnow()-created>timedelta(minutes=30):return 'Essa cotação expirou. Peça uma nova cotação com os mesmos dados; nenhuma etiqueta foi comprada.'
    value=match[1].lower() if match else ''
    if callback:
        rate=next((r for r in order.rates if r['id']==int(callback[2])),None)
    elif value.isdigit():
        index=int(value)-1
        rate=order.rates[index] if 0<=index<len(order.rates) else None
    else:rate=next((r for r in order.rates if re.sub(r'\s','',str(r.get('name','')).lower())==re.sub(r'\s','',value)),None)
    if not rate:return 'Escolha uma das opções disponíveis:\n'+quote_preview(order)
    if order.state=='pending' and order.service!=rate['id']:return 'Já há uma prévia com outro serviço. Cancele essa solicitação e peça uma nova cotação para trocar o serviço.'
    existing=db.query(AssistantAction).join(AssistantMessage,AssistantMessage.id==AssistantAction.source_message_id).filter(
        AssistantAction.user_id==message.user_id,AssistantAction.kind=='frete_emitir',AssistantAction.status=='draft',
        AssistantAction.payload['freight_id'].as_string()==str(order.id),
        AssistantMessage.channel==message.channel,AssistantMessage.conversation_id==message.conversation_id,
        AssistantAction.created_at>=utcnow()-timedelta(hours=24),
    ).first()
    if existing:return preview(existing)
    result=execute(db,message,identity,'preparar_etiqueta',{'freight_id':str(order.id),'service':rate['id']})
    return result.get('confirmacao') or result.get('erro') or result.get('error') or 'Não foi possível preparar a etiqueta. Nenhum pagamento foi realizado; confira o frete no gestor.'
