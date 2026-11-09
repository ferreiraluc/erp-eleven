"""Real PostgreSQL constraints and concurrency for conditional deliveries."""
from decimal import Decimal
import uuid
import pytest
import sqlalchemy as sa
from test_access_postgres import pg, upgrade
from test_order_reservations_postgres import orders_pg, race
from test_order_reservations import reserve, command, payment, balances
from test_order_conditionals import deliver
from app.models.inventory import StockMovement
from app.models.pedido_reserva import PedidoPaymentRefund
from app.models.pdv import PdvSale


def test_conditional_migration_keeps_original_order_and_payment_values(pg):
    engine, schema = pg
    oid, uid, pid, iid = [uuid.uuid4() for _ in range(4)]
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE usuarios (id uuid PRIMARY KEY)')
        conn.exec_driver_sql("CREATE TABLE pedidos (id uuid PRIMARY KEY, commerce_status varchar(20), total_gs numeric(15,2), CONSTRAINT ck_pedidos_commerce_status CHECK (commerce_status IS NULL OR commerce_status IN ('reserved','completed','cancelled')))")
        conn.exec_driver_sql('CREATE TABLE pedido_items (id uuid PRIMARY KEY, quantity integer NOT NULL)')
        conn.exec_driver_sql('CREATE TABLE pedido_payments (id uuid PRIMARY KEY, amount_gs numeric(15,2))')
        conn.execute(sa.text("INSERT INTO pedidos VALUES(:id,'reserved',120000)"), {'id': oid})
        conn.execute(sa.text('INSERT INTO pedido_items VALUES(:id,2)'), {'id': iid})
        conn.execute(sa.text('INSERT INTO pedido_payments VALUES(:id,30000)'), {'id': pid})
        conn.execute(sa.text('INSERT INTO usuarios VALUES(:id)'), {'id': uid})
        upgrade(conn, 'a9j0k1l2m3n4_order_conditionals.py')
        assert conn.exec_driver_sql('SELECT commerce_status,total_gs,delivered_at FROM pedidos').one() == ('reserved',120000,None)
        assert conn.exec_driver_sql('SELECT quantity,returned_quantity FROM pedido_items').one() == (2,0)
        assert conn.exec_driver_sql('SELECT amount_gs FROM pedido_payments').scalar() == 30000
        conn.exec_driver_sql("UPDATE pedidos SET commerce_status='conditional'")
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.exec_driver_sql('UPDATE pedido_items SET returned_quantity=3')


def test_concurrent_dispatch_retry_never_double_withdraws(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    order = reserve(client, cid, iid, 2)
    request = ('POST', f"/api/pedidos/{order['id']}/condicional", command(1))
    responses = race(client, [request, request], control)
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert balances(factory, iid) == (8,4,4,0,0)
    with factory() as db:
        assert db.query(StockMovement).count() == 1
        assert db.query(PdvSale).count() == 0


def test_return_and_settlement_race_cannot_double_move_stock(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    order = deliver(client, reserve(client, cid, iid, 2))
    url = f"/api/pedidos/{order['id']}"
    requests = [
        ('POST', url + '/checkout', command(2, payments=[payment(120000)])),
        ('POST', url + '/devolver-itens', command(2, reason='Uma peça devolvida',
            lines=[dict(line_id=order['items'][0]['id'], quantity=1)])),
    ]
    responses = race(client, requests, control)
    assert sorted(r.status_code for r in responses) == [200,409], [r.text for r in responses]
    with factory() as db:
        if responses[0].status_code == 200:
            assert db.query(PdvSale).count() == 1 and db.query(StockMovement).count() == 1
            assert balances(factory, iid) == (8,4,4,0,0)
        else:
            assert db.query(PdvSale).count() == 0 and db.query(StockMovement).count() == 2
            assert balances(factory, iid) == (9,5,4,0,0)


def test_partial_refund_concurrent_retry_is_single_money_event(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    order = reserve(client, cid, iid, 2)
    url = f"/api/pedidos/{order['id']}"
    paid = client.post(url + '/pagamentos', json=command(1, payment=payment(100000))).json()
    order = deliver(client, paid)
    payload = command(3, reason='Dinheiro devolvido', amount_gs=40000)
    request = ('POST', url + f"/pagamentos/{order['payments'][0]['id']}/estornar", payload)
    responses = race(client, [request, request], control)
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    with factory() as db:
        assert db.query(PedidoPaymentRefund).one().amount_gs == Decimal(40000)
