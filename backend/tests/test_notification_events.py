"""Business notices follow the real transaction, never historical reads or printing."""
from datetime import timedelta
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.notification import Notification, NotificationRecipient, NotificationRule
from app.models.cliente import Cliente
from app.models.pedido import Pedido
from app.models.pdv import PdvSale, PdvSaleItem
from app.models.printing import PrintDevice, PrintJob
from app.models.rastreamento import Rastreamento, RastreamentoStatus
from app.services import notification_events  # register transactional listeners
from app.services import notifications
from test_access_postgres import pg
from test_notifications import MODELS
from test_pdv_unknown_stock import pdv_app, make_item, sale_payload


@pytest.fixture
def factory(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated)
    value = sessionmaker(bind=isolated, autoflush=False, expire_on_commit=False,
                         info={'notification_events': True})
    with value() as db:
        for name in ('Lucas', 'Sol', 'Other'):
            db.add(Usuario(id=uuid.uuid4(), nome=name, email=f'{name.lower()}@eleven.com',
                           senha_hash='unused', role=UsuarioRole.ADMIN if name == 'Lucas' else UsuarioRole.GERENTE,
                           sales_scope='all' if name == 'Lucas' else 'own', ativo=True))
        db.commit()
    try:
        yield value
    finally:
        isolated.dispose()


def users(db):
    return {user.nome: user.id for user in db.query(Usuario).all()}


def sale(db, *, reason=None, avulso=True):
    ids = users(db)
    row = PdvSale(id=uuid.uuid4(), vendedor_id=ids['Sol'], status='completed', notas=reason,
                  total_gs=100, subtotal_gs=100)
    db.add(row)
    db.flush()
    db.add(PdvSaleItem(sale_id=row.id, item_name='Synthetic fixture', is_avulso=avulso,
                      quantity=1, unit_price_gs=100, total_gs=100))
    return row


def test_new_sale_reaches_owner_and_unexplained_avulso_only_its_seller(factory):
    with factory() as db:
        ids = users(db)
        row = sale(db)
        # API flushes before financial processing; notices wait until the outer commit.
        db.flush()
        assert db.query(Notification).count() == 0
        db.commit()
        notices = {notice.dedupe_key: notice for notice in db.query(Notification).all()}
        assert set(notices) == {f'sale-completed:{row.id}', f'sale-avulso:{row.id}'}
        completed = notices[f'sale-completed:{row.id}']
        review = notices[f'sale-avulso:{row.id}']
        assert review.requires_ack and review.requires_response
        assert {r.user_id for r in db.query(NotificationRecipient).filter_by(notification_id=completed.id)} == {ids['Lucas']}
        assert {r.user_id for r in db.query(NotificationRecipient).filter_by(notification_id=review.id)} == {ids['Lucas'], ids['Sol']}
        assert review.action_path == f'/vendas-pdv?sale_id={row.id}'
        # Reading, re-committing or subsequently editing a historical sale cannot replay it.
        row.notas = 'Context supplied later'
        db.commit()
        assert db.query(Notification).count() == 2


@pytest.mark.parametrize('reason,avulso', [('Legitimate manual sale', True), (None, False)])
def test_explained_or_inventory_sale_has_no_missing_context_alert(factory, reason, avulso):
    with factory() as db:
        sale(db, reason=reason, avulso=avulso)
        db.commit()
        assert db.query(Notification).count() == 1


def test_rollback_and_rolled_back_savepoint_never_publish_ghost_sales(factory):
    with factory() as db:
        sale(db)
        db.flush()
        db.rollback()
        assert notification_events.PENDING_KEY not in db.info
        with db.begin_nested() as nested:
            ghost = sale(db)
            db.flush()
            nested.rollback()
        kept = sale(db, avulso=False)
        db.commit()
        assert db.get(PdvSale, ghost.id) is None
        assert [notice.dedupe_key for notice in db.query(Notification)] == [f'sale-completed:{kept.id}']


def test_disabled_rule_and_cancelled_in_same_transaction_do_not_notify(factory):
    with factory() as db:
        notifications.ensure_defaults(db)
        db.get(NotificationRule, 'sale_completed').enabled = False
        db.commit()
        row = sale(db, avulso=False)
        db.commit()
        row2 = sale(db)
        row2.status = 'cancelled'
        db.commit()
        assert row.id != row2.id and db.query(Notification).count() == 0


def test_tracking_known_transition_only_with_final_status_and_rollback(factory):
    with factory() as db:
        ids = users(db)
        row = Rastreamento(codigo_rastreio='FIXTURE123BR', status=RastreamentoStatus.PENDENTE, created_by=ids['Sol'])
        db.add(row)
        db.commit()
        assert db.query(Notification).count() == 0
        row.status = RastreamentoStatus.EM_TRANSITO
        db.flush()
        row.status = RastreamentoStatus.ENTREGUE
        db.commit()
        notice = db.query(Notification).one()
        assert 'Entregue' in notice.body and 'FIXTURE123BR' in notice.title
        assert {r.user_id for r in db.query(NotificationRecipient)} == {ids['Lucas'], ids['Sol']}
        row.status = RastreamentoStatus.ERRO
        db.flush()
        db.rollback()
        row = db.get(Rastreamento, row.id)
        row.status = RastreamentoStatus.ERRO
        db.flush()
        row.status = RastreamentoStatus.ENTREGUE
        db.commit()
        assert db.query(Notification).count() == 1


@pytest.mark.parametrize('snapshot_name,order_name,expected', [
    ('Destinatário do pacote', 'Nome posterior no pedido', 'Destinatário do pacote'),
    (None, 'Nome histórico do pedido', 'Nome histórico do pedido'),
    (None, None, 'Cliente vinculado'),
])
def test_tracking_recipient_variable_is_real_and_transactional_in_postgresql(factory, snapshot_name, order_name, expected):
    with factory() as db:
        ids = users(db)
        customer = Cliente(nome='Cliente vinculado', cpf=None)
        db.add(customer)
        db.flush()
        order = Pedido(numero_pedido=uuid.uuid4().hex, descricao='Local fixture only', valor_total=1,
            cliente_nome=order_name, cliente_id=customer.id)
        db.add(order)
        db.flush()
        row = Rastreamento(codigo_rastreio='FIXTURE-CLIENTE-' + uuid.uuid4().hex[:10],
            destinatario=snapshot_name, pedido_id=order.id, created_by=ids['Sol'], status=RastreamentoStatus.PENDENTE)
        db.add(row)
        db.commit()
        row.status = RastreamentoStatus.ENTREGUE
        db.commit()
        notice = db.query(Notification).one()
        assert f'Destinatário: {expected}.' in notice.body and 'Entregue' in notice.body
        assert '{cliente_username}' not in notice.body and '00000000000' not in notice.body
        assert {receipt.user_id for receipt in db.query(NotificationRecipient)} == {ids['Lucas'], ids['Sol']}
        assert notice.entity_type == 'tracking' and notice.entity_id == str(row.id)
        # A retry never adopts a changed recipient or adds another delivery.
        previous = notice.body
        customer.nome = 'Nome alterado depois'
        row.destinatario = 'Outro nome posterior'
        db.commit()
        retried = notifications.emit_event(db, 'tracking_status_changed',
            context={'cliente_username': 'Outro nome posterior', 'tracking_code': row.codigo_rastreio, 'status': 'Entregue'},
            user_ids=[ids['Lucas'], ids['Sol']], dedupe_key=notice.dedupe_key,
            action_path=notice.action_path, entity_type='tracking', entity_id=str(row.id))
        db.commit()
        assert retried.id == notice.id and retried.body == previous and db.query(Notification).count() == 1


def test_receipt_problem_is_context_only_and_cannot_reprint(factory):
    with factory() as db:
        ids = users(db)
        row = sale(db, avulso=False)
        device = PrintDevice(name='Synthetic only', token_hash=uuid.uuid4().hex)
        db.add(device)
        db.flush()
        job = PrintJob(device_id=device.id, user_id=ids['Sol'], request_key=uuid.uuid4(), source='pdv_receipt',
                       snapshot={'sale_id': str(row.id)}, pdf=b'fixture-never-print', sha256='0' * 64,
                       status='pending', expires_at=notifications.utcnow() + timedelta(hours=1))
        db.add(job)
        db.commit()
        job.status = 'uncertain'
        db.commit()
        assert db.query(PrintJob).count() == 1 and job.status == 'uncertain'
        notice = db.query(Notification).filter(Notification.dedupe_key.like('receipt-problem:%')).one()
        assert {r.user_id for r in db.query(NotificationRecipient).filter_by(notification_id=notice.id)} == {ids['Lucas'], ids['Sol']}
        assert 'incerto' in notice.body.lower()


def test_pdv_api_creates_notices_only_after_successful_operation(pdv_app):
    factory, client, customer_id = pdv_app
    Base.metadata.create_all(factory.kw['bind'], tables=[model.__table__ for model in MODELS])
    factory.configure(info={'notification_events': True})
    with factory() as db:
        healthy = make_item(db)
        broken = make_item(db, current_stock=None)
        item_ids = healthy.id, broken.id
        db.commit()
    response = client.post('/api/pdv/sales', json=sale_payload(item_ids, customer_id))
    assert response.status_code == 409
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(Notification).count() == 0
    response = client.post('/api/pdv/sales', json=sale_payload([item_ids[0]], customer_id))
    assert response.status_code == 201, response.text
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(Notification).count() == 1


def test_new_tracking_event_with_same_status_notifies_once_with_recipient(factory):
    with factory() as db:
        ids=users(db)
        row=Rastreamento(codigo_rastreio='AA123456789BR',status=RastreamentoStatus.EM_TRANSITO,
            destinatario='Destinatário sintético',created_by=ids['Sol'],
            historico_eventos=[{'situacao':'Objeto postado','data':'28/10/2026 08:00'}])
        db.add(row); db.commit()
        assert db.query(Notification).count()==0
        row.historico_eventos=[{'situacao':'Objeto saiu para entrega','data':'28/10/2026 12:00'}]
        db.commit()
        notice=db.query(Notification).one()
        assert 'Destinatário sintético' in notice.body and 'Objeto saiu para entrega' in notice.body
        from app.config import settings
        row.ultima_atualizacao=settings.now(); db.commit()
        assert db.query(Notification).count()==1
        row.historico_eventos=[{'situacao':'Em outra unidade','data':'28/10/2026 13:00'}]
        db.flush(); db.rollback()
        assert db.query(Notification).count()==1
