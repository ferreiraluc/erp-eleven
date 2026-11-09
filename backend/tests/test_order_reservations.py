"""Commercial orders reserve available stock without inventing sales or payments."""
import uuid
from decimal import Decimal
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.api.endpoints import pedidos, pdv
from app.models import Usuario, Cliente, Pedido, Rastreamento
from app.models.usuario import UsuarioRole
from app.models.pedido import PedidoStatus
from app.models.pedido_reserva import PedidoItem, PedidoPayment, PedidoOperation, PedidoPaymentRefund
from app.models.pedido_tag import TagStatus, pedido_tags_association
from app.models.pedido_anexo import PedidoAnexo
from app.models.pdv import PdvCliente, PdvSale, PdvPayment, PdvSaleItem
from app.models.inventory import Item, StockMovement
from app.models.exchange_rate import ExchangeRate, CurrencyPair
from app.models.printing import PrintDevice, PrintJob, PrintSender, PrintLayout
from test_pdv_unknown_stock import TABLES as PDV_TABLES, make_item


@compiles(JSONB, 'sqlite')
def sqlite_jsonb(element, compiler, **kwargs):
    return 'JSON'

TABLES = list(dict.fromkeys([*(m.__table__ for m in PDV_TABLES), Pedido.__table__, PedidoItem.__table__,
    PedidoPayment.__table__, PedidoPaymentRefund.__table__, PedidoOperation.__table__, TagStatus.__table__, pedido_tags_association,
    PedidoAnexo.__table__, Rastreamento.__table__, PrintSender.__table__, PrintLayout.__table__, PrintDevice.__table__, PrintJob.__table__]))


def app_for(factory, uid, control):
    app = FastAPI()
    app.include_router(pedidos.router, prefix='/api/pedidos')
    app.include_router(pdv.router, prefix='/api/pdv')
    def session():
        with factory() as db:
            if control.get('before_request'):
                control['before_request'](db)
            yield db
    def user():
        with factory() as db:
            return db.get(Usuario, control.get('user_id', uid))
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = user
    return app


def seed(factory):
    with factory() as db:
        user = Usuario(nome='Lucas QA', email='lucas@eleven.com', role=UsuarioRole.ADMIN, senha_hash='unused')
        other = Usuario(nome='Sol QA', email='sol@example.test', role=UsuarioRole.VENDEDOR, sales_scope='own', senha_hash='unused')
        main = Cliente(nome='Gustavo QA', ativo=True)
        db.add_all([user, other, main]); db.flush()
        customer = PdvCliente(nome=main.nome, cadastro_cliente_id=main.id, ativo=True, saldo_fiado_gs=0)
        rate = ExchangeRate(currency_pair=CurrencyPair.USD_TO_PYG, rate=6000, source='Synthetic')
        db.add_all([customer, rate]); db.flush()
        item = make_item(db)
        db.commit()
        return user.id, customer.id, item.id, other.id


@pytest.fixture
def orders():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, autoflush=False)
    uid, cid, iid, other = seed(factory)
    control = {}
    with TestClient(app_for(factory, uid, control)) as client:
        yield factory, client, cid, iid, control, other
    engine.dispose()


def command(version=None, **fields):
    return dict(request_id=str(uuid.uuid4()), confirm=True, expected_version=version, **fields)


def body(cid, iid, qty=1, location='loja', **fields):
    return command(pdv_cliente_id=str(cid), usd_rate_gs=6000, desconto_gs=0,
                   items=[dict(item_id=str(iid), quantity=qty, location=location, unit_price_gs=60000)], **fields)


def payment(amount=30000):
    return dict(method='cash_gs', currency='GS', amount_original=amount, exchange_rate=1, amount_gs=amount)


def reserve(client, cid, iid, qty=1, **fields):
    response = client.post('/api/pedidos/reservas', json=body(cid, iid, qty, **fields))
    assert response.status_code == 201, response.text
    return response.json()


def balances(factory, iid):
    with factory() as db:
        item = db.get(Item, iid)
        return item.current_stock, item.stock_loja, item.stock_deposito, item.reserved_loja, item.reserved_deposito


def test_reserving_does_not_sell_or_reduce_physical_and_retry_is_single_effect(orders):
    factory, client, cid, iid, *_ = orders
    payload = body(cid, iid, qty=2)
    first = client.post('/api/pedidos/reservas', json=payload)
    assert first.status_code == 201, first.text
    second = client.post('/api/pedidos/reservas', json=payload)
    assert second.status_code == 201 and first.json()['id'] == second.json()['id']
    assert balances(factory, iid) == (10, 6, 4, 2, 0)
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(StockMovement).count() == 0
        assert db.query(Pedido).count() == db.query(PedidoOperation).count() == 1
    row = first.json()
    assert row['paid_gs'] == '0.00' and row['commerce_status'] == 'reserved'
    assert row['items'][0]['available_loja'] == 4
    payload['items'][0]['quantity'] = 1
    assert client.post('/api/pedidos/reservas', json=payload).status_code == 409
    assert balances(factory, iid) == (10, 6, 4, 2, 0)


def test_reservation_blocks_other_orders_and_pdv_but_not_other_location(orders):
    factory, client, cid, iid, *_ = orders
    reserved = reserve(client, cid, iid, 6)
    assert client.post('/api/pedidos/reservas', json=body(cid, iid)).status_code == 409
    sale = {'cliente_id': str(cid), 'items': [{'item_id': str(iid), 'item_name': 'Produto', 'quantity': 1, 'unit_price_gs': 60000}], 'payments': [payment(60000)]}
    assert client.post('/api/pdv/sales', json=sale).status_code == 409
    reserve(client, cid, iid, location='deposito')
    assert balances(factory, iid) == (10, 6, 4, 6, 1)
    with factory() as db:
        assert db.query(PdvSale).count() == 0


def test_edit_reserves_delta_moves_local_and_rejects_stale_revision(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 2)
    payload = body(cid, iid, 3, 'deposito'); payload['expected_version'] = 1
    response = client.put(f"/api/pedidos/{order['id']}/reserva", json=payload)
    assert response.status_code == 200, response.text
    assert balances(factory, iid) == (10, 6, 4, 0, 3)
    payload['request_id'] = str(uuid.uuid4())
    assert client.put(f"/api/pedidos/{order['id']}/reserva", json=payload).status_code == 409
    assert balances(factory, iid) == (10, 6, 4, 0, 3)


def test_deposits_and_final_sale_keep_dates_values_and_idempotency(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 2)
    url = f"/api/pedidos/{order['id']}"
    pay = command(1, payment=payment(30000))
    deposit = client.post(url + '/pagamentos', json=pay)
    assert deposit.status_code == 200, deposit.text
    assert client.post(url + '/pagamentos', json=pay).status_code == 200
    with factory() as db:
        row = db.query(PedidoPayment).one()
        row.created_at -= timedelta(days=3)
        original_date = row.created_at
        db.commit()
        db.query(ExchangeRate).update({'rate': 6100})
        db.commit()
    checkout = command(2, payments=[payment(90000)])
    sold = client.post(url + '/checkout', json=checkout)
    assert sold.status_code == 200, sold.text
    retry = client.post(url + '/checkout', json=checkout)
    assert retry.status_code == 200 and retry.json()['id'] == sold.json()['id']
    assert balances(factory, iid) == (8, 4, 4, 0, 0)
    assert Decimal(str(sold.json()['usd_rate_gs'])) == 6000
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(StockMovement).count() == 1
        deposit = db.query(PedidoPayment).filter(PedidoPayment.amount_gs == 30000).one()
        sale_payment = db.get(PdvPayment, deposit.sale_payment_id)
        assert sale_payment.amount_gs == 30000
        assert sale_payment.created_at.replace(tzinfo=None) == original_date.replace(tzinfo=None)
        assert db.get(Pedido, uuid.UUID(order['id'])).sale_id == uuid.UUID(sold.json()['id'])
    latest = client.get(url + '/reserva').json()
    assert latest['commerce_status'] == 'completed' and Decimal(latest['balance_gs']) == 0
    assert len(latest['payments']) == 2 and sum(Decimal(p['amount_gs']) for p in latest['payments']) == 120000
    assert client.post(url + '/checkout', json=command(2, payments=[payment(90000)])).status_code == 409


def test_insufficient_final_payment_rolls_back_release_and_sale(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 2)
    result = client.post(f"/api/pedidos/{order['id']}/checkout", json=command(1, payments=[payment(30000)]))
    assert result.status_code == 422, result.text
    assert balances(factory, iid) == (10, 6, 4, 2, 0)
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == db.query(StockMovement).count() == 0
        assert db.query(PedidoOperation).count() == 1


def test_cancel_requires_deposit_refund_record_and_preserves_history(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}"
    paid = client.post(url + '/pagamentos', json=command(1, payment=payment())).json()
    assert client.post(url + '/cancelar', json=command(2, reason='Cliente desistiu')).status_code == 409
    reversed_result = client.post(url + f"/pagamentos/{paid['payments'][0]['id']}/estornar",
                                 json=command(2, reason='Devolução conferida no caixa'))
    assert reversed_result.status_code == 200, reversed_result.text
    result = client.post(url + '/cancelar', json=command(3, reason='Cliente desistiu'))
    assert result.status_code == 200, result.text
    assert result.json()['commerce_status'] == 'cancelled'
    assert result.json()['payments'][0]['reversed_at']
    assert balances(factory, iid) == (10, 6, 4, 0, 0)
    with factory() as db:
        assert db.query(PedidoPayment).count() == 1 and db.query(PedidoOperation).count() == 4
        assert db.query(PdvSale).count() == db.query(StockMovement).count() == 0


def test_payments_cannot_overpay_be_fiado_or_shrink_paid_order(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}"
    for values in (payment(60001), {**payment(), 'method': 'fiado'}, payment(0)):
        assert client.post(url + '/pagamentos', json=command(1, payment=values)).status_code == 422
    assert client.post(url + '/pagamentos', json=command(1, payment=payment())).status_code == 200
    edited = body(cid, iid); edited.update(expected_version=2, desconto_gs=40000)
    assert client.put(url + '/reserva', json=edited).status_code == 409
    assert balances(factory, iid) == (10, 6, 4, 1, 0)


def test_legacy_routes_cannot_bypass_reservations_and_scope_precedes_page(orders):
    factory, client, cid, iid, control, other = orders
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}"
    assert client.put(url, json={'status': 'CANCELADO'}).status_code == 409
    assert client.put(url, json={'valor_total': 1}).status_code == 409
    assert client.delete(url).status_code == 409
    control['user_id'] = other
    assert client.get(url + '/reserva').status_code == 404
    assert client.get(url).status_code == 404
    assert client.get('/api/pedidos/pagina').json()['total'] == 0
    assert client.post(url + '/cancelar', json=command(1, reason='Outro funcionário')).status_code == 404


def test_search_reservation_by_inventory_code_and_filter_commercial_status(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid)
    with factory() as db:
        code = db.get(Item, iid).inventory_code
    found = client.get('/api/pedidos/pagina', params={'search': code, 'commerce_status': 'reserved'})
    assert found.status_code == 200, found.text
    assert found.json()['total'] == 1 and found.json()['items'][0]['id'] == order['id']
    assert client.get('/api/pedidos/pagina', params={'commerce_status': 'legacy'}).json()['total'] == 0


@pytest.mark.parametrize('changes', [
    {'quantity': 0}, {'quantity': 1.5}, {'quantity': True}, {'unit_price_gs': 'NaN'},
    {'unit_price_gs': -1}, {'location': 'elsewhere'},
])
def test_invalid_catalog_lines_never_reserve(orders, changes):
    factory, client, cid, iid, *_ = orders
    payload = body(cid, iid)
    payload['items'][0].update(changes)
    assert client.post('/api/pedidos/reservas', json=payload).status_code == 422
    assert balances(factory, iid) == (10, 6, 4, 0, 0)
