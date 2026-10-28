"""Recipient template variables use real local package data, with no provider calls."""
import uuid

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.database import Base
from app.models.cliente import Cliente
from app.models.notification import Notification, NotificationRecipient, NotificationRevision, NotificationTemplate
from app.models.pedido import Pedido
from app.models.rastreamento import Rastreamento, RastreamentoStatus
from app.services import notification_context, notifications as service
from test_notifications import setup, create, owner, payload


@compiles(JSONB, 'sqlite')
def jsonb_sqlite(element, compiler, **kw):
    return 'JSON'


@pytest.fixture
def tracking_setup(setup):
    _, factory, _ = setup
    Base.metadata.create_all(factory.kw['bind'], tables=[Pedido.__table__, Rastreamento.__table__])
    return setup


def package(factory, ids, *, name='Cliente destinatário', order_name=None, client_name=None, order_client_name=None):
    with factory() as db:
        customer = Cliente(nome=client_name, cpf=None) if client_name else None
        order_customer = Cliente(nome=order_client_name, cpf=None) if order_client_name else None
        db.add_all([row for row in (customer, order_customer) if row])
        db.flush()
        order = Pedido(numero_pedido=uuid.uuid4().hex, descricao='Synthetic delivery', valor_total=1,
                       cliente_nome=order_name, cliente_id=order_customer.id if order_customer else None)
        db.add(order)
        db.flush()
        row = Rastreamento(codigo_rastreio='FIXTURE' + uuid.uuid4().hex[:10].upper(), destinatario=name,
            pedido_id=order.id, cliente_id=customer.id if customer else None, created_by=ids['Sol'], status=RastreamentoStatus.EM_TRANSITO)
        db.add(row)
        db.commit()
        return row.id, row.codigo_rastreio


def test_owner_tracking_preview_returns_only_the_required_context(tracking_setup):
    client, factory, ids = tracking_setup
    tracking_id, code = package(factory, ids)
    result = client.get('/api/notifications/context/tracking/' + code, headers=owner())
    assert result.status_code == 200
    assert result.json() == {'id': str(tracking_id), 'code': code, 'cliente_username': 'Cliente destinatário', 'status': 'Em trânsito'}
    assert client.get('/api/notifications/context/tracking/' + code, headers={'X-User': 'Sol'}).status_code == 403
    assert client.get('/api/notifications/context/tracking/UNKNOWN', headers=owner()).status_code == 404


@pytest.mark.parametrize('names,expected', [
    ({'name': '  Nome do pacote  ', 'order_name': 'Outro pedido', 'client_name': 'Outro cadastro'}, 'Nome do pacote'),
    ({'name': ' ', 'order_name': 'Nome histórico pedido', 'client_name': 'Nome novo'}, 'Nome histórico pedido'),
    ({'name': None, 'client_name': 'Nome do cliente vinculado'}, 'Nome do cliente vinculado'),
    ({'name': None, 'order_client_name': 'Nome do cliente do pedido'}, 'Nome do cliente do pedido'),
    ({'name': None}, 'destinatário não informado'),
])
def test_manual_tracking_name_uses_only_explicit_references(tracking_setup, names, expected):
    client, factory, ids = tracking_setup
    tracking_id, code = package(factory, ids, **names)
    text = 'Olá {cliente_username}: {tracking_code} está {status}.'
    notice = create(tracking_setup, body=text, action_path='/rastreamento?search=' + code)
    assert notice['body'] == f'Olá {expected}: {code} está Em trânsito.'
    assert notice['authored_body'] == text
    with factory() as db:
        row = db.get(Notification, uuid.UUID(notice['id']))
        assert row.entity_type == 'tracking' and row.entity_id == str(tracking_id)
        assert '00000000000' not in row.body and '{cliente_username}' not in row.body
    assert client.get('/api/notifications/inbox', headers={'X-User': 'Junior'}).json()['total'] == 0


def test_manual_tracking_requires_real_active_context_and_keeps_retry_history_frozen(tracking_setup):
    client, factory, ids = tracking_setup
    tracking_id, code = package(factory, ids)
    for path in (None, '/rastreamento', '/rastreamento?search=UNKNOWN', '/rastreamento?search=' + code + '&search=OTHER'):
        result = client.post('/api/notifications/admin', headers=owner(), json=payload(ids, body='Pacote de {cliente_username}', action_path=path))
        assert result.status_code == 400 and 'rastreio cadastrado' in result.json()['detail']
    body = payload(ids, body='Pacote de {cliente_username}', action_path='/rastreamento?search=' + code)
    result = client.post('/api/notifications/admin', headers=owner(), json=body)
    assert result.status_code == 201
    with factory() as db:
        db.get(Rastreamento, tracking_id).destinatario = 'Nome corrigido posteriormente'
        db.get(Rastreamento, tracking_id).ativo = False
        db.commit()
    retry = client.post('/api/notifications/admin', headers=owner(), json=body)
    assert retry.status_code == 201 and retry.json()['body'] == result.json()['body']
    assert client.post('/api/notifications/admin', headers=owner(), json={**body, 'request_id': str(uuid.uuid4())}).status_code == 400
    with factory() as db:
        revisions = db.query(NotificationRevision).all()
        assert len(revisions) == 1 and revisions[0].snapshot['body'] == 'Pacote de Cliente destinatário'
        assert revisions[0].snapshot['authoring']['body'] == 'Pacote de {cliente_username}'


def test_legacy_tracking_placeholder_display_preserves_original_snapshots(tracking_setup):
    client, factory, ids = tracking_setup
    tracking_id, code = package(factory, ids)
    with factory() as db:
        old = service.emit_notification(db, title='Pacote {tracking_code}', body='Destinatário {cliente_username}',
            user_ids=[ids['Sol']], entity_type='tracking', entity_id=tracking_id)
        unknown = service.emit_notification(db, title='Pacote', body='Destinatário {cliente_username}', user_ids=[ids['Sol']])
        db.commit()
        old_id, unknown_id = old.id, unknown.id
    inbox = {row['id']: row for row in client.get('/api/notifications/inbox').json()['items']}
    assert inbox[str(old_id)]['body'] == 'Destinatário Cliente destinatário' and code in inbox[str(old_id)]['title']
    assert inbox[str(unknown_id)]['body'] == 'Destinatário destinatário não informado'
    with factory() as db:
        assert db.get(Notification, old_id).body == 'Destinatário {cliente_username}'
        assert db.query(NotificationRevision).filter_by(notification_id=old_id).one().snapshot['body'] == 'Destinatário {cliente_username}'


def test_recipient_variable_is_allowed_in_models_but_cannot_use_attributes(setup):
    client, _, _ = setup
    template = {'name': 'Cliente no rastreio', 'title': 'Pacote de {cliente_username}',
                'body': '{tracking_code}: {status}', 'category': 'tracking', 'severity': 'info'}
    result = client.post('/api/notifications/templates', headers=owner(), json=template)
    assert result.status_code == 201 and result.json()['title'] == template['title']
    assert client.post('/api/notifications/templates', headers=owner(), json={**template, 'title': '{cliente_username.__class__}'}).status_code == 422
    assert client.post('/api/notifications/admin', headers=owner(), json=payload(setup[2], body='{cliente_username!r}')).status_code == 422


@pytest.mark.parametrize('changed', [None, 'body', 'title', 'severity', 'version', 'created_by'])
def test_tracking_default_copy_updates_only_pristine_original_and_preserves_sent_history(setup, changed):
    _, factory, ids = setup
    with factory() as db:
        service.ensure_defaults(db)
        template_id = uuid.uuid5(uuid.NAMESPACE_URL, 'erp-eleven/notification-template/tracking_status_changed')
        template = db.get(NotificationTemplate, template_id)
        old = 'Situação atual: {status}. Abra o rastreamento para conferir.'
        template.body = old
        if changed == 'version':
            template.version = 2
        elif changed == 'created_by':
            template.created_by = ids['Lucas']
        elif changed:
            setattr(template, changed, {'body': 'Texto personalizado de Lucas', 'title': 'Título de Lucas', 'severity': 'urgent'}[changed])
        db.commit()
        previous = (template.title, template.body, template.severity, template.version, template.created_by)
        sent = service.emit_notification(db, title='Antes da atualização', body='Situação atual: Entregue.', user_ids=[ids['Sol']])
        db.commit()
        service.ensure_defaults(db)
        db.commit()
        if changed:
            assert (template.title, template.body, template.severity, template.version, template.created_by) == previous
        else:
            assert template.body == service.DEFAULTS['tracking_status_changed'][2] and template.version == 2
        assert db.get(Notification, sent.id).body == 'Situação atual: Entregue.'
        assert db.query(NotificationRevision).filter_by(notification_id=sent.id).one().snapshot['body'] == 'Situação atual: Entregue.'


def test_tracking_default_upgrade_does_not_overwrite_unflushed_owner_edit(setup):
    _, factory, _ = setup
    with factory() as db:
        service.ensure_defaults(db)
        template_id = uuid.uuid5(uuid.NAMESPACE_URL, 'erp-eleven/notification-template/tracking_status_changed')
        template = db.get(NotificationTemplate, template_id)
        template.body = 'Situação atual: {status}. Abra o rastreamento para conferir.'
        db.commit()
        template.body = 'Minha edição ainda pendente {cliente_username}'
        service.ensure_defaults(db)
        assert template.body == 'Minha edição ainda pendente {cliente_username}'
        db.commit()
        service.ensure_defaults(db)
        assert template.body == 'Minha edição ainda pendente {cliente_username}' and template.version == 1
