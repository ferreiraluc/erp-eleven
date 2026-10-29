"""Configured audiences apply to future events without widening sale access."""
import uuid

import pytest

from app.models.notification import Notification, NotificationRecipient, NotificationRule
from app.models.pdv import PdvSale
from app.models.usuario import Usuario
from app.services import notifications as service
from test_notifications import owner, setup


@pytest.mark.parametrize('event_key,expected_names', [
    ('sale_completed', {'Sol'}),
    ('tracking_status_changed', {'Sol', 'Junior'}),
])
def test_saved_selection_reaches_inboxes_even_when_event_defaults_only_include_lucas(setup, event_key, expected_names):
    client, factory, ids = setup
    state = client.get('/api/notifications/admin', headers=owner()).json()
    rule = next(row for row in state['rules'] if row['event_key'] == event_key)
    selected = [str(ids[name]) for name in ('Sol', 'Junior')]
    body = {key: rule[key] for key in ('enabled', 'template_id', 'local_time', 'weekdays')}
    body.update(expected_version=rule['version'], user_ids=selected)
    result = client.put(f'/api/notifications/rules/{event_key}', headers=owner(), json=body)
    assert result.status_code == 200, result.text
    saved = client.get('/api/notifications/admin', headers=owner()).json()
    assert next(row for row in saved['rules'] if row['event_key'] == event_key)['user_ids'] == selected
    # A stale editor cannot accidentally restore the previous audience.
    assert client.put(f'/api/notifications/rules/{event_key}', headers=owner(), json={**body, 'user_ids': []}).status_code == 409
    with factory() as db:
        sale = PdvSale(id=uuid.uuid4(), vendedor_id=ids['Sol'], status='completed', total_gs=100)
        db.add(sale)
        db.commit()
        sale_event = event_key == 'sale_completed'
        notice = service.emit_event(db, event_key, context={'user_name': 'Sol', 'tracking_code': 'FIXTURE123BR'},
            user_ids=[ids['Lucas']], dedupe_key=f'{event_key}:selected',
            entity_type='pdv_sale' if sale_event else 'tracking', entity_id=sale.id if sale_event else uuid.uuid4(),
            action_path=f'/vendas-pdv?sale_id={sale.id}' if sale_event else '/rastreamento?search=FIXTURE123BR')
        db.commit()
        assert notice and notice.action_path
        assert {row.user_id for row in db.query(NotificationRecipient)} == {ids[name] for name in expected_names}
    for name in ('Lucas', 'Sol', 'Junior'):
        inbox = client.get('/api/notifications/inbox', headers={'X-User': name}).json()
        assert inbox['total'] == int(name in expected_names)


@pytest.mark.parametrize('link', ['sale', 'product', 'none'])
def test_sale_entity_filters_selected_audience_before_publishing_regardless_of_shortcut(setup, link):
    _, factory, ids = setup
    with factory() as db:
        service.ensure_defaults(db)
        sale = PdvSale(id=uuid.uuid4(), vendedor_id=ids['Sol'], status='completed', total_gs=100)
        db.add(sale)
        db.get(NotificationRule, 'sale_completed').user_ids = [str(ids['Junior'])]
        db.commit()
        path = {'sale': f'/vendas-pdv?sale_id={sale.id}', 'product': '/inventory', 'none': None}[link]
        args = dict(context={'sale_total': '100', 'user_name': 'Sol'}, user_ids=[ids['Lucas']],
                    entity_type='pdv_sale', entity_id=sale.id, action_path=path)
        assert service.emit_event(db, 'sale_completed', **args, dedupe_key='sale:no-access') is None
        assert db.query(Notification).count() == db.query(NotificationRecipient).count() == 0
        # A selected user with existing general-sales access is eligible.
        db.get(Usuario, ids['Junior']).sales_scope = 'all'
        db.commit()
        first = service.emit_event(db, 'sale_completed', **args, dedupe_key='sale:general-access')
        db.commit()
        assert {row.user_id for row in db.query(NotificationRecipient)} == {ids['Junior']}
        # Updating recipients does not replay historical events to other users.
        db.get(NotificationRule, 'sale_completed').user_ids = [str(ids['Lucas'])]
        db.commit()
        replay = service.emit_event(db, 'sale_completed', **args, dedupe_key='sale:general-access')
        db.commit()
        assert replay.id == first.id
        assert db.query(Notification).count() == 1
        assert {row.user_id for row in db.query(NotificationRecipient)} == {ids['Junior']}
