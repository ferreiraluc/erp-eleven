"""Audited partial refunds survive sale revisions without relaxing new payments."""
from decimal import Decimal
import uuid
import pytest

from test_order_reservations import orders, body, command, balances
from test_order_reservations_postgres import orders_pg
from test_access_postgres import pg
from test_order_conditionals import deliver, returned
from test_pdv_management import apply, edit_body, command as sale_command
from app.models.pdv import PdvPayment, PdvSale, PdvSaleEvent
from app.models.pedido_reserva import PedidoPayment, PedidoPaymentRefund


@pytest.mark.parametrize('storage', ['orders', 'orders_pg'])
def test_two_owner_edits_preserve_exact_net_deposit_and_reject_changed_fx(request, storage):
    factory, client, cid, iid, *_ = request.getfixturevalue(storage)
    payload = body(cid, iid, qty=2)
    payload['items'][0]['unit_price_gs'] = '60031.00'
    order = client.post('/api/pedidos/reservas', json=payload).json()
    url = f"/api/pedidos/{order['id']}"
    pay = dict(method='cash_usd', currency='USD', amount_original=20, exchange_rate=6000, amount_gs=120000)
    paid = client.post(url + '/pagamentos', json=command(1, payment=pay)).json()
    order = returned(client, deliver(client, paid), 1)
    pid = order['payments'][0]['id']
    response = client.post(url + f'/pagamentos/{pid}/estornar', json=command(
        4, reason='USD devolvidos com arredondamento de centavos', amount_gs=59969))
    assert response.status_code == 200, response.text
    sold = client.post(url + '/checkout', json=command(5, payments=[]))
    assert sold.status_code == 200, sold.text
    sid = sold.json()['id']
    original_balances = balances(factory, iid)

    for revision in range(2):
        detail = client.get('/api/pdv/management/' + sid).json()
        edit = edit_body(detail)
        edit['notas'] = f'Conferência {revision + 1}'
        apply(client, sid, sale_command('edit', edit=edit))
        # Simulate PostgreSQL ON DELETE SET NULL on SQLite too, proving that a
        # second edit does not rely on the original (now replaced) payment ID.
        with factory() as db:
            deposit = db.get(PedidoPayment, uuid.UUID(pid))
            if db.bind.dialect.name == 'sqlite':
                deposit.sale_payment_id = None
                db.commit()
            assert deposit.sale_payment_id is None
            payment = db.query(PdvPayment).one()
            assert (payment.amount_original, payment.exchange_rate, payment.amount_gs) == (Decimal('10.01'), 6000, 60031)
            assert db.query(PedidoPaymentRefund).one().amount_gs == 59969
        assert balances(factory, iid) == original_balances

    detail = client.get('/api/pdv/management/' + sid).json()
    edit = edit_body(detail)
    edit['payments'][0]['amount_original'] = '10.02'
    rejected = client.post(f'/api/pdv/management/{sid}/preview', json=sale_command('edit', edit=edit))
    assert rejected.status_code == 422
    with factory() as db:
        assert db.query(PdvSaleEvent).count() == 2
        assert db.query(PdvPayment).one().amount_original == Decimal('10.01')

    apply(client, sid, sale_command('return', lines=[dict(
        line_id=detail['items'][0]['id'], quantity=1, restock=True)]))
    assert balances(factory, iid) == (10, 6, 4, 0, 0)
    with factory() as db:
        assert db.get(PdvSale, uuid.UUID(sid)).refunded_gs == 60031
