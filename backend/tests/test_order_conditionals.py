"""Delivered conditionals preserve physical stock, actual deposits and sale identity."""
from decimal import Decimal
import uuid

from test_order_reservations import orders, reserve, command, payment, balances, body
from app.models.pedido import Pedido
from app.models.pedido_reserva import PedidoPayment, PedidoPaymentRefund, PedidoOperation
from app.models.pdv import PdvSale, PdvPayment, PdvSaleItem
from app.models.inventory import StockMovement


def deliver(client, order):
    response = client.post(f"/api/pedidos/{order['id']}/condicional", json=command(order['commerce_version']))
    assert response.status_code == 200, response.text
    return response.json()


def returned(client, order, quantity, **fields):
    response = client.post(f"/api/pedidos/{order['id']}/devolver-itens", json=command(
        order['commerce_version'], reason='Peças conferidas e recebidas',
        lines=[dict(line_id=order['items'][0]['id'], quantity=quantity)], **fields))
    assert response.status_code == 200, response.text
    return response.json()


def test_dispatch_with_no_payment_is_not_sale_and_retry_cannot_double_exit(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 3)
    payload = command(1)
    url = f"/api/pedidos/{order['id']}/condicional"
    first = client.post(url, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()['commerce_status'] == 'conditional'
    assert first.json()['delivered_at'] and first.json()['delivered_total_gs'] == '180000.00'
    assert first.json()['balance_gs'] == '180000.00'
    assert client.post(url, json=payload).status_code == 200
    assert client.post(url, json=command(1)).status_code == 409
    assert balances(factory, iid) == (7, 3, 4, 0, 0)
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == 0
        movement = db.query(StockMovement).one()
        assert movement.reason == 'order_conditional_out' and movement.quantity == 3


def test_partial_return_replenishes_original_depot_once_and_sale_skips_second_exit(orders):
    factory, client, cid, iid, *_ = orders
    order = deliver(client, reserve(client, cid, iid, 3, location='deposito'))
    assert balances(factory, iid) == (7, 6, 1, 0, 0)
    payload = command(2, reason='Devolução conferida', lines=[dict(line_id=order['items'][0]['id'], quantity=1)])
    url = f"/api/pedidos/{order['id']}"
    response = client.post(url + '/devolver-itens', json=payload)
    assert response.status_code == 200, response.text
    assert client.post(url + '/devolver-itens', json=payload).status_code == 200
    latest = response.json()
    assert latest['items'][0]['quantity'] == 3
    assert latest['items'][0]['returned_quantity'] == 1
    assert latest['items'][0]['remaining_quantity'] == 2
    assert latest['total_gs'] == '120000.00'
    assert balances(factory, iid) == (8, 6, 2, 0, 0)
    payload = command(3, payments=[payment(120000)])
    sold = client.post(url + '/checkout', json=payload)
    assert sold.status_code == 200, sold.text
    assert client.post(url + '/checkout', json=payload).json()['id'] == sold.json()['id']
    assert balances(factory, iid) == (8, 6, 2, 0, 0)
    with factory() as db:
        assert db.query(PdvSale).one().stock_applied is True
        assert db.query(PdvSaleItem).one().quantity == 2
        assert db.query(StockMovement).count() == 2


def test_all_returned_unpaid_closes_without_sale_or_fake_payment(orders):
    factory, client, cid, iid, *_ = orders
    order = returned(client, deliver(client, reserve(client, cid, iid, 2)), 2)
    assert order['commerce_status'] == 'returned'
    assert Decimal(order['total_gs']) == Decimal(order['balance_gs']) == 0
    assert balances(factory, iid) == (10, 6, 4, 0, 0)
    assert client.post(f"/api/pedidos/{order['id']}/checkout", json=command(3, payments=[])).status_code == 409
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == 0


def test_receiving_pieces_never_blocked_by_refund_due_and_partial_refund_is_immutable(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 2)
    url = f"/api/pedidos/{order['id']}"
    paid = client.post(url + '/pagamentos', json=command(1, payment=payment(100000))).json()
    order = returned(client, deliver(client, paid), 1)
    assert order['refund_due_gs'] == '40000.00'
    assert order['total_gs'] == '60000.00'
    assert client.post(url + '/checkout', json=command(4, payments=[])).status_code == 409
    pid = order['payments'][0]['id']
    payload = command(4, reason='Devolvido em dinheiro ao cliente', amount_gs=40000)
    preview = client.post(url + f'/pagamentos/{pid}/estorno-previa', json=payload)
    assert preview.status_code == 200 and preview.json()['amount_original'] == '40000.00'
    with factory() as db:
        assert db.query(PedidoPaymentRefund).count() == 0
    refund = client.post(url + f'/pagamentos/{pid}/estornar', json=payload)
    assert refund.status_code == 200, refund.text
    assert client.post(url + f'/pagamentos/{pid}/estornar', json=payload).status_code == 200
    assert refund.json()['payments'][0]['amount_gs'] == '100000.00'
    assert refund.json()['payments'][0]['remaining_gs'] == '60000.00'
    assert refund.json()['refund_due_gs'] == '0.00'
    sold = client.post(url + '/checkout', json=command(5, payments=[]))
    assert sold.status_code == 200, sold.text
    with factory() as db:
        assert db.query(PedidoPaymentRefund).one().amount_gs == 40000
        assert db.query(PedidoPayment).one().amount_gs == 100000
        assert db.query(PdvPayment).one().amount_gs == 60000
        assert db.query(PdvSale).one().total_gs == 60000
        assert db.query(StockMovement).count() == 2


def test_all_returned_paid_remains_pending_until_money_returned(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}"
    paid = client.post(url + '/pagamentos', json=command(1, payment=payment(60000))).json()
    order = returned(client, deliver(client, paid), 1)
    assert order['commerce_status'] == 'conditional' and order['refund_due_gs'] == '60000.00'
    result = client.post(url + f"/pagamentos/{order['payments'][0]['id']}/estornar",
                         json=command(4, reason='Dinheiro devolvido integralmente'))
    assert result.status_code == 200, result.text
    assert result.json()['commerce_status'] == 'returned'
    with factory() as db:
        assert db.query(PdvSale).count() == 0
    assert balances(factory, iid) == (10, 6, 4, 0, 0)


def test_delivered_order_cannot_edit_cancel_or_return_more_than_outstanding(orders):
    factory, client, cid, iid, *_ = orders
    order = deliver(client, reserve(client, cid, iid, 2))
    url = f"/api/pedidos/{order['id']}"
    edit = body(cid, iid); edit['expected_version'] = 2
    assert client.put(url + '/reserva', json=edit).status_code == 409
    assert client.post(url + '/cancelar', json=command(2, reason='Cancelamento inválido')).status_code == 409
    for quantity in (3, 0, -1, 0.5):
        response = client.post(url + '/devolver-itens', json=command(2, reason='Devolução inválida',
            lines=[dict(line_id=order['items'][0]['id'], quantity=quantity)]))
        assert response.status_code in (409, 422), response.text
    response = client.post(url + '/devolver-itens', json=command(2, reason='Outra linha',
        lines=[dict(line_id=str(uuid.uuid4()), quantity=1)]))
    assert response.status_code == 422
    assert balances(factory, iid) == (8, 4, 4, 0, 0)


def test_conditional_actions_preserve_personal_seller_scope(orders):
    factory, client, cid, iid, control, other = orders
    order = reserve(client, cid, iid)
    control['user_id'] = other
    assert client.post(f"/api/pedidos/{order['id']}/condicional", json=command(1)).status_code == 404
    assert balances(factory, iid) == (10, 6, 4, 1, 0)


def test_discount_return_allocation_is_identical_for_incremental_and_combined_returns(orders):
    factory, client, cid, iid, *_ = orders
    results = []
    for split in (True, False):
        payload = body(cid, iid, qty=3)
        payload['desconto_gs'] = '10000.01'
        response = client.post('/api/pedidos/reservas', json=payload)
        assert response.status_code == 201, response.text
        order = deliver(client, response.json())
        if split:
            order = returned(client, returned(client, order, 1), 1)
        else:
            order = returned(client, order, 2)
        results.append((order['total_gs'], order['desconto_gs']))
        returned(client, order, 1)
    assert results[0] == results[1] == ('56666.66', '3333.34')


def test_partial_foreign_deposit_refund_keeps_frozen_rate_and_actual_original_amount(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 2)
    url = f"/api/pedidos/{order['id']}"
    pay = dict(method='cash_usd', currency='USD', amount_original=20, exchange_rate=6000, amount_gs=120000)
    paid = client.post(url + '/pagamentos', json=command(1, payment=pay)).json()
    order = returned(client, deliver(client, paid), 1)
    pid = order['payments'][0]['id']
    # A real refund amount can require rounding the original currency to cents.
    response = client.post(url + f'/pagamentos/{pid}/estornar', json=command(4, reason='USD devolvidos', amount_gs=60000))
    assert response.status_code == 200, response.text
    assert response.json()['payments'][0]['remaining_original'] == '10.00'
    response = client.post(url + '/checkout', json=command(5, payments=[]))
    assert response.status_code == 200, response.text
    with factory() as db:
        assert db.query(PdvPayment).one().exchange_rate == 6000
        assert db.query(PdvPayment).one().amount_original == 10


def test_partial_card_refund_preview_includes_fee_and_final_sale_keeps_net_values(orders):
    factory, client, cid, iid, *_ = orders
    order = reserve(client, cid, iid, 2)
    url = f"/api/pedidos/{order['id']}"
    pay = dict(method='card_credit_py', currency='GS', amount_original=127660, exchange_rate=1,
               amount_gs=120000, card_fee_gs=7660, card_fee_percent=6)
    paid_response = client.post(url + '/pagamentos', json=command(1, payment=pay))
    assert paid_response.status_code == 200, paid_response.text
    order = returned(client, deliver(client, paid_response.json()), 1)
    pid = order['payments'][0]['id']; payload = command(4, reason='Estorno confirmado na máquina', amount_gs=60000)
    preview = client.post(url + f'/pagamentos/{pid}/estorno-previa', json=payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()['amount_original'] == '63830.00'
    assert preview.json()['card_fee_gs'] == '3830.00'
    assert client.post(url + f'/pagamentos/{pid}/estornar', json=payload).status_code == 200
    response = client.post(url + '/checkout', json=command(5, payments=[]))
    assert response.status_code == 200, response.text
    with factory() as db:
        row = db.query(PdvPayment).one()
        assert (row.amount_gs, row.amount_original, row.card_fee_gs, row.card_fee_percent) == (60000,63830,3830,6)


def test_outstanding_conditional_blocks_catalog_deletion(orders):
    from app.database import Base
    from app.models.inventory import InventorySession, InventorySessionItem
    from app.models.usuario import Usuario
    from app.services.inventory_deletion import deletion_preview
    factory, client, cid, iid, *_ = orders
    order = deliver(client, reserve(client, cid, iid))
    Base.metadata.create_all(factory.kw['bind'], tables=[InventorySession.__table__, InventorySessionItem.__table__])
    with factory() as db:
        owner = db.query(Usuario).filter_by(email='lucas@eleven.com').one()
        preview = deletion_preview(db, iid, owner)
        assert preview['preserve_history_token'] is None
        assert {'code': 'conditional_pieces', 'count': 1} in preview['blockers']
    returned(client, order, 1)
    with factory() as db:
        preview = deletion_preview(db, iid, db.query(Usuario).filter_by(email='lucas@eleven.com').one())
        assert preview['preserve_history_token'] is not None


def test_settled_conditional_subsequent_sale_return_restocks_only_kept_pieces(orders):
    from test_pdv_management import apply, command as sale_command
    factory, client, cid, iid, *_ = orders
    order = returned(client, deliver(client, reserve(client, cid, iid, 3)), 1)
    sale = client.post(f"/api/pedidos/{order['id']}/checkout", json=command(3, payments=[payment(120000)]))
    assert sale.status_code == 200, sale.text
    sid = sale.json()['id']
    snapshot = client.get('/api/pdv/management/' + sid).json()
    apply(client, sid, sale_command('return', lines=[dict(line_id=snapshot['items'][0]['id'], quantity=2, restock=True)]))
    assert balances(factory, iid) == (10, 6, 4, 0, 0)
    with factory() as db:
        assert db.query(PdvSaleItem).one().returned_quantity == 2
        assert db.query(StockMovement).count() == 3


def test_foreign_refund_cent_rounding_does_not_change_frozen_currency_or_block_checkout(orders):
    factory, client, cid, iid, *_ = orders
    payload = body(cid, iid, qty=2)
    payload['items'][0]['unit_price_gs'] = '60031.00'
    order = client.post('/api/pedidos/reservas', json=payload).json()
    url = f"/api/pedidos/{order['id']}"
    pay = dict(method='cash_usd', currency='USD', amount_original=20, exchange_rate=6000, amount_gs=120000)
    paid = client.post(url + '/pagamentos', json=command(1, payment=pay)).json()
    order = returned(client, deliver(client, paid), 1)
    assert order['refund_due_gs'] == '59969.00'
    pid = order['payments'][0]['id']
    refund = client.post(url + f'/pagamentos/{pid}/estornar', json=command(4, reason='Valor devolvido em USD', amount_gs=59969))
    assert refund.status_code == 200, refund.text
    sold = client.post(url + '/checkout', json=command(5, payments=[]))
    assert sold.status_code == 200, sold.text
    with factory() as db:
        p = db.query(PdvPayment).one()
        assert (p.amount_original, p.exchange_rate, p.amount_gs) == (Decimal('10.01'),6000,60031)


def test_listing_conditional_summary_tracks_remaining_pieces(orders):
    _, client, cid, iid, *_ = orders
    order = returned(client, deliver(client, reserve(client, cid, iid, 3)), 1)
    response = client.get('/api/pedidos/pagina?commerce_status=conditional')
    assert response.status_code == 200, response.text
    row = response.json()['items'][0]
    assert row['remaining_quantity'] == 2 and row['vendedor_nome'] == 'Lucas QA'
    assert row['delivered_at']
