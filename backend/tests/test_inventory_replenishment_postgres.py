"""Replenishment races use disposable localhost PostgreSQL, never a real printer."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic, sleep
import uuid

import pytest
import sqlalchemy as sa

from app.api.endpoints import inventory_labels, inventory_replenishment, printing
from app.database import Base
from app.models.inventory import Item, StockMovement
from app.models.printing import PrintJob
from test_access_postgres import pg
from test_pdv_stock_postgres import pdv_pg, item, preload_barrier, post_two
from test_inventory_replenishment import URL, request_body, setup_device, stock


@pytest.fixture
def replenishment_pg(pdv_pg):
    factory, client, _, control, observer = pdv_pg
    with factory() as db:
        Base.metadata.create_all(db.get_bind())
    client.app.include_router(printing.router, prefix='/api/printing')
    client.app.include_router(inventory_labels.router, prefix='/api/inventory-labels')
    client.app.include_router(inventory_replenishment.router, prefix=URL)
    setup_device(client)
    return factory, client, control, observer


@pytest.mark.parametrize('same_key', [True, False])
def test_concurrent_confirmation_moves_and_enqueues_only_once(replenishment_pg, same_key):
    factory, client, control, _ = replenishment_pg
    uid = item(factory, loja=0, deposito=5)
    body = request_body(factory, client, [str(uid)], copies=2)
    other = deepcopy(body)
    if not same_key:
        other['request_key'] = str(uuid.uuid4())
    # Both request sessions already hold the old stock in the identity map.
    preload_barrier(control, [uid], [(5, 0, 5)])
    responses = post_two(client, [URL + '/confirm'] * 2, [body, other])
    control.clear()
    expected = [200, 200] if same_key else [200, 409]
    assert sorted(response.status_code for response in responses) == expected, [r.text for r in responses]
    result = next(response.json() for response in responses if response.status_code == 200)
    if same_key:
        assert responses[0].json() == responses[1].json()
    with factory() as db:
        assert stock(db, uid) == (5, 2, 3)
        movement = db.query(StockMovement).one()
        assert movement.quantity == 2 and movement.reference_id == result['id']
        assert movement.movement_type.value == 'transfer'
        job = db.query(PrintJob).one()
        assert job.source == 'product_labels' and job.snapshot['copies'] == 2
        assert job.snapshot['operation'] == 'inventory_replenishment'


def test_reversed_item_order_cannot_deadlock_or_partially_replenish(replenishment_pg):
    factory, client, control, _ = replenishment_pg
    a, b = item(factory, loja=0, deposito=6), item(factory, loja=0, deposito=8)
    first = request_body(factory, client, [str(a), str(b)], copies=3)
    second = request_body(factory, client, [str(b), str(a)], copies=2)
    preload_barrier(control, [a, b], [(6, 0, 6), (8, 0, 8)])
    responses = post_two(client, [URL + '/confirm'] * 2, [first, second])
    control.clear()
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    winner = next(r.json() for r in responses if r.status_code == 200)
    quantity = winner['jobs'][0]['copies']
    with factory() as db:
        assert stock(db, a) == (6, quantity, 6 - quantity)
        assert stock(db, b) == (8, quantity, 8 - quantity)
        assert db.query(StockMovement).count() == 2 and db.query(PrintJob).count() == 2
        assert {r.reference_id for r in db.query(StockMovement)} == {winner['id']}


def test_simultaneous_plain_label_and_replenishment_do_not_share_confirmation(replenishment_pg):
    factory, client, control, _ = replenishment_pg
    uid = item(factory, loja=0, deposito=5)
    body = request_body(factory, client, [str(uid)])
    plain = deepcopy(body)
    for field in ('expected_stock_loja', 'expected_stock_deposito', 'expected_current_stock'):
        plain['items'][0].pop(field)
    preload_barrier(control, [uid], [(5, 0, 5)])
    responses = post_two(client, [URL + '/confirm', '/api/inventory-labels/batches'], [body, plain])
    control.clear()
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    moved = responses[0].status_code == 200
    with factory() as db:
        assert db.query(PrintJob).count() == 1
        assert db.query(StockMovement).count() == int(moved)
        assert stock(db, uid) == ((5, 1, 4) if moved else (5, 0, 5))


@pytest.mark.parametrize('change', [
    {'stock_loja': 1, 'stock_deposito': 4},
    {'current_stock': 4, 'stock_deposito': 4},
    {'current_stock': None},
    {'is_active': False},
])
def test_confirm_waits_for_item_lock_and_rechecks_changed_stock(replenishment_pg, change):
    factory, client, control, observer = replenishment_pg
    uid = item(factory, loja=0, deposito=5)
    body = request_body(factory, client, [str(uid)])
    reader_ready = Queue()
    writer_ready = Event()
    def preload(db):
        row = db.get(Item, uid)
        assert stock(db, uid) == (5, 0, 5)
        db.info['held_preloaded_rows'] = [row]
        reader_ready.put(db.scalar(sa.text('SELECT pg_backend_pid()')))
        assert writer_ready.wait(timeout=10)
    control['before_request'] = preload
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(client.post, URL + '/confirm', json=body)
        reader_pid = reader_ready.get(timeout=10)
        with factory() as writer:
            product = writer.query(Item).filter_by(id=uid).with_for_update().one()
            for field, value in change.items():
                setattr(product, field, value)
            writer.flush()
            writer_ready.set()
            deadline, blocked = monotonic() + 5, False
            with observer.connect() as connection:
                while monotonic() < deadline:
                    blocked = bool(connection.scalar(sa.text('SELECT pg_blocking_pids(:pid)'), {'pid': reader_pid}))
                    if blocked:
                        break
                    sleep(.01)
            assert blocked, 'Replenishment must wait for the current product transaction'
            writer.commit()
        response = future.result(timeout=15)
    control.clear()
    assert response.status_code == 409, response.text
    with factory() as db:
        assert stock(db, uid) == (change.get('current_stock', 5), change.get('stock_loja', 0),
                                  change.get('stock_deposito', 5))
        assert db.query(StockMovement).count() == db.query(PrintJob).count() == 0
