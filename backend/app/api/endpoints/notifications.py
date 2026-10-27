"""Per-user notification inbox and Lucas-only authoring/audit controls."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_active_user, require_owner
from ...models.notification import (
    Notification, NotificationPreference, NotificationRecipient, NotificationRevision,
    NotificationRule, NotificationTemplate, utcnow,
)
from ...models.notification_push import NotificationPushDelivery
from ...models.usuario import Usuario
from ...schemas.notification import (
    Acknowledge, ExpectedVersion, NotificationCreate, NotificationUpdate, PreferenceUpdate,
    RuleUpdate, TemplateCreate, TemplateUpdate,
)
from ...services import notifications as service
from ...services.user_sessions import aware
from ...services.user_audit import record

router = APIRouter()


def _fields(notice):
    return {key: getattr(notice, key) for key in (
        'id', 'title', 'body', 'category', 'severity', 'action_path', 'requires_ack', 'requires_response',
        'scheduled_at', 'published_at', 'cancelled_at', 'created_at', 'updated_at', 'version')}


def _inbox_query(db, user):
    return db.query(Notification, NotificationRecipient).join(
        NotificationRecipient, NotificationRecipient.notification_id == Notification.id).filter(
        NotificationRecipient.user_id == user.id, NotificationRecipient.removed_at.is_(None),
        Notification.published_at.is_not(None), Notification.published_at <= utcnow(), Notification.cancelled_at.is_(None))


def _receipt(db, user, notification_id, *, lock=False):
    query = _inbox_query(db, user).filter(Notification.id == notification_id)
    row = query.with_for_update().first() if lock else query.first()
    if not row:
        raise HTTPException(404, 'Notificação não encontrada.')
    return row


def _owner_message(db, notification_id, expected_version=None):
    notice = db.query(Notification).filter_by(id=notification_id).populate_existing().with_for_update().first()
    if not notice:
        raise HTTPException(404, 'Notificação não encontrada.')
    if expected_version is not None and notice.version != expected_version:
        raise HTTPException(409, 'Esta notificação foi atualizada. Recarregue antes de alterar.')
    return notice


def _template(row):
    return {key: getattr(row, key) for key in ('id', 'name', 'title', 'body', 'category', 'severity',
        'action_path', 'requires_ack', 'requires_response', 'version', 'created_at', 'updated_at')}


def _rule(row):
    return {key: getattr(row, key) for key in ('event_key', 'enabled', 'template_id', 'user_ids',
        'local_time', 'weekdays', 'last_run_date', 'version', 'updated_at')}


def _admin_messages(db, rows):
    ids = [row.id for row in rows]
    recipients = db.query(NotificationRecipient, Usuario.nome).join(Usuario, Usuario.id == NotificationRecipient.user_id)\
        .filter(NotificationRecipient.notification_id.in_(ids)).order_by(Usuario.nome).all() if ids else []
    deliveries = db.query(NotificationPushDelivery).filter(NotificationPushDelivery.notification_id.in_(ids)).all() if ids else []
    grouped = {}
    for delivery in deliveries:
        grouped.setdefault(delivery.recipient_id, []).append(delivery)
    receipts = {}
    for receipt, name in recipients:
        pushes = grouped.get(receipt.id, [])
        states = [row.status for row in pushes]
        status = ('delivered' if 'delivered' in states else 'queued' if any(s in ('queued', 'retry', 'sending') for s in states)
                  else 'failed' if 'dead' in states else 'not_subscribed')
        receipts.setdefault(receipt.notification_id, []).append({
            'user_id': receipt.user_id, 'user_name': name, 'read_at': receipt.read_at,
            'acknowledged_at': receipt.acknowledged_at, 'acknowledgement_note': receipt.acknowledgement_note,
            'read_version': receipt.read_version, 'acknowledged_version': receipt.acknowledged_version,
            'removed_at': receipt.removed_at, 'push_status': status,
        })
    return [{**_fields(row), 'user_ids': [str(receipt['user_id']) for receipt in receipts.get(row.id, []) if not receipt['removed_at']],
             'receipts': receipts.get(row.id, [])} for row in rows]


@router.get('/inbox')
def inbox(offset: int = Query(0, ge=0, le=1000000), limit: int = Query(30, ge=1, le=100),
          unread_only: bool = False, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    query = _inbox_query(db, user)
    unread = query.filter(NotificationRecipient.read_at.is_(None)).count()
    if unread_only:
        query = query.filter(NotificationRecipient.read_at.is_(None))
    total = query.count()
    rows = query.order_by(Notification.published_at.desc(), Notification.id.desc()).offset(offset).limit(limit).all()
    items = []
    for notice, receipt in rows:
        item = {**_fields(notice), 'read_at': receipt.read_at, 'acknowledged_at': receipt.acknowledged_at,
                'acknowledgement_note': receipt.acknowledgement_note, 'read_version': receipt.read_version,
                'acknowledged_version': receipt.acknowledged_version}
        if not service.action_allowed(db, user, notice.action_path):
            item['action_path'] = None
        items.append(item)
    return {'items': items, 'total': total, 'unread_count': unread}


@router.get('/preferences')
def preferences(user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    return service.preference_dict(db.get(NotificationPreference, user.id))


@router.put('/preferences')
def update_preferences(body: PreferenceUpdate, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Serialize first-write races using the existing user row rather than relying on an in-memory setting.
    db.query(Usuario).filter_by(id=user.id).with_for_update().first()
    preference = db.get(NotificationPreference, user.id)
    if not preference:
        preference = NotificationPreference(user_id=user.id)
        db.add(preference)
    for field, value in body.model_dump().items():
        setattr(preference, field, sorted(set(value)) if field == 'categories' else value)
    preference.updated_at = utcnow()
    db.commit()
    return service.preference_dict(preference)


@router.post('/read-all')
def read_all(user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    moment = utcnow()
    rows = _inbox_query(db, user).filter(NotificationRecipient.read_at.is_(None)).with_for_update().all()
    for notice, receipt in rows:
        receipt.read_at, receipt.read_version = moment, notice.version
    db.commit()
    return {'ok': True}


@router.post('/{notification_id}/read')
def mark_read(notification_id: uuid.UUID, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    notice, receipt = _receipt(db, user, notification_id, lock=True)
    if receipt.read_at is None:
        receipt.read_at = utcnow()
    receipt.read_version = notice.version
    db.commit()
    return {'ok': True}


@router.post('/{notification_id}/acknowledge')
def acknowledge(notification_id: uuid.UUID, body: Acknowledge, user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    notice, receipt = _receipt(db, user, notification_id, lock=True)
    if body.expected_version is not None and body.expected_version != notice.version:
        raise HTTPException(409, 'A mensagem mudou. Recarregue antes de confirmar.')
    if notice.requires_response and not body.note:
        raise HTTPException(400, 'Informe o motivo ou a resposta solicitada para confirmar.')
    if receipt.acknowledged_at is not None:
        # Retrying a response cannot overwrite the original answer or silently change a prior acknowledgement.
        if body.note and body.note != receipt.acknowledgement_note:
            raise HTTPException(409, 'Esta notificação já possui uma resposta confirmada.')
        return {'ok': True}
    moment = utcnow()
    receipt.read_at = receipt.read_at or moment
    receipt.read_version = notice.version
    receipt.acknowledged_at, receipt.acknowledged_version = moment, notice.version
    receipt.acknowledgement_note = body.note or None
    db.commit()
    return {'ok': True}


@router.get('/admin')
def admin(offset: int = Query(0, ge=0, le=1000000), limit: int = Query(30, ge=1, le=100),
          owner=Depends(require_owner), db: Session = Depends(get_db)):
    service.ensure_defaults(db)
    db.commit()
    query = db.query(Notification)
    rows = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(limit).all()
    return {'items': _admin_messages(db, rows), 'total': query.count(),
        'users': [{'id': user.id, 'nome': user.nome} for user in db.query(Usuario).filter(Usuario.ativo.is_(True)).order_by(Usuario.nome).all()],
        'templates': [_template(row) for row in db.query(NotificationTemplate).order_by(NotificationTemplate.name).all()],
        'rules': [_rule(row) for row in db.query(NotificationRule).order_by(NotificationRule.event_key).all()]}


@router.post('/admin', status_code=201)
def create(body: NotificationCreate, owner=Depends(require_owner), db: Session = Depends(get_db)):
    service.validate_targets(db, body.user_ids, body.action_path)
    notice = service.emit_notification(db, **body.model_dump(), created_by=owner.id)
    # Validate the immutable first revision after INSERT as well as on a retry:
    # two concurrent requests may race with the same request ID and different text.
    original = db.query(NotificationRevision).filter_by(notification_id=notice.id, version=1).one().snapshot
    submitted = body.model_dump(exclude={'request_id', 'user_ids', 'scheduled_at'})
    submitted.update(user_ids=sorted(set(str(uid) for uid in body.user_ids)),
                     scheduled_at=aware(body.scheduled_at).isoformat() if body.scheduled_at else None)
    if any(original.get(key) != value for key, value in submitted.items()):
        raise HTTPException(409, 'Esta solicitação já foi usada para outra notificação.')
    record(db, 'notification_created', 'notifications', entity='notifications', entity_id=str(notice.id))
    db.commit()
    return _admin_messages(db, [notice])[0]


@router.patch('/admin/{notification_id}')
def edit(notification_id: uuid.UUID, body: NotificationUpdate, owner=Depends(require_owner), db: Session = Depends(get_db)):
    notice = _owner_message(db, notification_id, body.expected_version)
    if notice.cancelled_at:
        raise HTTPException(409, 'Uma notificação cancelada permanece no histórico. Crie outra mensagem.')
    users = service.validate_targets(db, body.user_ids, body.action_path)
    if notice.published_at and body.scheduled_at and aware(body.scheduled_at) > utcnow():
        raise HTTPException(400, 'Uma mensagem publicada não pode voltar ao agendamento. Crie outra notificação.')
    for field, value in body.model_dump(exclude={'expected_version', 'user_ids'}).items():
        setattr(notice, field, value)
    wanted = {user.id for user in users}
    current = db.query(NotificationRecipient).filter_by(notification_id=notice.id).with_for_update().all()
    by_user = {row.user_id: row for row in current}
    moment = utcnow()
    added = []
    removed = []
    for receipt in current:
        if receipt.user_id not in wanted and receipt.removed_at is None:
            receipt.removed_at = moment
            removed.append(receipt.id)
        elif receipt.user_id in wanted:
            receipt.removed_at = None
    for user in users:
        if user.id not in by_user:
            receipt = NotificationRecipient(id=uuid.uuid4(), notification_id=notice.id, user_id=user.id)
            db.add(receipt)
            added.append(receipt)
    if removed:
        db.query(NotificationPushDelivery).filter(NotificationPushDelivery.recipient_id.in_(removed),
            NotificationPushDelivery.status.in_(['queued', 'retry', 'sending'])).update(
                {'status': 'dead', 'last_error': 'recipient_removed', 'lease_token': None, 'lease_until': None}, synchronize_session=False)
    notice.version += 1
    notice.updated_at = moment
    db.flush()
    if notice.published_at:
        service._queue_push(db, notice, added, moment)
    elif notice.scheduled_at is None or aware(notice.scheduled_at) <= moment:
        notice.published_at = moment
        service._queue_push(db, notice, [row for row in current + added if row.removed_at is None], moment)
    service.record_revision(db, notice, owner.id)
    record(db, 'notification_updated', 'notifications', entity='notifications', entity_id=str(notice.id))
    db.commit()
    return _admin_messages(db, [notice])[0]


@router.post('/admin/{notification_id}/cancel')
def cancel(notification_id: uuid.UUID, body: ExpectedVersion, owner=Depends(require_owner), db: Session = Depends(get_db)):
    notice = _owner_message(db, notification_id, body.expected_version)
    if not notice.cancelled_at:
        notice.cancelled_at, notice.updated_at = utcnow(), utcnow()
        notice.version += 1
        db.query(NotificationPushDelivery).filter_by(notification_id=notice.id).filter(
            NotificationPushDelivery.status.in_(['queued', 'retry', 'sending'])).update(
                {'status': 'dead', 'last_error': 'notification_cancelled', 'lease_token': None, 'lease_until': None}, synchronize_session=False)
        service.record_revision(db, notice, owner.id)
        record(db, 'notification_cancelled', 'notifications', entity='notifications', entity_id=str(notice.id))
        db.commit()
    return _admin_messages(db, [notice])[0]


@router.get('/admin/{notification_id}/history')
def history(notification_id: uuid.UUID, owner=Depends(require_owner), db: Session = Depends(get_db)):
    _owner_message(db, notification_id)
    return {'items': [{'version': row.version, 'snapshot': row.snapshot, 'changed_at': row.changed_at, 'changed_by': row.changed_by}
        for row in db.query(NotificationRevision).filter_by(notification_id=notification_id).order_by(NotificationRevision.version).all()]}


@router.post('/templates', status_code=201)
def create_template(body: TemplateCreate, owner=Depends(require_owner), db: Session = Depends(get_db)):
    if db.query(NotificationTemplate).count() >= 200:
        raise HTTPException(400, 'Há 200 modelos cadastrados. Edite um modelo existente.')
    template = NotificationTemplate(**body.model_dump(), created_by=owner.id)
    db.add(template)
    db.flush()
    record(db, 'notification_template_created', 'notifications', entity='notification_templates', entity_id=str(template.id))
    db.commit()
    return _template(template)


@router.patch('/templates/{template_id}')
def edit_template(template_id: uuid.UUID, body: TemplateUpdate, owner=Depends(require_owner), db: Session = Depends(get_db)):
    template = db.query(NotificationTemplate).filter_by(id=template_id).populate_existing().with_for_update().first()
    if not template:
        raise HTTPException(404, 'Modelo não encontrado.')
    if template.version != body.expected_version:
        raise HTTPException(409, 'Este modelo mudou. Recarregue antes de alterar.')
    for field, value in body.model_dump(exclude={'expected_version'}).items():
        setattr(template, field, value)
    template.version += 1
    template.updated_at = utcnow()
    record(db, 'notification_template_updated', 'notifications', entity='notification_templates', entity_id=str(template.id))
    db.commit()
    return _template(template)


@router.put('/rules/{event_key}')
def edit_rule(event_key: str, body: RuleUpdate, owner=Depends(require_owner), db: Session = Depends(get_db)):
    service.ensure_defaults(db)
    rule = db.query(NotificationRule).filter_by(event_key=event_key).populate_existing().with_for_update().first()
    if not rule:
        raise HTTPException(404, 'Regra não encontrada.')
    if rule.version != body.expected_version:
        raise HTTPException(409, 'Esta regra mudou. Recarregue antes de alterar.')
    template = db.get(NotificationTemplate, body.template_id)
    if not template:
        raise HTTPException(400, 'Escolha um modelo existente.')
    if body.user_ids:
        service.validate_targets(db, body.user_ids, template.action_path)
    elif event_key in service.DAILY_EVENTS:
        all_ids = [uid for (uid,) in db.query(Usuario.id).filter(Usuario.ativo.is_(True)).all()]
        service.validate_targets(db, all_ids, template.action_path)
    for field, value in body.model_dump(exclude={'expected_version'}).items():
        setattr(rule, field, [str(uid) for uid in value] if field == 'user_ids' else value)
    rule.version += 1
    rule.updated_at = utcnow()
    record(db, 'notification_rule_updated', 'notifications', entity='notification_rules', entity_id=rule.event_key)
    db.commit()
    return _rule(rule)
