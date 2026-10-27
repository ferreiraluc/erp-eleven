"""Disposable notification fixtures: no production, provider calls, printing or payments."""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.access import AuthSession, AuditEvent
from app.models.notification import (
    Notification, NotificationPreference, NotificationRecipient, NotificationRevision,
    NotificationRule, NotificationTemplate, utcnow,
)
from app.models.notification_push import NotificationPushDelivery, NotificationPushSetting, NotificationPushSubscription
from app.api.endpoints import notifications as api
from app.services import notifications as service

MODELS = (Usuario, Vendedor, AuthSession, AuditEvent, Notification, NotificationRecipient,
          NotificationRevision, NotificationPreference, NotificationTemplate, NotificationRule,
          NotificationPushSetting, NotificationPushSubscription, NotificationPushDelivery)


@pytest.fixture
def setup():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in MODELS])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    ids = {}
    with factory() as db:
        for name in ['Lucas', 'Sol', 'Junior', 'Inactive']:
            user = Usuario(id=uuid.uuid4(), nome=name, email=name.lower() + '@eleven.com', senha_hash='unused',
                role=UsuarioRole.ADMIN if name == 'Lucas' else UsuarioRole.GERENTE,
                sales_scope='all' if name == 'Lucas' else 'own', ativo=name != 'Inactive')
            db.add(user)
            ids[name] = user.id
        db.commit()
    app = FastAPI()
    app.include_router(api.router, prefix='/api/notifications')
    def get_session():
        with factory() as db:
            yield db
    def current(request: Request):
        with factory() as db:
            user = db.get(Usuario, ids.get(request.headers.get('X-User', 'Sol')))
            if not user or not user.ativo:
                raise HTTPException(401)
            return user
    app.dependency_overrides[get_db] = get_session
    app.dependency_overrides[get_current_active_user] = current
    with TestClient(app) as client:
        yield client, factory, ids
    engine.dispose()


def owner():
    return {'X-User': 'Lucas'}


def payload(ids, **updates):
    return {'request_id': str(uuid.uuid4()), 'title': 'Conferir venda', 'body': 'Informe o motivo do item avulso.',
        'category': 'sales', 'severity': 'warning', 'requires_ack': True, 'requires_response': True,
        'user_ids': [str(ids['Sol'])], **updates}


def create(setup, **updates):
    client, _, ids = setup
    response = client.post('/api/notifications/admin', headers=owner(), json=payload(ids, **updates))
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_authoring_and_recipient_isolation(setup):
    client, factory, ids = setup
    assert client.get('/api/notifications/admin').status_code == 403
    assert client.post('/api/notifications/admin', json=payload(ids)).status_code == 403
    notice = create(setup)
    inbox = client.get('/api/notifications/inbox').json()
    assert inbox['total'] == inbox['unread_count'] == 1
    assert inbox['items'][0]['id'] == notice['id']
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['items'] == []
    assert client.post(f"/api/notifications/{notice['id']}/read", headers={'X-User': 'Junior'}).status_code == 404
    assert client.post(f"/api/notifications/{notice['id']}/acknowledge", headers={'X-User': 'Junior'}, json={'note': 'x'}).status_code == 404
    assert client.get(f"/api/notifications/admin/{notice['id']}/history").status_code == 403
    with factory() as db:
        event = db.query(AuditEvent).one()
        assert event.action == 'notification_created' and event.changes == {}
        assert 'motivo' not in str(event.changes)


def test_create_retries_are_idempotent_and_reject_request_reuse(setup):
    client, factory, ids = setup
    body = payload(ids)
    first = client.post('/api/notifications/admin', headers=owner(), json=body)
    second = client.post('/api/notifications/admin', headers=owner(), json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()['id'] == second.json()['id']
    assert client.post('/api/notifications/admin', headers=owner(), json={**body, 'body': 'Outra mensagem'}).status_code == 409
    with factory() as db:
        assert db.query(Notification).count() == db.query(NotificationRecipient).count() == 1


def test_recipient_validation_no_external_links_or_inactive_targets(setup):
    client, factory, ids = setup
    for targets in [[str(ids['Inactive'])], [str(uuid.uuid4())]]:
        response = client.post('/api/notifications/admin', headers=owner(), json=payload(ids, user_ids=targets))
        assert response.status_code == 400
    for path in ['https://evil.example', '//evil.example', '/dashboard#x', '/dashboard\\evil', '/%2f%2fevil', '/unknown']:
        assert client.post('/api/notifications/admin', headers=owner(), json=payload(ids, action_path=path)).status_code == 422
    assert client.post('/api/notifications/admin', headers=owner(), json=payload(ids, action_path='/auditoria')).status_code == 400
    with factory() as db:
        assert db.query(Notification).count() == 0


def test_read_is_separate_from_acknowledgement_and_response_is_immutable(setup):
    client, _, _ = setup
    notice = create(setup)
    base = f"/api/notifications/{notice['id']}"
    assert client.post(base + '/read').status_code == 200
    row = client.get('/api/notifications/inbox').json()['items'][0]
    assert row['read_at'] and row['acknowledged_at'] is None
    assert client.post(base + '/acknowledge', json={}).status_code == 400
    assert client.post(base + '/acknowledge', json={'note': 'Venda avulsa legítima', 'expected_version': 2}).status_code == 409
    assert client.post(base + '/acknowledge', json={'note': 'Venda avulsa legítima', 'expected_version': 1}).status_code == 200
    assert client.post(base + '/acknowledge', json={'note': 'Venda avulsa legítima'}).status_code == 200
    assert client.post(base + '/acknowledge', json={'note': 'Outra resposta'}).status_code == 409
    row = client.get('/api/notifications/inbox').json()['items'][0]
    assert row['acknowledged_version'] == 1 and row['acknowledgement_note'] == 'Venda avulsa legítima'
    admin = client.get('/api/notifications/admin', headers=owner()).json()
    assert admin['items'][0]['receipts'][0]['acknowledgement_note'] == 'Venda avulsa legítima'


def test_edit_preserves_history_receipts_and_hides_removed_recipients(setup):
    client, factory, ids = setup
    notice = create(setup)
    client.post(f"/api/notifications/{notice['id']}/read")
    body = payload(ids, user_ids=[str(ids['Junior'])], title='Mensagem corrigida', expected_version=1)
    body.pop('request_id')
    response = client.patch(f"/api/notifications/admin/{notice['id']}", headers=owner(), json=body)
    assert response.status_code == 200, response.text
    assert response.json()['version'] == 2
    assert client.get('/api/notifications/inbox').json()['items'] == []
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['total'] == 1
    assert client.patch(f"/api/notifications/admin/{notice['id']}", headers=owner(), json=body).status_code == 409
    history = client.get(f"/api/notifications/admin/{notice['id']}/history", headers=owner()).json()['items']
    assert [row['version'] for row in history] == [1, 2]
    assert history[0]['snapshot']['user_ids'] == [str(ids['Sol'])]
    with factory() as db:
        original = db.query(NotificationRecipient).filter_by(user_id=ids['Sol']).one()
        assert original.read_at and original.removed_at
    cancel = client.post(f"/api/notifications/admin/{notice['id']}/cancel", headers=owner(), json={'expected_version': 2})
    assert cancel.status_code == 200 and cancel.json()['cancelled_at']
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['items'] == []
    body['expected_version'] = 3
    assert client.patch(f"/api/notifications/admin/{notice['id']}", headers=owner(), json=body).status_code == 409


def test_scheduled_notice_visibility_and_bounded_publication(setup):
    client, factory, _ = setup
    due = utcnow() + timedelta(minutes=10)
    notice = create(setup, scheduled_at=due.isoformat())
    assert notice['published_at'] is None
    assert client.get('/api/notifications/inbox').json()['total'] == 0
    with factory() as db:
        assert service.publish_due_notifications(db, due - timedelta(seconds=1)) == 0
        assert service.publish_due_notifications(db, due + timedelta(seconds=1)) == 1
        db.commit()
        assert service.publish_due_notifications(db, due + timedelta(seconds=2)) == 0
        saved = db.get(Notification, uuid.UUID(notice['id']))
        assert saved.published_at
    # Client clocks cannot make a future publication visible before the server's time.
    assert client.get('/api/notifications/inbox').json()['total'] == 0


def test_preferences_are_per_user_and_inbox_is_never_silently_dropped(setup):
    client, _, _ = setup
    prefs = {'push_enabled': False, 'sound_enabled': False, 'categories': ['manual']}
    assert client.put('/api/notifications/preferences', json=prefs).json() == prefs
    assert client.get('/api/notifications/preferences', headers={'X-User': 'Junior'}).json()['push_enabled'] is True
    create(setup)
    assert client.get('/api/notifications/inbox').json()['unread_count'] == 1
    assert client.post('/api/notifications/read-all').status_code == 200
    assert client.get('/api/notifications/inbox').json()['unread_count'] == 0
    assert client.get('/api/notifications/inbox?unread_only=true').json()['items'] == []


def test_templates_allow_only_safe_variables_and_edits_are_versioned(setup):
    client, factory, ids = setup
    admin = client.get('/api/notifications/admin', headers=owner()).json()
    templates = {row['name']: row for row in admin['templates']}
    rules = {row['event_key']: row for row in admin['rules']}
    assert rules['sale_avulso_without_reason']['enabled']
    assert rules['morning_greeting']['enabled'] and rules['afternoon_greeting']['enabled']
    assert not rules['daily_greeting']['enabled']
    template = templates['Conferir itens avulsos']
    body = {key: template[key] for key in ('name', 'title', 'body', 'category', 'severity', 'action_path', 'requires_ack', 'requires_response')}
    body.update(expected_version=1)
    for unsafe in ['{user_name.__class__}', '{user_name!r}', '{user_name:>99999}', '{unknown}', '{']:
        assert client.patch(f"/api/notifications/templates/{template['id']}", headers=owner(), json={**body, 'body': unsafe}).status_code == 422
    body['body'] = 'Olá {user_name}: confira {sale_code}.'
    assert client.patch(f"/api/notifications/templates/{template['id']}", headers=owner(), json=body).status_code == 200
    assert client.patch(f"/api/notifications/templates/{template['id']}", headers=owner(), json=body).status_code == 409
    with factory() as db:
        service.ensure_defaults(db)
        assert db.get(NotificationTemplate, uuid.UUID(template['id'])).body == body['body']
        rule = db.get(NotificationRule, 'sale_avulso_without_reason')
        rule.user_ids = [str(ids['Junior']), str(ids['Sol'])]
        db.commit()
        notification = service.emit_event(db, 'sale_avulso_without_reason', context={'user_name': 'Sol', 'sale_code': 'ABC', '__class__': 'x'},
            user_ids=[ids['Sol'], ids['Lucas']], dedupe_key='sale:abc:review')
        db.commit()
        assert notification.body == 'Olá Sol: confira ABC.'
        assert [row.user_id for row in db.query(NotificationRecipient).filter_by(notification_id=notification.id)] == [ids['Sol']]


def test_daily_rules_have_brasilia_window_once_per_day_and_no_deploy_night_spam(setup):
    _, factory, _ = setup
    with factory() as db:
        # 23:00 in Brasília: neither morning nor afternoon greetings should replay on deploy.
        assert service.run_notification_rules(db, datetime(2026, 10, 27, 2, 0, tzinfo=timezone.utc)) == 0
        assert service.run_notification_rules(db, datetime(2026, 10, 27, 12, 1, tzinfo=timezone.utc)) == 1
        assert service.run_notification_rules(db, datetime(2026, 10, 27, 12, 2, tzinfo=timezone.utc)) == 0
        assert service.run_notification_rules(db, datetime(2026, 10, 27, 17, 0, tzinfo=timezone.utc)) == 1
        db.commit()
        assert db.query(Notification).count() == 2
        assert db.query(NotificationRecipient).count() == 6  # Only the three active users.


def test_event_transaction_rollback_and_idempotency(setup):
    _, factory, ids = setup
    with factory() as db:
        service.ensure_defaults(db)
        db.commit()
        first = service.emit_event(db, 'sale_completed', context={'user_name': 'Sol', 'sale_code': 'ABC'},
            user_ids=[ids['Lucas']], dedupe_key='sale:ABC:completed')
        second = service.emit_event(db, 'sale_completed', context={'user_name': 'Sol', 'sale_code': 'ABC'},
            user_ids=[ids['Lucas']], dedupe_key='sale:ABC:completed')
        assert first.id == second.id
        db.rollback()
        assert db.query(Notification).count() == 0
        assert db.query(NotificationRecipient).count() == 0


def test_outbox_respects_preferences_keeps_durable_inbox_and_does_not_resend_on_edit(setup):
    client, factory, ids = setup
    with factory() as db:
        for name in ['Sol', 'Junior']:
            session = AuthSession(id=uuid.uuid4(), user_id=ids[name], expires_at=utcnow() + timedelta(days=1))
            db.add(session)
            db.flush()
            db.add(NotificationPushSubscription(id=uuid.uuid4(), user_id=ids[name], auth_session_id=session.id,
                auth_version=0, endpoint_hash=name, endpoint='https://fcm.googleapis.com/test/' + name,
                p256dh='local', auth='local', device_token_hash='local', device_token_encrypted='unused'))
        db.add(NotificationPreference(user_id=ids['Junior'], push_enabled=False, sound_enabled=True, categories=['sales']))
        db.commit()
    notice = create(setup, user_ids=[str(ids['Sol']), str(ids['Junior'])])
    with factory() as db:
        assert db.query(NotificationRecipient).count() == 2
        assert db.query(NotificationPushDelivery).count() == 1
    body = payload(ids, user_ids=[str(ids['Sol']), str(ids['Junior'])], title='Corrigido', expected_version=1)
    body.pop('request_id')
    assert client.patch(f"/api/notifications/admin/{notice['id']}", headers=owner(), json=body).status_code == 200
    with factory() as db:
        assert db.query(NotificationPushDelivery).count() == 1
    assert client.post(f"/api/notifications/admin/{notice['id']}/cancel", headers=owner(), json={'expected_version': 2}).status_code == 200
    with factory() as db:
        assert db.query(NotificationPushDelivery).one().status == 'dead'


def test_reusable_template_with_unavailable_values_keeps_event_message_valid(setup):
    client, factory, ids = setup
    admin = client.get('/api/notifications/admin', headers=owner()).json()
    template = next(row for row in admin['templates'] if row['name'] == 'Venda concluída')
    body = {key: template[key] for key in ('name', 'title', 'body', 'category', 'severity', 'action_path', 'requires_ack', 'requires_response')}
    body.update(title='{tracking_code}', body=' {status} ', expected_version=template['version'])
    changed = client.patch(f"/api/notifications/templates/{template['id']}", headers=owner(), json=body)
    assert changed.status_code == 200, changed.text
    with factory() as db:
        notification = service.emit_event(db, 'sale_completed', context={'user_name': 'Sol', 'sale_code': 'ABC'},
            user_ids=[ids['Lucas']], dedupe_key='sale:template-empty:completed')
        db.commit()
        assert notification.title == 'Venda #ABC concluída'
        assert notification.body == 'Sol concluiu uma venda. Abra o sistema para conferir.'
        # A valid customized field is preserved while the other field falls back.
        saved = db.get(NotificationTemplate, uuid.UUID(template['id']))
        saved.title = 'Meu aviso: {sale_code}'
        db.commit()
        customized = service.emit_event(db, 'sale_completed', context={'user_name': 'Sol', 'sale_code': 'DEF'},
            user_ids=[ids['Lucas']], dedupe_key='sale:template-custom:completed')
        db.commit()
        assert customized.title == 'Meu aviso: DEF'
        assert customized.body == 'Sol concluiu uma venda. Abra o sistema para conferir.'
