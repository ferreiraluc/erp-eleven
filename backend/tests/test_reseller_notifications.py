"""A reseller can receive sale summaries without gaining sale or customer access."""
from datetime import timedelta
import json
import uuid

from app.models.access import AuthSession
from app.models.notification import Notification, NotificationRecipient, NotificationRule, NotificationTemplate, utcnow
from app.models.pdv import PdvSale
from app.models.usuario import Usuario, UsuarioRole
from app.services import notification_context, notification_push, notifications
from test_notifications import owner, setup
from test_notification_push import subscription


def prepare(factory, ids, recipients=('Lucas', 'Junior')):
    with factory() as db:
        reseller = db.get(Usuario, ids['Junior'])
        reseller.access_profile, reseller.role = 'reseller', UsuarioRole.VENDEDOR
        reseller.sales_scope = 'own'
        notifications.ensure_defaults(db)
        db.get(NotificationRule, 'sale_completed').user_ids = [str(ids[name]) for name in recipients]
        sale = PdvSale(id=uuid.uuid4(), vendedor_id=ids['Sol'], status='completed', total_gs=480000, usd_rate_gs=6000)
        db.add(sale)
        db.commit()
        return sale.id


def emit(db, ids, identity, key='fixture-sale', event='sale_completed'):
    return notifications.emit_event(db, event, context={'user_name': 'Sol', 'sale_total': '80'},
        user_ids=[ids['Lucas']], dedupe_key=key, entity_type='pdv_sale', entity_id=identity,
        action_path=f'/vendas-pdv?sale_id={identity}')


def test_reseller_summary_is_separate_from_team_details_and_can_be_selected(setup):
    client, factory, ids = setup
    identity = prepare(factory, ids)
    state = client.get('/api/notifications/admin', headers=owner()).json()
    rule = next(row for row in state['rules'] if row['event_key'] == 'sale_completed')
    payload = {key: rule[key] for key in ('enabled', 'template_id', 'user_ids', 'local_time', 'weekdays')}
    payload['expected_version'] = rule['version']
    assert client.put('/api/notifications/rules/sale_completed', headers=owner(), json=payload).status_code == 200
    with factory() as db:
        template = db.get(NotificationTemplate, db.get(NotificationRule, 'sale_completed').template_id)
        template.body = 'Detalhe interno: cliente e pagamento.'
        db.commit()
        team = emit(db, ids, identity)
        db.commit()
        assert team.action_path == f'/vendas-pdv?sale_id={identity}'
        assert db.query(Notification).count() == 2
        summary = db.query(Notification).filter_by(entity_type='pdv_sale_summary').one()
        assert summary.title == 'Venda U$ 80 concluída'
        assert summary.body == 'Sol concluiu uma venda.'
        assert summary.action_path is None and not summary.requires_ack and not summary.requires_response
        assert notifications.action_allowed(db, db.get(Usuario, ids['Junior']), team.action_path) is False
    reseller = client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()
    assert reseller['total'] == reseller['unread_count'] == 1
    assert reseller['items'][0]['action_path'] is None
    assert 'cliente' not in reseller['items'][0]['body']
    assert client.get('/api/notifications/inbox', headers=owner()).json()['items'][0]['action_path'] == team.action_path


def test_old_employee_inbox_and_other_event_categories_stay_hidden(setup):
    client, factory, ids = setup
    identity = prepare(factory, ids)
    with factory() as db:
        reseller = db.get(Usuario, ids['Junior'])
        reseller.access_profile, reseller.sales_scope = 'standard', 'all'
        notifications.emit_notification(db, title='Histórico privado', body='Detalhes anteriores',
            user_ids=[reseller.id], entity_type='pdv_sale', entity_id=identity, category='sales')
        db.commit()
        reseller.access_profile, reseller.sales_scope = 'reseller', 'own'
        notifications.ensure_defaults(db)
        db.get(NotificationRule, 'tracking_status_changed').user_ids = [str(reseller.id)]
        db.commit()
        assert emit(db, ids, identity, key='tracking', event='tracking_status_changed') is None
        emit(db, ids, identity)
        db.commit()
        summary = db.query(Notification).filter_by(entity_type='pdv_sale_summary').one()
        assert notification_context.notification_allowed(db, reseller, summary)
        old = db.query(Notification).filter_by(title='Histórico privado').one()
        assert not notification_context.notification_allowed(db, reseller, old)
    inbox = client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()
    assert inbox['total'] == 1
    assert client.post(f'/api/notifications/{old.id}/read', headers={'X-User': 'Junior'}).status_code == 404
    with factory() as db:
        db.get(PdvSale, identity).deleted_at = utcnow()
        db.commit()
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['total'] == 0


def test_retries_or_audience_changes_do_not_replay_old_sales(setup):
    _, factory, ids = setup
    identity = prepare(factory, ids, recipients=('Lucas',))
    with factory() as db:
        first = emit(db, ids, identity)
        db.commit()
        db.get(NotificationRule, 'sale_completed').user_ids = [str(ids['Lucas']), str(ids['Junior'])]
        db.commit()
        assert emit(db, ids, identity).id == first.id
        db.commit()
        assert db.query(Notification).count() == db.query(NotificationRecipient).count() == 1
        next_sale = PdvSale(id=uuid.uuid4(), vendedor_id=ids['Sol'], status='completed', total_gs=600000, usd_rate_gs=6000)
        db.add(next_sale)
        db.commit()
        emit(db, ids, next_sale.id, key='next-sale')
        db.commit()
        emit(db, ids, next_sale.id, key='next-sale')
        db.commit()
        assert db.query(Notification).count() == 3
        assert db.query(NotificationRecipient).filter_by(user_id=ids['Junior']).count() == 1


def test_push_uses_summary_and_notification_inbox_without_sale_link(setup):
    _, factory, ids = setup
    identity = prepare(factory, ids, recipients=('Junior',))
    with factory() as db:
        reseller = db.get(Usuario, ids['Junior'])
        session = AuthSession(id=uuid.uuid4(), user_id=reseller.id, expires_at=utcnow() + timedelta(hours=1))
        db.add(session)
        db.flush()
        subscription(db, reseller, session)
        db.commit()
        emit(db, ids, identity)
        db.commit()
        claim = notification_push.claim_delivery(db)
        assert claim is not None
        payload = json.loads(claim.payload)
        assert payload['title'] == 'Venda U$ 80 concluída'
        assert payload['body'] == 'Sol concluiu uma venda.'
        assert payload['action_path'] == '/notificacoes'
        assert str(identity) not in claim.payload
        db.rollback()


def test_converting_reseller_to_personal_employee_restricts_old_summaries(setup):
    client, factory, ids = setup
    identity = prepare(factory, ids, recipients=('Junior',))
    with factory() as db:
        emit(db, ids, identity)
        db.commit()
        user = db.get(Usuario, ids['Junior'])
        user.access_profile = 'standard'
        db.commit()
        notice = db.query(Notification).one()
        assert not notification_context.notification_allowed(db, user, notice)
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['total'] == 0
