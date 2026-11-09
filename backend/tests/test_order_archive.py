"""Reviewed directory archival never releases reservations or erases history."""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import pedidos_archive
from app.database import Base
from app.models import Pedido, Usuario, Rastreamento
from app.models.access import AuditEvent
from app.models.pedido_archive import PedidoArchiveOperation
from app.models.pedido_reserva import PedidoPayment
from app.models.pedido_anexo import PedidoAnexo
from app.models.inventory import StockMovement
from app.models.pdv import PdvSale, PdvPayment
from app.services import order_archive
from test_order_reservations import TABLES, app_for, seed, reserve, balances, command, payment

ARCHIVE_TABLES = [*TABLES, PedidoArchiveOperation.__table__]


@pytest.fixture
def archive_app():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=ARCHIVE_TABLES)
    factory = sessionmaker(bind=engine, autoflush=False)
    uid, cid, iid, other = seed(factory)
    control = {}
    app = app_for(factory, uid, control)
    app.include_router(pedidos_archive.router, prefix='/api/pedidos')
    with TestClient(app) as client:
        yield factory, client, uid, cid, iid, other, control
    engine.dispose()


def add_order(factory, uid, **fields):
    with factory() as db:
        row = Pedido(numero_pedido='QA-' + uuid.uuid4().hex[:12], descricao='Historical fixture',
                     valor_total=10, moeda='U$', cliente_nome='Cliente sintético', created_by=uid, **fields)
        db.add(row); db.commit()
        return row.id


def archive_payload(client):
    response = client.get('/api/pedidos/arquivo/preview')
    assert response.status_code == 200, response.text
    preview = response.json()
    return dict(request_id=str(uuid.uuid4()), confirm=True, plan_token=preview['plan_token'], expected_count=preview['total'])


def test_archive_hides_only_directory_preserves_records_and_durable_retry(archive_app):
    factory, client, uid, _, iid, _, _ = archive_app
    ids = [add_order(factory, uid, commerce_status=state, paid_gs=paid)
           for state, paid in [(None, None), ('completed', 100), ('cancelled', 0), ('returned', 0)]]
    before = balances(factory, iid)
    payload = archive_payload(client)
    response = client.post('/api/pedidos/arquivo/confirm', json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['archived_count'] == 4 and result['history_preserved'] and result['remaining_count'] == 0
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).json() == result
    assert client.get('/api/pedidos/pagina').json()['total'] == 0
    assert client.get('/api/pedidos/').json() == []
    for listing in ('archived', 'all'):
        listed = client.get('/api/pedidos/pagina', params={'listing': listing}).json()
        assert listed['total'] == 4 and all(row['archived_at'] for row in listed['items'])
        assert len(client.get('/api/pedidos/', params={'listing': listing}).json()) == 4
    for ident in ids:
        assert client.get(f'/api/pedidos/{ident}').status_code == 200
    assert client.delete(f'/api/pedidos/{ids[0]}').status_code == 409
    assert balances(factory, iid) == before
    with factory() as db:
        assert db.query(Pedido).count() == 4
        assert db.query(PedidoArchiveOperation).count() == 1
        assert db.query(PdvSale).count() == db.query(PedidoPayment).count() == db.query(StockMovement).count() == 0
        assert db.query(AuditEvent).filter_by(action='orders_archived').count() == 1
        assert all(db.get(Pedido, ident).archived_by == uid for ident in ids)
    new_id = add_order(factory, uid)
    assert client.get('/api/pedidos/pagina').json()['items'][0]['id'] == str(new_id)
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).json() == result
    assert client.get('/api/pedidos/pagina').json()['total'] == 1


@pytest.mark.parametrize('state,paid', [('reserved', 0), ('conditional', 0), ('conditional', 100), ('cancelled', 1), ('returned', 1)])
def test_active_or_unsettled_orders_block_entire_batch(archive_app, state, paid):
    factory, client, uid, *_ = archive_app
    old_id = add_order(factory, uid)
    add_order(factory, uid, commerce_status=state, paid_gs=paid)
    preview = client.get('/api/pedidos/arquivo/preview').json()
    assert not preview['allowed'] and preview['blocked_count'] == 1 and preview['eligible_count'] == 1
    response = client.post('/api/pedidos/arquivo/confirm', json=archive_payload(client))
    assert response.status_code == 409
    with factory() as db:
        assert db.get(Pedido, old_id).archived_at is None
        assert db.query(PedidoArchiveOperation).count() == 0


def test_archival_cannot_release_a_real_reserved_balance(archive_app):
    factory, client, _, cid, iid, *_ = archive_app
    row = reserve(client, cid, iid, qty=2)
    before = balances(factory, iid)
    assert client.post('/api/pedidos/arquivo/confirm', json=archive_payload(client)).status_code == 409
    assert balances(factory, iid) == before == (10, 6, 4, 2, 0)
    assert client.get(f'/api/pedidos/{row["id"]}/reserva').json()['commerce_status'] == 'reserved'


def test_completed_sale_payments_tracking_and_attachments_remain_linked(archive_app):
    factory, client, uid, cid, iid, *_ = archive_app
    order = reserve(client, cid, iid, qty=2)
    oid = uuid.UUID(order['id'])
    url = f'/api/pedidos/{oid}'
    assert client.post(url + '/pagamentos', json=command(1, payment=payment(30000))).status_code == 200
    sold = client.post(url + '/checkout', json=command(2, payments=[payment(90000)]))
    assert sold.status_code == 200, sold.text
    with factory() as db:
        row = db.get(Pedido, oid)
        customer_id, sale_id = row.cliente_id, row.sale_id
        shipment = Rastreamento(codigo_rastreio='QA' + uuid.uuid4().hex, pedido_id=oid, cliente_id=customer_id)
        attachment = PedidoAnexo(pedido_id=oid, nome_arquivo='fixture.png', tipo_arquivo='image/png', tamanho=1, dados='AA==', created_by=uid)
        db.add_all([shipment, attachment]); db.commit()
        sid, aid = shipment.id, attachment.id
        payment_ids = set(db.query(PedidoPayment.id).all())
        sale_payment_ids = set(db.query(PdvPayment.id).all())
    before = balances(factory, iid)
    assert client.post('/api/pedidos/arquivo/confirm', json=archive_payload(client)).status_code == 200
    with factory() as db:
        row = db.get(Pedido, oid)
        assert (row.cliente_id, row.sale_id, row.commerce_status) == (customer_id, sale_id, 'completed')
        assert db.get(Rastreamento, sid).pedido_id == db.get(PedidoAnexo, aid).pedido_id == oid
        assert set(db.query(PedidoPayment.id).all()) == payment_ids
        assert set(db.query(PdvPayment.id).all()) == sale_payment_ids
        assert db.query(PdvSale).count() == db.query(StockMovement).count() == 1
    assert balances(factory, iid) == before


def test_preview_changes_confirmation_and_request_identity_are_checked(archive_app):
    factory, client, uid, *_ = archive_app
    ident = add_order(factory, uid)
    payload = archive_payload(client)
    assert client.post('/api/pedidos/arquivo/confirm', json={**payload, 'confirm': False}).status_code == 422
    with factory() as db:
        db.get(Pedido, ident).descricao = 'Changed since review'; db.commit()
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).status_code == 409
    assert client.get('/api/pedidos/pagina').json()['total'] == 1
    payload = archive_payload(client)
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).status_code == 200
    assert client.post('/api/pedidos/arquivo/confirm', json={**payload, 'expected_count': 99}).status_code == 409


def test_new_order_invalidates_preview_and_vendor_cannot_archive_or_expand_scope(archive_app):
    factory, client, uid, _, _, other, control = archive_app
    add_order(factory, uid, commerce_status='completed', vendedor_id=uid)
    payload = archive_payload(client)
    own_id = add_order(factory, uid, commerce_status='completed', vendedor_id=other)
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).status_code == 409
    payload = archive_payload(client)
    control['user_id'] = other
    assert client.get('/api/pedidos/arquivo/preview').status_code == 403
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).status_code == 403
    control['user_id'] = uid
    assert client.post('/api/pedidos/arquivo/confirm', json=payload).status_code == 200
    control['user_id'] = other
    for listing in ('archived', 'all'):
        page = client.get('/api/pedidos/pagina', params={'listing': listing}).json()
        assert page['total'] == 1 and page['items'][0]['id'] == str(own_id)


def test_unknown_state_fails_closed():
    from types import SimpleNamespace
    assert order_archive._blocked(SimpleNamespace(commerce_status='future_status', paid_gs=Decimal(0)))
