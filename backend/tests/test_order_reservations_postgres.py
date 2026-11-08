"""Reservation migration, real row locks and retry races on disposable PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from test_access_postgres import pg, upgrade
from test_order_reservations import TABLES, app_for, seed, body, command, payment, reserve, balances
from app.database import Base
from app.models.inventory import Item, StockMovement
from app.models.pedido import Pedido
from app.models.pedido_reserva import PedidoItem, PedidoPayment, PedidoOperation
from app.models.pdv import PdvSale, PdvPayment


def test_migration_preserves_legacy_orders_stock_and_payments(pg):
    engine, schema = pg
    item_id, order_id, payment_id = [uuid.uuid4() for _ in range(3)]
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        for name in ('usuarios', 'clientes', 'pdv_clientes', 'pdv_sales', 'cambistas'):
            conn.exec_driver_sql(f'CREATE TABLE {name} (id uuid PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE inventory_items (id uuid PRIMARY KEY, current_stock integer, stock_loja integer, stock_deposito integer)')
        conn.exec_driver_sql('CREATE TABLE pedidos (id uuid PRIMARY KEY, descricao text, valor_total numeric(10,2))')
        conn.exec_driver_sql('CREATE TABLE pdv_payments (id uuid PRIMARY KEY, amount_gs numeric(15,2))')
        conn.execute(sa.text('INSERT INTO inventory_items VALUES(:id,10,6,4)'), {'id': item_id})
        conn.execute(sa.text("INSERT INTO pedidos VALUES(:id,'Legacy order',99)"), {'id': order_id})
        conn.execute(sa.text('INSERT INTO pdv_payments VALUES(:id,99)'), {'id': payment_id})
        upgrade(conn, 'z8i9j0k1l2m3_order_reservations.py')
        assert conn.exec_driver_sql('SELECT current_stock,stock_loja,stock_deposito,reserved_loja,reserved_deposito FROM inventory_items').one() == (10,6,4,0,0)
        assert conn.exec_driver_sql('SELECT descricao,valor_total,commerce_status,sale_id FROM pedidos').one() == ('Legacy order',99,None,None)
        assert conn.exec_driver_sql('SELECT amount_gs FROM pdv_payments').scalar() == 99
        assert set(('pedido_items', 'pedido_payments', 'pedido_operations')) <= set(sa.inspect(conn).get_table_names(schema=schema))
        fks = sa.inspect(conn).get_foreign_keys('pedido_payments', schema=schema)
        assert next(fk for fk in fks if fk['constrained_columns'] == ['sale_payment_id'])['options']['ondelete'] == 'SET NULL'
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.exec_driver_sql('UPDATE inventory_items SET reserved_loja = -1')


@pytest.fixture
def orders_pg(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema} -clock_timeout=8000 -cstatement_timeout=15000'})
    Base.metadata.create_all(isolated, tables=TABLES)
    factory = sessionmaker(bind=isolated, autoflush=False)
    uid, cid, iid, other = seed(factory)
    control = {}
    with TestClient(app_for(factory, uid, control)) as client:
        yield factory, client, cid, iid, control, other
    isolated.dispose()


def race(client, requests, control):
    barrier = Barrier(len(requests))
    control['before_request'] = lambda db: barrier.wait(timeout=10)
    try:
        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            tasks = [pool.submit(client.request, method, path, json=body) for method, path, body in requests]
            return [task.result(timeout=25) for task in tasks]
    finally:
        control.clear()


def test_concurrent_reservations_cannot_both_take_last_unit(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    with factory() as db:
        item = db.get(Item, iid)
        item.stock_loja, item.stock_deposito, item.current_stock = 1, 0, 1
        db.commit()
    responses = race(client, [('POST', '/api/pedidos/reservas', body(cid, iid)) for _ in range(2)], control)
    assert sorted(r.status_code for r in responses) == [201,409], [r.text for r in responses]
    assert balances(factory, iid) == (1,1,0,1,0)
    with factory() as db:
        assert db.query(Pedido).count() == db.query(PedidoItem).count() == 1


def test_lost_create_response_parallel_retries_return_same_order(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    payload = body(cid, iid)
    responses = race(client, [('POST', '/api/pedidos/reservas', payload)] * 2, control)
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    assert len({r.json()['id'] for r in responses}) == 1
    assert balances(factory, iid) == (10,6,4,1,0)


def test_parallel_deposit_retry_is_single_payment(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    order = reserve(client, cid, iid)
    payload = command(1, payment=payment(30000))
    responses = race(client, [('POST', f"/api/pedidos/{order['id']}/pagamentos", payload)] * 2, control)
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    with factory() as db:
        assert db.query(PedidoPayment).count() == 1
        assert db.get(Pedido, uuid.UUID(order['id'])).paid_gs == 30000


def test_two_checkouts_and_lost_response_never_double_sell(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    order = reserve(client, cid, iid)
    url = f"/api/pedidos/{order['id']}/checkout"
    payload = command(1, payments=[payment(60000)])
    responses = race(client, [('POST', url, payload)] * 2, control)
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert len({r.json()['id'] for r in responses}) == 1
    assert balances(factory, iid) == (9,5,4,0,0)
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == db.query(StockMovement).count() == 1
        assert db.query(PedidoPayment).count() == 1
    assert client.post(url, json=command(1, payments=[payment(60000)])).status_code == 409


def test_reserved_stock_competes_atomically_with_regular_sale(orders_pg):
    factory, client, cid, iid, control, _ = orders_pg
    with factory() as db:
        item = db.get(Item, iid)
        item.stock_loja, item.stock_deposito, item.current_stock = 1,0,1
        db.commit()
    sale = {'cliente_id': str(cid), 'items': [{'item_id': str(iid), 'item_name': 'Test', 'quantity': 1, 'unit_price_gs': 60000}], 'payments': [payment(60000)]}
    responses = race(client, [('POST', '/api/pedidos/reservas', body(cid,iid)), ('POST', '/api/pdv/sales', sale)], control)
    assert sorted(r.status_code for r in responses) == [201,409], [r.text for r in responses]
    with factory() as db:
        item = db.get(Item,iid)
        assert (item.stock_loja, item.reserved_loja) in {(0, 0), (1, 1)}
        assert db.query(Pedido).count() + db.query(PdvSale).count() == 1


def test_owner_can_correct_completed_sale_without_deleting_order_payment_history(orders_pg):
    from test_pdv_management import apply, command as sale_command
    factory, client, cid, iid, *_ = orders_pg
    order = reserve(client, cid, iid)
    sale = client.post(f"/api/pedidos/{order['id']}/checkout", json=command(1, payments=[payment(60000)])).json()
    correction = dict(cliente_id=str(cid), notas='Correção conferida', items=[{
        'item_id': str(iid), 'item_name': 'Produto sintético', 'quantity': 1, 'unit_price_gs': 60000,
    }], payments=[payment(60000)])
    apply(client, sale['id'], sale_command('edit', edit=correction))
    with factory() as db:
        deposit = db.query(PedidoPayment).one()
        assert deposit.amount_gs == 60000 and deposit.sale_payment_id is None
        assert db.get(Pedido, uuid.UUID(order['id'])).sale_id == uuid.UUID(sale['id'])
        assert db.query(PdvSale).one().notas == 'Correção conferida'
        assert db.query(PdvPayment).one().amount_gs == 60000
