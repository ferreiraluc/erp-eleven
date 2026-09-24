"""Durable label polling; provider callbacks only wake it, never authorize purchases."""
import logging
import uuid
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import or_
from ..database import SessionLocal
from ..models.address_book import FreightOrder
from ..models.assistant import AssistantDelivery, AssistantMessage, utcnow
from ..models.printing import PrintDevice, PrintJob
from ..models.usuario import Usuario
from . import superfrete as sf

logger = logging.getLogger('freight_labels')
PAID = ('released','posted','delivered')


def watch_label(db, row, *, auto_print=False, device_id=None, message=None):
    """Persist the user's print choice in the same durable transaction as checkout."""
    if row.label_status in ('none', 'failed'):
        row.label_status = 'waiting'
        row.label_attempts = 0
    if not row.print_job_id:
        row.auto_print = auto_print
        if device_id:row.print_device_id = device_id
        if auto_print and not row.print_device_id:
            devices = db.query(PrintDevice).filter_by(active=True).limit(2).all()
            if len(devices) == 1:row.print_device_id = devices[0].id
    # Frontend purchases by a connected employee use their existing company conversation.
    if message is None and not row.notify_destination:
        message = db.query(AssistantMessage).filter_by(user_id=row.user_id, channel='telegram', should_reply=True).order_by(AssistantMessage.created_at.desc()).first()
    if message and message.user_id == row.user_id and message.channel == 'telegram':
        row.notify_channel, row.notify_destination = message.channel, message.conversation_id
    if row.label_status != 'ready' or row.auto_print and not row.print_job_id:
        row.label_check_at = utcnow() + timedelta(seconds=15)
    db.flush()


def notify_pdf(db, row, printed):
    from ..config import settings
    from .assistant_channels import authorized_identity
    from ..models.assistant import AssistantIdentity
    if not row.notify_destination or row.notify_channel != 'telegram':return
    if row.notify_destination.split(':')[0] != settings.TELEGRAM_GROUP_ID:return
    identities = db.query(AssistantIdentity).filter_by(user_id=row.user_id, channel='telegram', active=True).all()
    if not any(authorized_identity(db,'telegram',i.external_id) for i in identities):return
    event_key = 'freight-pdf:' + str(row.id)
    old = db.query(AssistantDelivery).filter_by(event_key=event_key).first()
    name = row.payload.get('to', {}).get('name', 'destinatário')
    if old:
        # A PDF already sent while the printer was unavailable needs one later status update.
        if printed and 'fila de impressão' not in old.text:
            key = 'freight-printed:' + str(row.id)
            if not db.query(AssistantDelivery.id).filter_by(event_key=key).first():
                db.add(AssistantDelivery(event_key=key, channel='telegram', destination=row.notify_destination,
                    text=f'Etiqueta de {name} enviada à fila de impressão da loja: uma cópia A4.', user_id=row.user_id))
        return
    text = f'Etiqueta de {name} disponível. O PDF também está no gestor de endereços do ERP.'
    if printed:text += '\nEnviada à fila de impressão da loja: uma cópia A4. Mantenha o Eleven Impressao aberto no Windows.'
    elif row.auto_print:text += '\nA impressão aguarda a impressora configurada no ERP. O gestor mostra o motivo.'
    db.add(AssistantDelivery(event_key=event_key, channel='telegram', destination=row.notify_destination,
        text=text, user_id=row.user_id, document_pdf=row.label_pdf))


def process_label():
    # A committed five-minute lease survives provider calls/commits and overlapping deploys.
    with SessionLocal() as db:
        row = db.query(FreightOrder).filter(FreightOrder.label_check_at <= utcnow(),
            FreightOrder.label_status.in_(('waiting','ready'))).order_by(FreightOrder.label_check_at).with_for_update(skip_locked=True).first()
        if not row:return False
        key = row.id
        row.label_check_at = utcnow() + timedelta(minutes=5)
        row.label_attempts += 1
        db.commit()
    try:
        with SessionLocal() as db:
            row = db.get(FreightOrder, key)
            if not row.label_pdf:
                row = sf.refresh(db, key)
                if row.state == 'cancelled':
                    row.label_status='cancelled';row.label_check_at=None;db.commit();return True
                if row.state not in PAID or not row.label_url:
                    raise HTTPException(409, 'Aguardando a SuperFrete liberar o PDF. Não é necessário pagar novamente.')
                pdf = sf.label_pdf(row.label_url)
                row = sf.locked(db, key)
                row.label_pdf = pdf
                row.label_status = 'ready'
                row.label_error = None
                db.commit()  # make the verified PDF available even if printing is temporarily blocked
            row = sf.locked(db, key)
            user = db.get(Usuario, row.user_id)
            allowed = user and user.ativo and str(getattr(user.role,'value',user.role)) in ('ADMIN','GERENTE')
            if row.auto_print and not row.print_job_id:
                if not allowed:
                    row.label_error='Impressão automática suspensa: gestor inativo ou sem permissão.'
                    row.auto_print=False
                else:
                    devices = db.query(PrintDevice).filter_by(active=True)
                    if row.print_device_id:devices=devices.filter_by(id=row.print_device_id)
                    options = devices.limit(2).all()
                    if len(options) == 1:
                        device = options[0]
                        request_key=uuid.uuid5(uuid.NAMESPACE_URL, 'eleven:freight:auto-print:'+str(row.id))
                        job=sf.print_label(db,row.id,device.id,request_key,row.user_id)
                        row.print_job_id=job.id
                        row.label_error=None
                    else:
                        row.label_error='Selecione uma impressora ativa para concluir a impressão automática.'
            notify_pdf(db,row,bool(row.print_job_id))
            row.label_check_at = utcnow()+timedelta(minutes=2) if row.auto_print and not row.print_job_id else None
            if row.label_attempts >= 400 and row.label_check_at:
                row.label_check_at=None
                row.label_error='PDF disponível. Impressora indisponível; envie à fila pelo gestor quando configurada.'
            db.commit()
        return True
    except Exception as exc:
        with SessionLocal() as db:
            row = db.query(FreightOrder).filter_by(id=key).with_for_update().first()
            if row:
                row.label_error = str(exc.detail)[:200] if isinstance(exc, HTTPException) else 'Falha temporária ao buscar o PDF; nova tentativa automática.'
                if row.label_attempts >= 400:
                    row.label_status='failed';row.label_check_at=None
                    if row.notify_destination and row.notify_channel=='telegram':
                        event='freight-pdf-timeout:'+str(row.id)
                        if not db.query(AssistantDelivery.id).filter_by(event_key=event).first():
                            db.add(AssistantDelivery(event_key=event,channel='telegram',destination=row.notify_destination,
                                user_id=row.user_id,text='A SuperFrete ainda não liberou uma etiqueta pendente. Confira o gestor de endereços; não pague novamente.'))
                else:
                    row.label_check_at=utcnow()+timedelta(seconds=min(300,15*2**min(row.label_attempts,5)))
                db.commit()
        logger.warning('label_waiting freight_id=%s', key)
        return True


def main(stop_event):
    while not stop_event.is_set():
        try:
            if not process_label():stop_event.wait(3)
        except Exception:
            logger.warning('label_worker_iteration_failed')
            stop_event.wait(10)
