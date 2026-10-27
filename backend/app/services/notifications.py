"""Transactional inbox/outbox. No provider call or commit belongs to this module."""
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from ..models.notification import (
    Notification, NotificationPreference, NotificationRecipient, NotificationRevision,
    NotificationRule, NotificationTemplate, utcnow,
)
from ..models.usuario import Usuario
from ..schemas.notification import CATEGORIES, NotificationFields, validate_action_path
from .access_policy import is_owner, own_sales
from .user_sessions import aware

BRT = ZoneInfo('America/Sao_Paulo')
DAILY_EVENTS = {'daily_greeting', 'morning_greeting', 'afternoon_greeting'}
DEFAULTS = {
    'sale_completed': ('Venda concluída', 'Venda #{sale_code} concluída',
                       '{user_name} concluiu uma venda. Abra o sistema para conferir.', 'sales', 'success', False, False, '09:00'),
    'sale_avulso_without_reason': ('Conferir itens avulsos', 'Venda #{sale_code}: informe o motivo',
                                 '{user_name}, esta venda contém itens avulsos sem vínculo com o estoque. Informe o motivo para conferência.', 'sales', 'warning', True, True, '09:00'),
    'sale_receipt_problem': ('Conferir impressão do ticket', 'Ticket da venda #{sale_code}: conferir impressão',
                             'Situação da impressão: {status}. Confira a fila antes de pedir outra cópia.', 'sales', 'warning', False, False, '09:00'),
    'tracking_status_changed': ('Atualização de rastreio', 'Rastreio {tracking_code} atualizado',
                                'Situação atual: {status}. Abra o rastreamento para conferir.', 'tracking', 'info', False, False, '09:00'),
    'daily_greeting': ('Lembrete diário', 'Seu lembrete da Eleven',
                        'Confira as suas notificações e pendências do dia.', 'reminder', 'info', False, False, '09:00'),
    'morning_greeting': ('Bom dia', 'Bom dia, equipe Eleven!',
                          'Bom trabalho! Confira as suas notificações e pendências de hoje.', 'greeting', 'info', False, False, '09:00'),
    'afternoon_greeting': ('Boa tarde', 'Boa tarde, equipe Eleven!',
                            'Confira as suas notificações e pendências antes de encerrar o dia.', 'greeting', 'info', False, False, '14:00'),
}


def _savepoint(db):
    # Python's SQLite legacy mode does not begin on SELECT; releasing its first
    # SAVEPOINT would commit notification rows outside the caller's rollback.
    # PostgreSQL already owns a real transaction and needs no special handling.
    connection = db.connection()
    if connection.dialect.name == 'sqlite' and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN')
    return db.begin_nested()


def ensure_defaults(db):
    """Forward-only defaults. Existing owner edits are never overwritten on startup."""
    existing = {key for (key,) in db.query(NotificationRule.event_key).all()}
    for key, values in DEFAULTS.items():
        if key in existing:
            continue
        name, title, body, category, severity, ack, response, local_time = values
        template_id = uuid.uuid5(uuid.NAMESPACE_URL, 'erp-eleven/notification-template/' + key)
        try:
            with _savepoint(db):
                if not db.get(NotificationTemplate, template_id):
                    db.add(NotificationTemplate(id=template_id, name=name, title=title, body=body,
                        category=category, severity=severity, requires_ack=ack, requires_response=response))
                    db.flush()
                db.add(NotificationRule(event_key=key, enabled=key != 'daily_greeting',
                    template_id=template_id, user_ids=[], local_time=local_time, weekdays=list(range(7))))
                db.flush()
        except IntegrityError:
            # Another process installed the same deterministic defaults concurrently.
            if not db.get(NotificationRule, key):
                raise


def active_users(db, user_ids, *, exact=False):
    ids = list(dict.fromkeys(uuid.UUID(str(value)) for value in user_ids))
    users = db.query(Usuario).filter(Usuario.id.in_(ids), Usuario.ativo.is_(True)).all() if ids else []
    if exact and len(users) != len(ids):
        raise HTTPException(400, 'Selecione somente usuários ativos e existentes.')
    return users


def action_allowed(db, user, path):
    """Do not send shortcuts to a module or someone else's sale outside the user's scope."""
    if not path:
        return True
    try:
        parts = urlsplit(validate_action_path(path))
    except ValueError:
        return False
    if parts.path in {'/auditoria', '/configuracoes', '/usuarios'} and not is_owner(user):
        return False
    if parts.path == '/assistente' and not is_owner(user):
        return False
    if parts.path in {'/enderecos', '/bi-vendas', '/inventory/labels'} and user.role.value not in {'ADMIN', 'GERENTE'}:
        return False
    if parts.path == '/fiado' and own_sales(user):
        return False
    query = parse_qs(parts.query)
    if parts.path == '/vendas-pdv' and query.get('sale_id'):
        from ..models.pdv import PdvSale
        try:
            sale_id = uuid.UUID(query['sale_id'][0])
        except (ValueError, TypeError):
            return False
        sale = db.get(PdvSale, sale_id)
        if not sale or (own_sales(user) and sale.vendedor_id != user.id):
            return False
    return True


def validate_targets(db, user_ids, action_path):
    users = active_users(db, user_ids, exact=True)
    if any(not action_allowed(db, user, action_path) for user in users):
        raise HTTPException(400, 'O atalho escolhido não está disponível para todos os destinatários.')
    return users


def notification_snapshot(db, notice):
    result = {field: getattr(notice, field) for field in (
        'title', 'body', 'category', 'severity', 'action_path', 'requires_ack', 'requires_response',
        'entity_type', 'entity_id')}
    result.update(scheduled_at=aware(notice.scheduled_at).isoformat() if notice.scheduled_at else None,
                  cancelled_at=aware(notice.cancelled_at).isoformat() if notice.cancelled_at else None,
                  user_ids=sorted(str(uid) for (uid,) in db.query(NotificationRecipient.user_id)
                                  .filter_by(notification_id=notice.id, removed_at=None).all()))
    return result


def record_revision(db, notice, actor_id=None):
    db.flush()
    db.add(NotificationRevision(notification_id=notice.id, version=notice.version,
                                snapshot=notification_snapshot(db, notice), changed_by=actor_id))
    db.flush()


def _queue_push(db, notice, recipients, moment):
    from ..models.notification_push import NotificationPushDelivery, NotificationPushSubscription
    by_user = {row.user_id: row for row in recipients}
    if not by_user:
        return
    preferences = {row.user_id: row for row in db.query(NotificationPreference)
                   .filter(NotificationPreference.user_id.in_(by_user)).all()}
    subscriptions = db.query(NotificationPushSubscription).join(Usuario, Usuario.id == NotificationPushSubscription.user_id).filter(
        NotificationPushSubscription.user_id.in_(by_user), NotificationPushSubscription.active.is_(True),
        Usuario.ativo.is_(True)).all()
    for subscription in subscriptions:
        pref = preferences.get(subscription.user_id)
        if pref and (not pref.push_enabled or notice.category not in pref.categories):
            continue
        db.add(NotificationPushDelivery(notification_id=notice.id, recipient_id=by_user[subscription.user_id].id,
            subscription_id=subscription.id, version=notice.version, status='queued', attempts=0, next_attempt_at=moment))


def emit_notification(db, *, title, body, user_ids, category='manual', severity='info',
                      action_path=None, requires_ack=False, requires_response=False, dedupe_key=None,
                      entity_type=None, entity_id=None, scheduled_at=None, created_by=None, request_id=None):
    fields = NotificationFields(title=title, body=body, category=category, severity=severity,
        action_path=action_path, requires_ack=requires_ack, requires_response=requires_response)
    if dedupe_key is not None and not 1 <= len(dedupe_key) <= 200:
        raise ValueError('Notification dedupe key must contain 1–200 characters.')
    filters = {'request_id': request_id} if request_id else {'dedupe_key': dedupe_key} if dedupe_key else None
    if filters:
        existing = db.query(Notification).filter_by(**filters).first()
        if existing:
            return existing
    users = active_users(db, user_ids)
    if not users:
        return None
    moment = utcnow()
    notice = Notification(id=uuid.uuid4(), **fields.model_dump(), created_by=created_by,
        request_id=request_id, dedupe_key=dedupe_key, entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None, scheduled_at=scheduled_at,
        created_at=moment, updated_at=moment, version=1)
    try:
        with _savepoint(db):
            db.add(notice)
            db.flush()
            recipients = [NotificationRecipient(id=uuid.uuid4(), notification_id=notice.id, user_id=user.id) for user in users]
            db.add_all(recipients)
            db.flush()
            record_revision(db, notice, created_by)
            if scheduled_at is None or aware(scheduled_at) <= moment:
                notice.published_at = moment
                _queue_push(db, notice, recipients, moment)
                db.flush()
    except IntegrityError:
        if filters:
            existing = db.query(Notification).filter_by(**filters).first()
            if existing:
                return existing
        raise
    return notice


def publish_due_notifications(db, now=None):
    moment = now or utcnow()
    notices = db.query(Notification).filter(Notification.published_at.is_(None), Notification.cancelled_at.is_(None),
        Notification.scheduled_at <= moment).order_by(Notification.scheduled_at, Notification.id).with_for_update(skip_locked=True).limit(100).all()
    for notice in notices:
        notice.published_at = moment
        recipients = db.query(NotificationRecipient).filter_by(notification_id=notice.id, removed_at=None).all()
        _queue_push(db, notice, recipients, moment)
    db.flush()
    return len(notices)


def emit_event(db, event_key, *, context, user_ids, dedupe_key, action_path=None, entity_type=None, entity_id=None):
    ensure_defaults(db)
    rule = db.get(NotificationRule, event_key)
    if not rule or not rule.enabled:
        return None
    template = db.get(NotificationTemplate, rule.template_id)
    moment = utcnow().astimezone(BRT)
    values = {'user_name': 'equipe', 'sale_code': '', 'tracking_code': '', 'status': '',
              'date': moment.strftime('%d/%m/%Y'), 'time': moment.strftime('%H:%M')}
    # No nested lookups, formatting operations or arbitrary object attributes.
    values.update({key: str(value)[:500] for key, value in context.items() if key in values and value is not None})
    if event_key in DAILY_EVENTS:
        recipients = rule.user_ids or user_ids
    else:
        allowed = {str(uid) for uid in user_ids}
        recipients = [uid for uid in rule.user_ids if str(uid) in allowed] if rule.user_ids else user_ids
    users = active_users(db, recipients)
    path = action_path or template.action_path
    # Retain the inbox message when access changed, while dropping a now-forbidden shortcut.
    if any(not action_allowed(db, user, path) for user in users):
        path = None
    defaults = DEFAULTS.get(event_key)
    default_title = defaults[1] if defaults else 'Notificação da Eleven'
    default_body = defaults[2] if defaults else 'Abra o sistema para conferir esta atualização.'
    # A reusable template can reference a value unavailable to this event (for
    # example {tracking_code} on a sale). Empty rendered text must not prevent
    # the surrounding business transaction from completing. Valid owner text
    # remains unchanged; database failures are deliberately not swallowed.
    title = template.title.format_map(values).strip() or default_title.format_map(values).strip()
    body = template.body.format_map(values).strip() or default_body.format_map(values).strip()
    return emit_notification(db, title=title[:120], body=body[:2000],
        category=template.category, severity=template.severity, requires_ack=template.requires_ack,
        requires_response=template.requires_response, user_ids=[user.id for user in users], action_path=path,
        dedupe_key=dedupe_key, entity_type=entity_type, entity_id=entity_id)


def run_notification_rules(db, now=None):
    ensure_defaults(db)
    moment = now or utcnow()
    local = moment.astimezone(BRT)
    day, clock = local.date().isoformat(), local.strftime('%H:%M')
    rules = db.query(NotificationRule).filter(NotificationRule.event_key.in_(DAILY_EVENTS), NotificationRule.enabled.is_(True))\
        .order_by(NotificationRule.event_key).with_for_update(skip_locked=True).all()
    emitted = 0
    for rule in rules:
        if rule.last_run_date == day or local.weekday() not in rule.weekdays or clock < rule.local_time:
            continue
        # Greetings expire after one hour: a late deploy must not greet the team at night.
        hour, minute = (int(part) for part in rule.local_time.split(':'))
        elapsed = local.hour * 60 + local.minute - (hour * 60 + minute)
        if rule.event_key in {'morning_greeting', 'afternoon_greeting'} and elapsed >= 60:
            continue
        # Generic reminders catch up once on the same day, never replay previous days.
        user_ids = rule.user_ids or [str(uid) for (uid,) in db.query(Usuario.id).filter(Usuario.ativo.is_(True)).all()]
        notice = emit_event(db, rule.event_key, context={'date': local.strftime('%d/%m/%Y'), 'time': clock},
                            user_ids=user_ids, dedupe_key=f'daily:{rule.event_key}:{day}')
        rule.last_run_date = day
        emitted += int(notice is not None)
    db.flush()
    return emitted


def preference_dict(preference):
    return {'push_enabled': preference.push_enabled if preference else True,
            'sound_enabled': preference.sound_enabled if preference else True,
            'categories': preference.categories if preference else list(CATEGORIES)}
