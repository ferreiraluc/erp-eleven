"""Order holds protect the same physical stock used by every stock writer."""
import uuid

import pytest

from test_assistant import setup
from test_inventory_ocr import stock_app, item
from test_inventory_deletion import deletion_app, confirm
from test_inventory_replenishment import replenishment_env, request_body, setup_device
from test_product_labels import label_env, tickets, pdv_app
from app.models.inventory import Item, StockMovement
from app.services.inventory_service import create_movement, StockMovementError


@pytest.mark.parametrize('kind,quantity,location,extra', [
    ('exit', 2, 'loja', {}),
    ('transfer', 2, 'loja', {'location_from': 'loja', 'location_to': 'deposito'}),
    ('adjustment', 1, 'loja', {}),
    ('exit', 5, 'deposito', {}),
    ('transfer', 5, 'deposito', {'location_from': 'deposito', 'location_to': 'loja'}),
    ('adjustment', 2, 'deposito', {}),
])
def test_every_stock_writer_preserves_order_holds(stock_app, kind, quantity, location, extra):
    factory, _, uid = stock_app
    with factory() as db:
        row = item(db, reserved_loja=2, reserved_deposito=3)
        identity = row.id
        db.commit()
        with pytest.raises(StockMovementError, match='reservad'):
            create_movement(db, identity, kind, quantity, uid, location=location, **extra)
        db.rollback()
        row = db.get(Item, identity)
        assert (row.current_stock, row.stock_loja, row.stock_deposito) == (10, 3, 7)
        assert (row.reserved_loja, row.reserved_deposito) == (2, 3)
        assert db.query(StockMovement).count() == 0


def test_only_available_stock_can_leave_and_releasing_hold_does_not_move_stock(stock_app):
    factory, client, uid = stock_app
    with factory() as db:
        row = item(db, reserved_loja=2, reserved_deposito=3)
        identity = row.id
        db.commit()
        create_movement(db, identity, 'exit', 1, uid, location='loja')
        db.commit()
        assert (row.stock_loja, row.reserved_loja, row.available_loja) == (2, 2, 0)
        row.reserved_loja = 0
        db.flush()
        create_movement(db, identity, 'exit', 2, uid, location='loja')
        db.commit()
        assert (row.current_stock, row.stock_loja, row.stock_deposito) == (7, 0, 7)
    result = client.get('/api/inventory/items').json()['items'][0]
    assert (result['stock_deposito'], result['reserved_deposito'], result['available_deposito']) == (7, 3, 4)
    assert result['available_stock'] == 4


def test_unknown_physical_stock_remains_unknown_with_reservations(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        row = item(db, reserved_loja=1)
        row.stock_loja = None
        row.current_stock = None
        db.commit()
    result = client.get('/api/inventory/items').json()['items'][0]
    assert result['stock_loja'] is None and result['available_loja'] is None
    assert result['current_stock'] is None and result['available_stock'] is None
    assert result['reserved_loja'] == 1


def test_reservations_block_inactivation_and_both_deletion_modes(deletion_app):
    factory, client, _, identity = deletion_app
    with factory() as db:
        db.get(Item, uuid.UUID(identity)).reserved_loja = 1
        db.commit()
    preview, body = confirm(client, identity)
    assert {'code': 'order_reservations', 'count': 1} in preview['blockers']
    assert not preview['allowed']
    assert preview['preserve_history_token'] is None
    assert client.delete(f'/api/inventory/items/{identity}').status_code == 409
    assert client.put(f'/api/inventory/items/{identity}', json={'is_active': False}).status_code == 409
    assert client.patch('/api/inventory/items/batch', json={'item_ids': [identity], 'is_active': False}).status_code == 409
    body['plan_token'] = '0' * 64  # bypassing the disabled UI must still fail on the backend
    assert client.post(f'/api/inventory/items/{identity}/delete-from-catalog', json=body).status_code == 409
    assert client.request('DELETE', f'/api/inventory/items/{identity}/permanent', json=body).status_code == 409
    with factory() as db:
        row = db.get(Item, uuid.UUID(identity))
        assert row.is_active and row.deleted_at is None and row.reserved_loja == 1


@pytest.mark.parametrize('state', ['completed', 'cancelled'])
def test_closed_order_history_blocks_permanent_deletion_but_allows_catalog_removal(deletion_app, state):
    from app.models.pedido import Pedido
    from app.models.pedido_reserva import PedidoItem
    factory, client, uid, identity = deletion_app
    with factory() as db:
        order = Pedido(numero_pedido=f'HISTORY-{state}', descricao='Separado', valor_total=100,
                       commerce_status=state, vendedor_id=uid)
        db.add(order); db.flush()
        line = PedidoItem(pedido_id=order.id, item_id=uuid.UUID(identity), item_name='Camiseta',
                          location='loja', quantity=1, unit_price_gs=100, total_gs=100)
        db.add(line); db.commit()
    preview, body = confirm(client, identity)
    assert {'code': 'orders', 'count': 1} in preview['blockers']
    assert not preview['allowed'] and preview['preserve_history_token']
    body['plan_token'] = preview['preserve_history_token']
    assert client.request('DELETE', f'/api/inventory/items/{identity}/permanent', json=body).status_code == 409
    assert client.post(f'/api/inventory/items/{identity}/delete-from-catalog', json=body).status_code == 200
    with factory() as db:
        assert db.query(PedidoItem).count() == 1
        assert db.get(Item, uuid.UUID(identity)).deleted_at


def test_replenishment_excludes_reserved_depot_units_and_rechecks_on_confirmation(replenishment_env):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1], copies=3)
    with factory() as db:
        db.get(Item, uuid.UUID(ids[0])).reserved_deposito = 4
        db.get(Item, uuid.UUID(ids[1])).reserved_deposito = 8
        db.commit()
    rows = client.get('/api/inventory-replenishment/items').json()['items']
    assert [row['id'] for row in rows] == ids[:1]
    assert rows[0]['stock_deposito'] == 5 and rows[0]['available_deposito'] == 1
    assert client.post('/api/inventory-replenishment/confirm', json=body).status_code == 409
    with factory() as db:
        assert db.query(StockMovement).count() == 0
        row = db.get(Item, uuid.UUID(ids[0]))
        assert (row.stock_loja, row.stock_deposito, row.reserved_deposito) == (0, 5, 4)
