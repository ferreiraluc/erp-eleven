"""Signed inbox and bounded monitoring; no provider calls in the webhook request."""
import base64
import hashlib
import hmac
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models.access import now
from ..models.wonca import WoncaConfig, WoncaSubscription, WoncaEvent
from ..models.rastreamento import Rastreamento, RastreamentoStatus
from .tracking_codes import normalize_tracking_code, tracking_code_expression
from .wonca_service import _headers, _unwrap, normalize_events, extract_meta, infer_status
from .rastreamento_sync import RastreamentoSyncService

log = logging.getLogger(__name__)
BASE = 'https://api-labs.wonca.com.br/wonca.labs.v1.LabsService/'
CODE = re.compile(r'^[A-Z]{2}[0-9]{9}[A-Z]{2}$')


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def cipher():
    key = hashlib.sha256(('eleven:wonca:webhook:' + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def secret(config):
    try:
        return cipher().decrypt(config.secret_encrypted.encode()).decode() if config else ''
    except (InvalidToken, ValueError, AttributeError):
        return ''


def lock(db, key):
    return db.bind.dialect.name != 'postgresql' or bool(db.execute(
        text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': key}).scalar())


def owns(subscription, config):
    return bool(subscription and config and subscription.endpoint_id == config.endpoint_id and
                (subscription.remote_id or subscription.state == 'pending' and subscription.attempts > 0))


def call(method, payload):
    if method not in {'UpsertTrackingSubscriptions', 'DeleteTrackingSubscriptions'}:
        raise ValueError('Unsupported Wonca operation')
    try:
        response = requests.post(BASE + method, headers=_headers(), json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError('invalid_response')
        return result
    except (requests.RequestException, ValueError):
        # Never include provider bodies/headers/credentials or tracking details in logs.
        raise RuntimeError('provider_unavailable') from None


def receive(db, body, headers, moment=None):
    config = db.get(WoncaConfig, 'main')
    signing = secret(config)
    if not signing:
        raise HTTPException(503, 'Webhook Wonca ainda não configurado.')
    moment = moment or now()
    stamp = headers.get('x-wonca-webhook-timestamp', '')
    signature = headers.get('x-wonca-webhook-signature', '')
    if (not re.fullmatch(r'[0-9]{10,12}', stamp) or
            abs(moment.timestamp() - int(stamp)) > 300 or
            headers.get('x-wonca-webhook-algorithm') != 'hmac-sha256' or
            not re.fullmatch(r'[0-9a-fA-F]{64}', signature)):
        raise HTTPException(403, 'Assinatura ou timestamp inválido.')
    expected = hmac.new(signing.encode(), stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.lower(), expected):
        raise HTTPException(403, 'Assinatura inválida.')
    try:
        event = json.loads(body)
        event_id = str(UUID(event['event_id']))
        if str(UUID(headers.get('x-wonca-webhook-event-id', ''))) != event_id:
            raise ValueError('event_id')
        if headers.get('x-wonca-webhook-delivery-id'):
            UUID(headers['x-wonca-webhook-delivery-id'])
        code = normalize_tracking_code(event['code'])
        checked = datetime.fromisoformat(event['checked_at'].replace('Z', '+00:00'))
        if checked.tzinfo is None or checked > moment + timedelta(minutes=5):
            raise ValueError('checked_at')
        if not CODE.fullmatch(code) or not isinstance(event['payload'], dict):
            raise ValueError('payload')
        if event.get('type') != 'tracking.updated' or event.get('carrier') != 'CARRIER_CORREIOS':
            return {'accepted': True, 'ignored': True}
        inner = _unwrap(event['payload'])
        if not isinstance(inner, dict):
            raise ValueError('payload')
        if inner.get('codObjeto') and normalize_tracking_code(str(inner['codObjeto'])) != code:
            raise ValueError('code mismatch')
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise HTTPException(400, 'Evento Wonca inválido.') from None
    digest = hashlib.sha256(body).hexdigest()
    previous = db.get(WoncaEvent, event_id)
    if previous:
        if previous.body_hash != digest:
            raise HTTPException(409, 'Evento já recebido com outro conteúdo.')
        return {'accepted': True, 'duplicate': True}
    subscription = db.get(WoncaSubscription, code)
    owned = owns(subscription, config)
    status = 'pending' if owned and config.enabled else 'ignored'
    row = WoncaEvent(event_id=event_id, code=code, checked_at=checked,
        body_hash=digest, payload=event['payload'] if status == 'pending' else None,
        status=status, processed_at=moment if status == 'ignored' else None)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        previous = db.get(WoncaEvent, event_id, populate_existing=True)
        if not previous or previous.body_hash != digest:
            raise HTTPException(409, 'Evento conflitante.')
    return {'accepted': True}


def process_one(db):
    if not lock(db, 711013):
        return False
    event = db.query(WoncaEvent).filter_by(status='pending').order_by(
        WoncaEvent.checked_at, WoncaEvent.event_id).with_for_update(skip_locked=True).first()
    if not event:
        return False
    config = db.get(WoncaConfig, 'main')
    subscription = db.get(WoncaSubscription, event.code)
    row = db.query(Rastreamento).filter(tracking_code_expression(Rastreamento.codigo_rastreio) == event.code).first()
    # Lock parent before parcel, exactly as manual refresh/order flows do.
    if row and row.pedido_id:
        from ..models.pedido import Pedido
        db.query(Pedido.id).filter_by(id=row.pedido_id).with_for_update().first()
    if row:
        row = db.query(Rastreamento).filter_by(id=row.id).populate_existing().with_for_update().first()
    applicable = (config and config.enabled and owns(subscription, config) and row and row.ativo and
        utc(event.checked_at) <= utc(subscription.expires_at) and
        normalize_tracking_code(row.codigo_rastreio) == event.code)
    events = normalize_events(event.payload or {}) if applicable else []
    incoming_status = infer_status(events)
    if (not applicable or not events or
            row.provedor_verificado_em and utc(row.provedor_verificado_em) >= utc(event.checked_at) or
            row.status == RastreamentoStatus.ENTREGUE and incoming_status != RastreamentoStatus.ENTREGUE):
        event.status = 'ignored'
    else:
        row.historico_eventos = events
        inner = _unwrap(event.payload)
        row.rastreio_info = extract_meta({**inner, 'tipoPostal': inner.get('tipoPostal') if isinstance(inner.get('tipoPostal'), dict) else {}})
        row.status = incoming_status
        row.provedor_verificado_em = event.checked_at
        row.ultima_atualizacao = settings.now()
        db.flush()
        if row.pedido_id:
            RastreamentoSyncService.sincronizar_rastreamento_com_pedido(db, row)
        event.status = 'processed'
    event.payload = None  # The normalized history is enough; drop raw personal data.
    event.processed_at = now()
    db.flush()
    return True


def process_safely(db):
    """A malformed provider event must not block every following delivery."""
    if not lock(db, 711013):
        return False
    event = db.query(WoncaEvent).filter_by(status='pending').order_by(
        WoncaEvent.checked_at, WoncaEvent.event_id).with_for_update(skip_locked=True).first()
    if not event:
        return False
    try:
        with db.begin_nested():
            process_one(db)
    except Exception as exc:
        event.attempts += 1
        event.last_error = type(exc).__name__[:40]
        if event.attempts >= 5:
            event.status = 'failed'
            event.processed_at = now()
            event.payload = None
        db.flush()
    return True


def sync_subscriptions(db, provider=call, moment=None, *, guarded=False, plan_only=False, enroll_new=True):
    """One serialized bounded batch; calls only for new/changed owned subscriptions."""
    if not guarded and not lock(db, 711014):
        return {'added': 0, 'removed': 0}
    config = db.get(WoncaConfig, 'main')
    if not config or not secret(config) or not settings.WONCA_API_KEY:
        return {'added': 0, 'removed': 0}
    moment = moment or now()
    awake = not config.daytime_only or 7 <= moment.astimezone(settings.tz).hour < 21
    current = {normalize_tracking_code(row.codigo_rastreio) for row in db.query(Rastreamento).filter(
        Rastreamento.ativo.is_(True), Rastreamento.status != RastreamentoStatus.ENTREGUE)} if config.enabled else set()
    desired = {code for code in current if CODE.fullmatch(code)} if awake else set()
    subscriptions = db.query(WoncaSubscription).order_by(WoncaSubscription.code).all()
    by_code = {row.code: row for row in subscriptions}
    # Existing registrations keep their first window; never renew expired objects silently.
    for code in (sorted(desired - by_code.keys())[:100] if enroll_new else []):
        row = WoncaSubscription(code=code, endpoint_id=config.endpoint_id, profile_id=config.profile_id,
            created_at=moment, expires_at=moment + timedelta(days=config.monitor_days), retry_at=moment, attempts=1)
        db.add(row); subscriptions.append(row)
    db.flush()
    for row in subscriptions:
        if not row.remote_id and not row.attempts and utc(row.expires_at) <= moment:
            row.state = 'expired'
        if (plan_only and row.code in desired and row.state in ('stopped', 'paused') and
                utc(row.expires_at) > moment and utc(row.retry_at) <= moment):
            # Its previous remote registration was already cancelled. Persist an
            # uncertain intent before a new ID can be created by the provider.
            row.remote_id = None
            row.state = 'pending'
            row.attempts = max(1, row.attempts)
    if plan_only:
        db.flush()
        return {'added': 0, 'removed': 0}
    due = [row for row in subscriptions if utc(row.retry_at) <= moment]
    removing = [row for row in due if row.remote_id and row.state in ('active', 'pending', 'removing') and
        (row.code not in desired or utc(row.expires_at) <= moment or row.state == 'removing')][:100]
    adding = [row for row in due if ((row.code in desired and utc(row.expires_at) > moment) or row.attempts > 0 and not row.remote_id) and
        row.state in ('pending', 'stopped', 'paused') and row.endpoint_id == config.endpoint_id and row.profile_id == config.profile_id][:100]
    added = removed = 0
    for rows, method in ((removing, 'DeleteTrackingSubscriptions'), (adding, 'UpsertTrackingSubscriptions')):
        if not rows:
            continue
        try:
            data = ({'ids': [row.remote_id for row in rows]} if method.startswith('Delete') else {
                'endpointId': config.endpoint_id, 'profileId': config.profile_id,
                'entries': [{'code': row.code, 'carrier': 'CARRIER_CORREIOS'} for row in rows]})
            result = provider(method, data)
            if method.startswith('Delete'):
                for row in rows:
                    row.state = ('expired' if utc(row.expires_at) <= moment else
                                 'paused' if config.enabled and not awake and row.code in current else 'stopped')
                    row.last_error = None; row.attempts = 0
                removed = len(rows)
            else:
                received = result.get('subscriptions', [])
                matches = {normalize_tracking_code(str(item.get('code', ''))): item for item in received if isinstance(item, dict)}
                for row in rows:
                    item = matches.get(row.code, {})
                    if (item.get('endpointId') != config.endpoint_id or item.get('profileId') != config.profile_id or
                            item.get('carrier', 'CARRIER_CORREIOS') != 'CARRIER_CORREIOS' or not item.get('active')):
                        raise RuntimeError('invalid_response')
                    row.remote_id = str(UUID(item['id'])); row.state = 'active'
                    row.last_error = None; row.attempts = 0
                added = len(rows)
                abandoned = [row for row in rows if row.code not in desired or utc(row.expires_at) <= moment]
                if abandoned:
                    # A timeout may have accepted an upsert before the operator
                    # paused/archived it. Recover its ID and cancel immediately.
                    for row in abandoned:
                        row.state = 'removing'
                    provider('DeleteTrackingSubscriptions', {'ids': [row.remote_id for row in abandoned]})
                    for row in abandoned:
                        row.state = ('expired' if utc(row.expires_at) <= moment else
                                     'paused' if config.enabled and not awake and row.code in current else 'stopped')
                    removed += len(abandoned)
        except (RuntimeError, ValueError, KeyError, TypeError):
            for row in rows:
                row.attempts += 1
                row.retry_at = moment + timedelta(seconds=min(3600, 60 * 2 ** min(row.attempts, 6)))
                row.last_error = 'provider_unavailable'
                if method.startswith('Delete'):
                    row.state = 'removing'
    db.flush()
    return {'added': added, 'removed': removed}


def reconcile(session_factory, provider=call, moment=None):
    # Separate guard owns the lock across the durable intent and remote phases.
    # A deployment may stop after the provider accepted an upsert; the next
    # worker can then recover its ID even if the parcel was archived meanwhile.
    with session_factory() as guard:
        if not lock(guard, 711014):
            return {'added': 0, 'removed': 0}
        with session_factory() as db:
            sync_subscriptions(db, provider, moment, guarded=True, plan_only=True)
            db.commit()
        with session_factory() as db:
            result = sync_subscriptions(db, provider, moment, guarded=True, enroll_new=False)
            db.commit()
            return result


def main(stop):
    from ..database import SessionLocal
    from .worker_health import beat
    sync_at = 0
    while not stop.is_set():
        beat('wonca')
        try:
            for _ in range(20):
                with SessionLocal() as db:
                    if not process_safely(db):
                        break
                    db.commit()
                beat('wonca')
            if time.monotonic() >= sync_at:
                reconcile(SessionLocal)
                with SessionLocal() as db:
                    # Keep idempotency receipts, purge only completed raw-free inbox rows after 90d.
                    db.query(WoncaEvent).filter(WoncaEvent.processed_at < now() - timedelta(days=90)).delete(synchronize_session=False)
                    db.commit()
                sync_at = time.monotonic() + 60
        except Exception as exc:
            log.warning('[WONCA] worker retry type=%s', type(exc).__name__)
        stop.wait(2)
