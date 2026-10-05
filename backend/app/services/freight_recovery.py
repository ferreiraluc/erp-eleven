"""Durable retries for safe requests and read-only reconciliation of uncertain carts.

The provider does not document an idempotency key. A tag identifies a created order,
but absence from a paginated list is never authorization to repeat a cart/checkout.
"""
from datetime import timedelta
from time import monotonic
from urllib.parse import quote
import logging
from fastapi import HTTPException
from ..database import SessionLocal
from ..models.address_book import FreightOrder
from ..models.assistant import AssistantMessage, AssistantDelivery, utcnow
from ..models.usuario import Usuario
from . import superfrete as sf

logger = logging.getLogger('freight_recovery')
_health = {}


def service_status():
    configured = bool(sf.settings.SUPERFRETE_TOKEN and sf.settings.SUPERFRETE_CONTACT_EMAIL)
    base = {'configured': configured, 'environment': sf.environment()}
    if not configured: return {**base, 'availability': 'configuration'}
    key = (sf.environment(), sf.settings.SUPERFRETE_TOKEN, sf.settings.SUPERFRETE_CONTACT_EMAIL)
    if _health.get('key') == key and _health.get('until', 0) > monotonic():
        return {**base, **_health['result']}
    try:
        result = sf.call('GET', 'me/orders?per_page=1&page=1&order=desc&sort_by=created_at')
        if not isinstance(result, dict) or not isinstance(result.get('data'), list):
            raise sf.ProviderError('unknown', 'Resposta de consulta inesperada.')
        result = {'availability': 'available'}
    except HTTPException as exc:
        category=getattr(exc,'category','unknown')
        result = {'availability': category if category in ('unavailable','configuration','unknown') else 'unknown'}
    _health.update(key=key, until=monotonic()+60, result=result)
    return {**base, **result}


def source_message(db, row):
    from uuid import UUID
    key = row.payload.get('_recovery_source')
    return db.get(AssistantMessage, UUID(key) if key else row.request_key)


def authorized(db, row):
    user = db.get(Usuario, row.user_id)
    if not user or not user.ativo or str(getattr(user.role, 'value', user.role)) not in ('ADMIN', 'GERENTE'):
        return False
    message = source_message(db, row)
    if message:
        from .assistant_channels import authorized_identity
        identity = authorized_identity(db, message.channel, message.sender_id)
        return bool(message.user_id == row.user_id and identity and identity.user_id == row.user_id and identity.can_register)
    return True  # Frontend request, already authorized by the endpoint.


def notify(db, row, state):
    from .assistant_channels import authorized_identity
    from .assistant_controls import InteractiveReply, button
    from .assistant_freight import quote_preview
    from ..config import settings
    message = source_message(db, row)
    if not message:
        message = db.query(AssistantMessage).filter_by(user_id=row.user_id, channel='telegram', should_reply=True).order_by(AssistantMessage.created_at.desc()).first()
    if not message or message.channel != 'telegram' or message.conversation_id.split(':')[0] != settings.TELEGRAM_GROUP_ID: return
    identity = authorized_identity(db, 'telegram', message.sender_id)
    if not identity or identity.user_id != row.user_id or not identity.can_register: return
    row.notify_channel='telegram';row.notify_destination=message.conversation_id
    if state in ('released','posted','delivered'):
        # The existing PDF worker delivers the document with its supported
        # freight-pdf event; recovery only supplies its authorized destination.
        return
    event = f'freight-recovery:{row.id}:{state}'
    if db.query(AssistantDelivery.id).filter_by(event_key=event).first(): return
    prefix = 'A solicitação SuperFrete pode continuar. Nenhum pagamento automático foi feito.\n'
    original = db.get(AssistantMessage, row.request_key)
    bot_quote = bool(original and original.channel == message.channel and original.conversation_id == message.conversation_id and original.user_id == row.user_id)
    if state == 'quoted':
        reply = quote_preview(row) if bot_quote else f"Cotação de {row.payload['to']['name']} recuperada. Abra o gestor de endereços para conferir os serviços e continuar."
    elif state == 'pending':
        text = f"Frete de {row.payload['to']['name']} preparado: R$ {row.price:.2f}. Confira no gestor antes de pagar."
        # Bot quotes can use the original conversation-bound service selection.
        rows = [[button('Conferir pagamento', f'q:{row.id.hex}:{row.service}')]] if bot_quote else []
        reply = InteractiveReply(text, rows)
    else:
        prefix = 'Não foi possível concluir automaticamente a solicitação SuperFrete.\n'
        reply = row.error or 'Confira o frete no gestor; não repita um pagamento incerto.'
    db.add(AssistantDelivery(event_key=event, channel='telegram', destination=message.conversation_id,
        user_id=row.user_id, text=prefix+str(reply), reply_markup=getattr(reply,'reply_markup',None),
        expires_at=utcnow()+timedelta(hours=24)))


def reconcile(db, row):
    if row.provider_id:
        # A known ID may already have reached checkout. Its pending provider
        # state is not evidence that an uncertain payment can be attempted again.
        info=sf.call('GET','order/info/'+quote(row.provider_id,safe=''))
        apply_info(db,row,info,allow_pending=False)
        return
    tag = row.payload.get('_provider_tag')
    if not tag:
        row.recovery_kind=None;row.recovery_check_at=None
        row.error='Solicitação antiga sem identificação para consulta automática. Confira o painel SuperFrete antes de solicitar outra etiqueta.'
        return
    # Inspect bounded recent candidates, then require an exact provider tag. Names
    # alone are not unique: the same customer may have several packages per day.
    matches = []
    for page in range(1, 6):
        result = sf.call('GET', f'me/orders?per_page=20&page={page}&order=desc&sort_by=created_at')
        if not isinstance(result,dict) or not isinstance(result.get('data'),list):
            raise sf.ProviderError('unknown','Resposta de consulta inesperada.')
        for item in result['data']:
            if not isinstance(item,dict) or item.get('to',{}).get('name') != row.payload['to']['name']: continue
            provider_id = item.get('order_id') or item.get('id')
            if not provider_id: continue
            info = sf.call('GET', 'order/info/'+quote(str(provider_id),safe=''))
            if not isinstance(info,dict) or str(info.get('id')) != str(provider_id): continue
            tags = info.get('tags') or info.get('options',{}).get('tags') or []
            if any(isinstance(t,dict) and t.get('tag') == tag for t in tags): matches.append(info)
        if page >= int(result.get('meta',{}).get('last_page',page)): break
    if len(matches) == 1:
        info = matches[0]
        apply_info(db,row,info,allow_pending=True)
    elif len(matches) > 1:
        row.error='Mais de um frete retornou a mesma identificação. Confira a SuperFrete; nenhum pagamento será repetido.'
        row.recovery_kind=None;row.recovery_check_at=None
    else:
        sf.schedule_recovery(row,'reconcile')


def apply_info(db,row,info,*,allow_pending):
    """Apply a confirmed provider identity/state atomically under the order lock."""
    if not isinstance(info,dict) or not info.get('id') or row.provider_id and str(info['id'])!=row.provider_id:
        raise sf.ProviderError('unknown','Identificador retornado não confere.')
    state=info.get('status')
    if state=='generated':state='released'
    if state not in ('pending','released','posted','delivered','cancelled'):
        raise sf.ProviderError('unknown','Estado retornado pela SuperFrete precisa de conferência.')
    price=sf.provider_price(info.get('price'))
    row.provider_id=str(info['id']);row.price=price
    if (state!='pending' or allow_pending or row.state=='pending') and (
            sf.may_advance_state(row.state,state) or (allow_pending and row.state in ('creating','uncertain'))):
        row.state=state;row.error=None;row.error_category=None
    row.tracking=info.get('tracking') or row.tracking
    row.recovery_kind=None;row.recovery_check_at=None
    sf.sync_tracking(db,row)
    if row.state in ('released','posted','delivered') and not row.label_pdf:
        if row.label_status=='none':row.label_status='waiting'
        row.label_check_at=utcnow()


def process_recovery():
    with SessionLocal() as db:
        row=db.query(FreightOrder).filter(FreightOrder.recovery_check_at<=utcnow(),
            FreightOrder.environment==sf.environment()).order_by(FreightOrder.recovery_check_at).with_for_update(skip_locked=True).first()
        if not row: return False
        key=row.id;kind=row.recovery_kind
        row.recovery_attempts+=1
        attempt=row.recovery_attempts
        row.recovery_check_at=utcnow()+timedelta(minutes=5)
        db.commit()  # Lease covers calls that commit independently.
    try:
        with SessionLocal() as db:
            row=sf.locked(db,key)
            if row.recovery_kind!=kind or row.recovery_attempts!=attempt:
                return True  # A newer result or worker replaced this lease.
            if not authorized(db,row):
                row.recovery_kind=None;row.recovery_check_at=None
                row.error='Recuperação suspensa: usuário ou identidade sem permissão.'
            elif kind == 'quote':
                sf.calculate(db,row)
            elif kind == 'cart':
                # Safe only because the previous POST was provably rejected.
                if row.provider_id or row.state!='retry_waiting':
                    row.recovery_kind=None;row.recovery_check_at=None
                else:
                    if utcnow()-sf.quote_time(row)>timedelta(minutes=30): sf.calculate(db,row)
                    if row.state in ('quoted','retry_waiting') and row.recovery_kind != 'quote':
                        row.state='quoted';db.commit();sf.cart(db,key,row.service)
            elif kind == 'reconcile':
                # A crash while creating is treated as unknown, never as rejected.
                if row.state=='creating':row.state='uncertain'
                reconcile(db,row)
            else:
                row.recovery_kind=None;row.recovery_check_at=None
            if row.recovery_kind and row.recovery_attempts>=144:
                row.recovery_kind=None;row.recovery_check_at=None
                row.error='Consulta automática encerrada após várias tentativas. Confira a solicitação na SuperFrete antes de emitir novamente.'
            if not row.recovery_kind:
                notify(db,row,row.state if row.state in ('quoted','pending','released','posted','delivered') else 'failed')
            row.updated_at=utcnow();db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            row=sf.locked(db,key)
            if row.recovery_attempts!=attempt:return True
            # A crashed cart can never inherit permission to POST again.
            if row.state=='creating': row.state='uncertain';kind='reconcile'
            if row.recovery_attempts>=144:
                row.recovery_kind=None;row.recovery_check_at=None
                row.error='A recuperação precisa de conferência no painel SuperFrete. Não repita o pagamento.'
                notify(db,row,'failed')
            else:
                sf.schedule_recovery(row,kind)
            row.updated_at=utcnow();db.commit()
        logger.warning('freight_recovery_waiting freight_id=%s category=%s',key,getattr(exc,'category','unknown'))
    return True
