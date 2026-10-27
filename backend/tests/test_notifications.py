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
from app.models.cliente import Cliente
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem
from app.models.inventory import Item, Supplier
from app.models.access import AuthSession, AuditEvent
from app.models.notification import (
    Notification, NotificationPreference, NotificationRecipient, NotificationRevision,
    NotificationRule, NotificationTemplate, utcnow,
)
from app.models.notification_push import NotificationPushDelivery, NotificationPushSetting, NotificationPushSubscription
from app.api.endpoints import notifications as api
from app.services import notifications as service

MODELS = (Usuario, Vendedor, AuthSession, AuditEvent, Cliente, PdvCliente, PdvSale, PdvSaleItem, Supplier, Item, Notification, NotificationRecipient,
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


def context_fixtures(factory, ids):
    sale_id = uuid.UUID('8b316ebb-ca00-4000-8000-000000000001')
    product_id, reference_id = uuid.uuid4(), uuid.uuid4()
    with factory() as db:
        db.add_all([Item(id=product_id, name='Camiseta vinculada', sku_internal='CONTEXT-ONE', inventory_code='INV-CONTX1', is_active=True,
                       image_data='PRIVATE-ORIGINAL', additional_images=['PRIVATE-GALLERY'], cost_price=123, sale_price=456),
                    Item(id=reference_id, name='Produto de referência', sku_internal='CONTEXT-REF', inventory_code='INV-CONTX2', is_active=True)])
        db.add(PdvSale(id=sale_id, vendedor_id=ids['Sol'], status='completed', total_gs=999, notas='PRIVATE-SALE-NOTE', cliente_nome='PRIVATE-CUSTOMER'))
        db.flush()
        db.add_all([PdvSaleItem(sale_id=sale_id, item_id=product_id, item_name='Camiseta vinculada', item_size='M', item_color='Azul',
                               is_avulso=False, quantity=1, unit_price_gs=999, total_gs=999),
                    PdvSaleItem(sale_id=sale_id, item_id=None, item_name='Item avulso', is_avulso=True,
                               quantity=1, unit_price_gs=1, total_gs=1)])
        db.commit()
    return sale_id, product_id, reference_id


def test_manual_template_requires_real_sale_and_renders_recipient_context(setup, monkeypatch):
    from app.api.endpoints import notifications as api_module
    client, factory, ids = setup
    sale_id, _, _ = context_fixtures(factory, ids)
    rejected = client.post('/api/notifications/admin', headers=owner(), json=payload(ids, title='Venda {sale_code}', body='Olá {user_name}'))
    assert rejected.status_code == 400 and 'venda real' in rejected.json()['detail']
    fixed = datetime(2026, 10, 27, 14, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(api_module, 'utcnow', lambda: fixed)
    body = payload(ids, title='Conferir #{sale_code}', body='Olá {user_name}, confira em {date} às {time}.',
                   context={'sale_id': str(sale_id), 'target': 'sale'}, user_ids=[str(ids['Lucas']), str(ids['Sol'])])
    result = client.post('/api/notifications/admin', headers=owner(), json=body)
    assert result.status_code == 201, result.text
    value = result.json()
    assert value['title'] == 'Conferir #8B316EBBCA'
    assert value['body'] == 'Olá Sol, confira em 27/10/2026 às 11:45.'
    assert value['action_path'] == '/vendas-pdv?sale_id=' + str(sale_id)
    assert value['authored_title'] == body['title'] and value['authored_body'] == body['body']
    assert value['context'] == body['context']
    with factory() as db:
        original = db.query(NotificationRevision).one()
        assert original.snapshot['authoring']['title'] == 'Conferir #{sale_code}'
        assert db.query(Notification).one().entity_id == str(sale_id)
    # A retried UUID returns the same frozen text even after the context changes
    # or is no longer available; it does not re-render or create another push.
    with factory() as db:
        db.get(Usuario, ids['Sol']).nome = 'Sol renomeada'
        db.get(Usuario, ids['Sol']).ativo = False
        db.get(PdvSale, sale_id).deleted_at = fixed
        db.commit()
    monkeypatch.setattr(api_module, 'utcnow', lambda: fixed + timedelta(days=1))
    retry = client.post('/api/notifications/admin', headers=owner(), json=body)
    assert retry.status_code == 201 and retry.json()['body'] == value['body']
    assert client.post('/api/notifications/admin', headers=owner(), json={**body, 'context': None}).status_code == 409
    with factory() as db:
        assert db.query(Notification).count() == 1


def test_plain_manual_user_name_uses_unique_recipient_or_team(setup):
    client, _, ids = setup
    single = create(setup, body='Bom dia, {user_name}.')
    assert single['body'] == 'Bom dia, Sol.'
    group = create(setup, body='Bom dia, {user_name}.', user_ids=[str(ids['Sol']), str(ids['Junior'])])
    assert group['body'] == 'Bom dia, equipe.'
    assert client.post('/api/notifications/admin', headers=owner(), json=payload(ids, body='Código {tracking_code}')).status_code == 400
    assert client.post('/api/notifications/admin', headers=owner(), json=payload(ids, body='{user_name.__class__}')).status_code == 422


def test_manual_literal_braces_remain_compatible_after_edit_and_cancel(setup):
    client, factory, ids = setup
    literal = 'Kit {P,M,L}: {"erro":true}; literal {{sale_code}}. Olá {user_name}.'
    notice = create(setup, title='Texto {{sale_code}}', body=literal)
    expected = 'Kit {P,M,L}: {"erro":true}; literal {sale_code}. Olá Sol.'
    assert notice['title'] == 'Texto {sale_code}' and notice['body'] == expected
    assert client.get('/api/notifications/inbox').json()['items'][0]['body'] == expected
    changed = payload(ids, title='Texto {{sale_code}}', body=literal + ' Confira {quantidade}.', expected_version=1)
    changed.pop('request_id')
    response = client.patch('/api/notifications/admin/' + notice['id'], headers=owner(), json=changed)
    assert response.status_code == 200, response.text
    assert response.json()['body'] == expected + ' Confira {quantidade}.'
    assert client.get('/api/notifications/inbox').json()['items'][0]['body'] == response.json()['body']
    cancelled = client.post('/api/notifications/admin/' + notice['id'] + '/cancel', headers=owner(), json={'expected_version': 2})
    assert cancelled.status_code == 200 and cancelled.json()['body'] == response.json()['body']
    assert cancelled.json()['authored_body'] == changed['body']
    history = client.get('/api/notifications/admin/' + notice['id'] + '/history', headers=owner()).json()['items']
    assert [row['version'] for row in history] == [1, 2, 3]
    assert history[0]['snapshot']['authoring']['body'] == literal
    assert history[1]['snapshot']['authoring'] == history[2]['snapshot']['authoring']
    assert history[0]['snapshot']['body'] == expected
    with factory() as db:
        legacy = service.emit_notification(db, title='Kit {P,M,L}', body='Dados {"erro":true}', user_ids=[ids['Sol']])
        db.commit()
        legacy_id = legacy.id
    changed.update(title='Kit {P,M,L}', body='Dados {"erro":true}', expected_version=1)
    assert client.patch('/api/notifications/admin/' + str(legacy_id), headers=owner(), json=changed).status_code == 200


@pytest.mark.parametrize('unsafe', ['{user_name.__class__}', '{user_name!r}', '{sale_code:>20}', '{user_name[0]}', '{sale_code'])
def test_manual_known_variable_syntax_still_rejects_unsafe_or_incomplete_fields(setup, unsafe):
    client, _, ids = setup
    assert client.post('/api/notifications/admin', headers=owner(), json=payload(ids, body=unsafe)).status_code == 422


def test_product_reference_can_be_outside_sale_without_rewriting_associations(setup):
    client, factory, ids = setup
    sale_id, member_id, reference_id = context_fixtures(factory, ids)
    context = {'sale_id': str(sale_id), 'item_id': str(reference_id), 'target': 'product'}
    result = create(setup, context=context, body='Sol, confira o produto de referência da venda {sale_code}.')
    assert result['action_path'] == '/inventory?item_id=' + str(reference_id)
    assert result['context'] == context
    with factory() as db:
        notice = db.query(Notification).one()
        assert notice.entity_type == 'pdv_sale' and notice.entity_id == str(sale_id)
        assert {row.item_id for row in db.query(PdvSaleItem).filter_by(sale_id=sale_id)} == {None, member_id}
        assert db.get(PdvSale, sale_id).notas == 'PRIVATE-SALE-NOTE'
        db.get(Item, reference_id).is_active = False
        db.commit()
    assert client.post('/api/notifications/admin', headers=owner(), json=payload(ids, context=context)).status_code == 404
    assert client.get('/api/notifications/context/products/' + str(reference_id), headers=owner()).status_code == 404


def test_source_sale_scope_is_enforced_for_product_links_and_after_access_reduction(setup):
    client, factory, ids = setup
    sale_id, _, reference_id = context_fixtures(factory, ids)
    linked = {'sale_id': str(sale_id), 'item_id': str(reference_id), 'target': 'product'}
    denied = client.post('/api/notifications/admin', headers=owner(), json=payload(ids, context=linked, user_ids=[str(ids['Junior'])]))
    assert denied.status_code == 400
    with factory() as db:
        db.get(Usuario, ids['Junior']).sales_scope = 'all'
        db.commit()
    notice = create(setup, context=linked, user_ids=[str(ids['Junior'])])
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['total'] == 1
    with factory() as db:
        db.get(Usuario, ids['Junior']).sales_scope = 'own'
        db.commit()
    inbox = client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()
    assert inbox['total'] == inbox['unread_count'] == 0
    assert client.post(f"/api/notifications/{notice['id']}/acknowledge", headers={'X-User': 'Junior'}, json={'note': 'no'}).status_code == 404
    assert client.post(f"/api/notifications/{notice['id']}/read", headers={'X-User': 'Junior'}).status_code == 404


def test_context_lookups_are_owner_only_bounded_and_omit_customer_prices_photos(setup):
    client, factory, ids = setup
    sale_id, member_id, _ = context_fixtures(factory, ids)
    base = '/api/notifications/context'
    for path in ['/sales', '/sales/' + str(sale_id), '/products/' + str(member_id)]:
        assert client.get(base + path).status_code == 403
    result = client.get(base + '/sales?search=%238B316EBBCA', headers=owner())
    assert result.status_code == 200 and result.json()['items'][0]['id'] == str(sale_id)
    assert client.get(base + '/sales?search=not-a-code', headers=owner()).json()['items'] == []
    assert client.get(base + '/sales?limit=31', headers=owner()).status_code == 422
    selects = []
    def capture(conn, cursor, statement, parameters, context, many):
        if statement.startswith('SELECT'):
            selects.append(statement)
    from sqlalchemy import event
    event.listen(factory.kw['bind'], 'before_cursor_execute', capture)
    try:
        detail = client.get(base + '/sales/' + str(sale_id), headers=owner()).json()
        product = client.get(base + '/products/' + str(member_id), headers=owner()).json()
    finally:
        event.remove(factory.kw['bind'], 'before_cursor_execute', capture)
    assert detail['code'] == '8B316EBBCA' and detail['seller_id'] == str(ids['Sol'])
    assert detail['items_total'] == 2 and any(row['item_id'] is None for row in detail['items'])
    assert product['name'] == 'Camiseta vinculada' and product['inventory_code'] == 'INV-CONTX1'
    assert not any(word in str(detail) + str(product) for word in ('PRIVATE', 'price', 'total_gs', 'image'))
    assert all('image_data' not in sql and 'additional_images' not in sql and 'unit_price_gs' not in sql for sql in selects)


def test_old_placeholder_message_is_repaired_for_display_without_mutating_history(setup):
    client, factory, ids = setup
    sale_id, _, _ = context_fixtures(factory, ids)
    with factory() as db:
        known = service.emit_notification(db, title='Venda {sale_code}', body='Olá {user_name}.', user_ids=[ids['Sol']],
            entity_type='pdv_sale', entity_id=sale_id, action_path='/vendas-pdv?sale_id=' + str(sale_id))
        unknown = service.emit_notification(db, title='Conferir {sale_code}', body='Olá {user_name}: {date}.', user_ids=[ids['Sol']])
        db.commit()
        known_id, unknown_id = known.id, unknown.id
    inbox = {entry['id']: entry for entry in client.get('/api/notifications/inbox').json()['items']}
    assert inbox[str(known_id)]['title'] == 'Venda 8B316EBBCA' and inbox[str(known_id)]['body'] == 'Olá Sol.'
    assert 'venda não vinculada' in inbox[str(unknown_id)]['title']
    assert '{date}' not in inbox[str(unknown_id)]['body']
    with factory() as db:
        original = db.get(Notification, known_id)
        assert original.title == 'Venda {sale_code}' and original.body == 'Olá {user_name}.'
        assert db.query(NotificationRevision).filter_by(notification_id=known_id).one().snapshot['title'] == 'Venda {sale_code}'


def test_edit_keeps_raw_template_and_reference_in_versioned_snapshot(setup):
    client, factory, ids = setup
    sale_id, _, reference_id = context_fixtures(factory, ids)
    notice = create(setup, title='Venda {sale_code}', body='Olá {user_name}.', context={'sale_id': str(sale_id), 'target': 'sale'})
    changed = payload(ids, title='Conferir {sale_code}', body='Olá {user_name}, veja o produto de referência.',
                      expected_version=1, context={'sale_id': str(sale_id), 'item_id': str(reference_id), 'target': 'product'})
    changed.pop('request_id')
    response = client.patch('/api/notifications/admin/' + notice['id'], headers=owner(), json=changed)
    assert response.status_code == 200, response.text
    assert response.json()['title'] == 'Conferir 8B316EBBCA'
    assert response.json()['context'] == changed['context'] and response.json()['authored_body'] == changed['body']
    assert response.json()['action_path'] == '/inventory?item_id=' + str(reference_id)
    assert client.patch('/api/notifications/admin/' + notice['id'], headers=owner(), json=changed).status_code == 409
    with factory() as db:
        rows = db.query(NotificationRevision).filter_by(notification_id=uuid.UUID(notice['id'])).order_by(NotificationRevision.version).all()
        assert rows[0].snapshot['context']['target'] == 'sale'
        assert rows[1].snapshot['context']['target'] == 'product'
        assert rows[1].snapshot['authoring']['body'] == changed['body']
        db.get(Item, reference_id).is_active = False
        db.commit()
    assert client.get('/api/notifications/inbox').json()['items'][0]['action_path'] is None
    cancelled = client.post('/api/notifications/admin/' + notice['id'] + '/cancel', headers=owner(), json={'expected_version': 2})
    assert cancelled.status_code == 200 and cancelled.json()['context'] == changed['context']
    assert cancelled.json()['authored_title'] == changed['title']
    history = client.get('/api/notifications/admin/' + notice['id'] + '/history', headers=owner()).json()['items']
    assert history[-1]['snapshot']['context'] == history[-2]['snapshot']['context'] == changed['context']
    assert history[-1]['snapshot']['authoring'] == history[-2]['snapshot']['authoring']


def test_legacy_sale_link_without_entity_obeys_scope_before_count_page_and_push(setup):
    from app.services import notification_push
    client, factory, ids = setup
    sale_id, _, _ = context_fixtures(factory, ids)
    with factory() as db:
        # Simulate an old manual message authored before explicit context existed.
        notice = service.emit_notification(db, title='Venda {sale_code}', body='Olá {user_name}.', user_ids=[ids['Junior']],
            action_path='/vendas-pdv?sale_id=' + str(sale_id))
        session = AuthSession(id=uuid.uuid4(), user_id=ids['Junior'], expires_at=utcnow() + timedelta(days=1))
        db.add(session)
        db.flush()
        subscription = NotificationPushSubscription(id=uuid.uuid4(), user_id=ids['Junior'], auth_session_id=session.id,
            auth_version=0, endpoint_hash='fixture-scope-endpoint', endpoint='https://fcm.googleapis.com/local-scope-only',
            p256dh='unused-local', auth='unused-local', device_token_hash='unused', device_token_encrypted='unused-local')
        db.add(subscription)
        db.flush()
        receipt = db.query(NotificationRecipient).filter_by(notification_id=notice.id).one()
        delivery = NotificationPushDelivery(notification_id=notice.id, recipient_id=receipt.id, subscription_id=subscription.id,
            status='queued', next_attempt_at=utcnow())
        db.add(delivery)
        db.commit()
        delivery_id = delivery.id
        assert notification_push.claim_delivery(db) is None
        db.commit()
        assert db.get(NotificationPushDelivery, delivery_id).last_error == 'expired_or_disabled'
    response = client.get('/api/notifications/inbox?page_size=1', headers={'X-User': 'Junior'}).json()
    assert response['items'] == [] and response['total'] == response['unread_count'] == 0


@pytest.mark.parametrize('query_kind', ['duplicate', 'encoded', 'blank_duplicate'])
def test_ambiguous_legacy_sale_query_fails_closed_for_inbox_read_ack_and_push(setup, query_kind):
    from app.services.notification_context import notification_allowed
    client, factory, ids = setup
    sale_id, _, _ = context_fixtures(factory, ids)
    with factory() as db:
        owned_sale = PdvSale(id=uuid.uuid4(), vendedor_id=ids['Junior'], status='completed')
        db.add(owned_sale)
        db.flush()
        query = {'duplicate': f'sale_id={sale_id}&sale_id={owned_sale.id}',
                 'encoded': f'sale%5Fid={sale_id}', 'blank_duplicate': f'sale_id={owned_sale.id}&sale_id='}[query_kind]
        notice = service.emit_notification(db, title='Venda privada de Sol', body='Motivo privado.', user_ids=[ids['Junior']],
            action_path='/vendas-pdv?' + query)
        db.commit()
        notice_id = notice.id
        assert notification_allowed(db, db.get(Usuario, ids['Junior']), notice) is False
    response = client.get('/api/notifications/inbox?limit=1', headers={'X-User': 'Junior'}).json()
    assert response['items'] == [] and response['total'] == response['unread_count'] == 0
    assert client.post(f'/api/notifications/{notice_id}/read', headers={'X-User': 'Junior'}).status_code == 404
    assert client.post(f'/api/notifications/{notice_id}/acknowledge', headers={'X-User': 'Junior'}, json={}).status_code == 404
