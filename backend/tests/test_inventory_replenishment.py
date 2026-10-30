"""Synthetic stock replenishment: transfer and label queue are one transaction."""
from copy import deepcopy
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import event, update

from app.api.endpoints import inventory_replenishment
from app.database import Base
from app.dependencies import get_current_active_user
from app.models.access import AuditEvent
from app.models.address_book import PrintLayout
from app.models.assistant import utcnow
from app.models.inventory import Item, StockMovement
from app.models.printing import PrintDevice, PrintJob
from app.models.usuario import Usuario, UsuarioRole
from app.services import product_labels
from app.services.product_label_layouts import default_config
from test_product_labels import label_env, tickets, pdv_app, setup_device, selection
from test_pdv_unknown_stock import make_item


URL = '/api/inventory-replenishment'
EXPECTED = ('expected_stock_loja', 'expected_stock_deposito', 'expected_current_stock')


@pytest.fixture
def replenishment_env(label_env):
    factory, client, ids, _ = label_env
    client.app.include_router(inventory_replenishment.router, prefix=URL)
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintLayout.__table__])
        for item_id, amount in zip(ids, (5, 8, 3)):
            row = db.get(Item, uuid.UUID(item_id))
            row.stock_loja = 0 if amount != 3 else 1
            row.stock_deposito = amount if amount != 3 else 2
            row.current_stock = amount
        db.commit()
    return factory, client, ids


def request_body(factory, client, ids, copies=1):
    products = {row['id']: row for row in selection(client, ids)}
    lines = []
    with factory() as db:
        for item_id in ids:
            row = products[item_id]
            stored = db.get(Item, uuid.UUID(item_id))
            lines.append(dict(item_id=item_id, code=row['inventory_code'], name=row['name'],
                size=row['size'], color=row['color'], sale_price=row['sale_price'],
                sale_currency=row['sale_currency'], copies=copies,
                expected_stock_loja=stored.stock_loja, expected_stock_deposito=stored.stock_deposito,
                expected_current_stock=stored.current_stock))
    return dict(request_key=str(uuid.uuid4()), confirm=True, items=lines)


def stock(db, item_id):
    row = db.get(Item, uuid.UUID(str(item_id)))
    return row.current_stock, row.stock_loja, row.stock_deposito


def no_writes(factory, ids, expected):
    with factory() as db:
        assert [stock(db, item_id) for item_id in ids] == expected
        assert db.query(PrintJob).count() == 0
        assert db.query(StockMovement).count() == 0
        assert db.query(AuditEvent).count() == 0


def confirm(client, body):
    response = client.post(URL + '/confirm', json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_listing_only_out_of_store_active_items_without_loading_photo_originals(replenishment_env):
    factory, client, ids = replenishment_env
    with factory() as db:
        extra = []
        for changes in ({'stock_loja': None}, {'stock_deposito': None}, {'stock_deposito': 0},
                        {'stock_loja': -1}, {'is_active': False}, {'deleted_at': utcnow()}):
            row = make_item(db, **(dict(current_stock=5, stock_loja=0, stock_deposito=5) | changes))
            extra.append(str(row.id))
        row = db.get(Item, uuid.UUID(ids[0]))
        row.image_data = 'original-photo-is-never-a-catalog-payload'
        row.additional_images = ['another-original']
        row.brand = 'Boss'
        row.location = 'Prateleira A'
        db.commit()
    statements = []
    engine = factory.kw['bind']
    def record(conn, cursor, statement, *args):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        response = client.get(URL + '/items')
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data['total'], data['page'], data['page_size']) == (2, 1, 40)
    assert {row['id'] for row in data['items']} == set(ids[:2])
    first = next(row for row in data['items'] if row['id'] == ids[0])
    assert first['brand'] == 'Boss' and first['location'] == 'Prateleira A'
    assert first['has_image'] is True and first['updated_at']
    assert first['blocked_reason'] is None
    assert 'image_data' not in first and 'additional_images' not in first
    assert 'original-photo' not in response.text and 'another-original' not in response.text
    # A SQL boolean presence check is allowed; selecting the original itself is not.
    assert not any('inventory_items.additional_images' in sql for sql in statements)
    assert not any('inventory_items.image_data AS inventory_items_image_data' in sql for sql in statements)


@pytest.mark.parametrize('total', [None, 3, -1])
def test_unknown_or_inconsistent_totals_stay_visible_but_block_confirmation(replenishment_env, total):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    with factory() as db:
        db.execute(update(Item).where(Item.id == uuid.UUID(ids[0])).values(current_stock=total))
        db.commit()
    data = client.get(URL + '/items').json()
    row = next(row for row in data['items'] if row['id'] == ids[0])
    assert row['blocked_reason'] and row['current_stock'] == total
    result = client.post(URL + '/confirm', json=body)
    assert result.status_code == 409, result.text
    no_writes(factory, ids[:1], [(total, 0, 5)])


def test_search_matches_internal_code_and_paginated_results_have_no_duplicates(replenishment_env):
    factory, client, ids = replenishment_env
    with factory() as db:
        code = db.get(Item, uuid.UUID(ids[0])).inventory_code
        for index in range(42):
            row = make_item(db, current_stock=1, stock_loja=0, stock_deposito=1)
            row.name = f'Reposição sintética {index:02}'
        db.commit()
    found = client.get(URL + '/items', params={'q': code})
    assert found.status_code == 200, found.text
    assert [row['id'] for row in found.json()['items']] == [ids[0]]
    first = client.get(URL + '/items').json()
    second = client.get(URL + '/items', params={'page': 2}).json()
    assert first['total'] == second['total'] == 44
    assert len(first['items']) == 40 and len(second['items']) == 4
    assert not ({row['id'] for row in first['items']} & {row['id'] for row in second['items']})
    assert client.get(URL + '/items', params={'page': 0}).status_code == 422
    assert client.get(URL + '/items', params={'q': 'x' * 151}).status_code == 422


def test_confirm_moves_exact_quantities_and_queues_one_label_per_piece(replenishment_env):
    factory, client, ids = replenishment_env
    device = setup_device(client)
    body = request_body(factory, client, ids[:2])
    body['items'][1]['copies'] = 3
    result = confirm(client, body)
    assert result['request_key'] == body['request_key'] and result['total'] == 4
    assert result['replenished_items'] == 2 and result['created_at']
    assert [job['copies'] for job in result['jobs']] == [1, 3]
    assert len(result['movements']) == 2
    by_item = {move['item_id']: move for move in result['movements']}
    assert (by_item[ids[0]]['quantity'], by_item[ids[0]]['stock_loja'], by_item[ids[0]]['stock_deposito']) == (1, 1, 4)
    assert (by_item[ids[1]]['quantity'], by_item[ids[1]]['stock_loja'], by_item[ids[1]]['stock_deposito']) == (3, 3, 5)
    with factory() as db:
        assert stock(db, ids[0]) == (5, 1, 4) and stock(db, ids[1]) == (8, 3, 5)
        movements = db.query(StockMovement).all()
        assert len(movements) == 2
        for movement in movements:
            assert movement.movement_type.value == 'transfer'
            assert (movement.location_from, movement.location_to) == ('deposito', 'loja')
            assert movement.reference_type == 'inventory_replenishment'
            assert movement.reference_id == result['id']
            assert movement.quantity_before == movement.quantity_after
            assert str(movement.id) == by_item[str(movement.item_id)]['id']
        jobs = db.query(PrintJob).all()
        assert len(jobs) == 2
        assert all(job.source == 'product_labels' and job.status == 'pending' for job in jobs)
        assert all(str(job.device_id) == device['device']['id'] for job in jobs)
        assert all(job.snapshot['operation'] == 'inventory_replenishment' for job in jobs)
        assert all(job.pdf == b'' for job in jobs)
    assert client.get(URL + '/items').json()['total'] == 0


def test_exact_replay_survives_product_device_and_layout_changes(replenishment_env):
    factory, client, ids = replenishment_env
    setup_device(client)
    key = 'product-' + uuid.uuid4().hex[:20]
    saved = client.put('/api/inventory-labels/layouts/' + key,
        json=dict(name='Modelo sintético', version=0, config=default_config()))
    assert saved.status_code == 200, saved.text
    body = request_body(factory, client, ids[:1], copies=2)
    body.update(layout_id=key, layout_revision=1)
    first = confirm(client, body)
    with factory() as db:
        product = db.get(Item, uuid.UUID(ids[0]))
        product.name, product.is_active = 'Produto alterado', False
        product.sale_price = Decimal('999')
        db.query(PrintDevice).filter_by(purpose='product_labels').one().active = False
        db.delete(db.get(PrintLayout, key))
        db.commit()
    replay = confirm(client, body)
    assert replay == first
    with factory() as db:
        assert stock(db, ids[0]) == (5, 2, 3)
        assert db.query(StockMovement).count() == db.query(PrintJob).count() == 1
        assert db.query(PrintJob).one().snapshot['name'] == body['items'][0]['name']
    changed = deepcopy(body)
    changed['items'][0]['copies'] = 3
    assert client.post(URL + '/confirm', json=changed).status_code == 409


@pytest.mark.parametrize('first_operation', ['replenishment', 'labels'])
def test_idempotency_key_cannot_cross_label_and_replenishment_operations(replenishment_env, first_operation):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    plain = deepcopy(body)
    for line in plain['items']:
        for field in EXPECTED:
            line.pop(field)
    if first_operation == 'replenishment':
        confirm(client, body)
        response = client.post('/api/inventory-labels/batches', json=plain)
    else:
        assert client.post('/api/inventory-labels/batches', json=plain).status_code == 200
        response = client.post(URL + '/confirm', json=body)
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.query(PrintJob).count() == 1
        assert db.query(StockMovement).count() == (1 if first_operation == 'replenishment' else 0)
        assert stock(db, ids[0]) == ((5, 1, 4) if first_operation == 'replenishment' else (5, 0, 5))


@pytest.mark.parametrize('change', [
    {'stock_loja': 1, 'stock_deposito': 4},
    {'stock_deposito': 4, 'current_stock': 4},
    {'current_stock': None}, {'stock_deposito': None},
    {'is_active': False}, {'deleted_at': utcnow()}, {'name': 'Alterado'},
])
def test_changed_second_product_rolls_back_entire_batch(replenishment_env, change):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:2])
    with factory() as db:
        db.execute(update(Item).where(Item.id == uuid.UUID(ids[1])).values(**change))
        db.commit()
        before = [stock(db, item_id) for item_id in ids[:2]]
    response = client.post(URL + '/confirm', json=body)
    assert response.status_code == 409, response.text
    no_writes(factory, ids[:2], before)


def test_second_label_render_failure_rolls_back_jobs_and_stock(replenishment_env, monkeypatch):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:2])
    original = product_labels.render_zpl
    def fail_second(snapshot):
        if snapshot['item_id'] == ids[1]:
            raise RuntimeError('Synthetic label renderer failure')
        return original(snapshot)
    monkeypatch.setattr(product_labels, 'render_zpl', fail_second)
    with pytest.raises(RuntimeError, match='Synthetic label renderer failure'):
        client.post(URL + '/confirm', json=body)
    no_writes(factory, ids[:2], [(5, 0, 5), (8, 0, 8)])


def test_offline_printer_keeps_durable_pending_queue_but_missing_printer_blocks_stock(replenishment_env):
    factory, client, ids = replenishment_env
    body = request_body(factory, client, ids[:1])
    response = client.post(URL + '/confirm', json=body)
    assert response.status_code == 409, response.text
    no_writes(factory, ids[:1], [(5, 0, 5)])
    setup_device(client)
    # No connect/claim calls: a configured but offline agent still retains its work.
    result = confirm(client, body)
    assert result['jobs'][0]['status'] == 'pending'
    with factory() as db:
        assert stock(db, ids[0]) == (5, 1, 4)
        assert db.query(PrintJob).one().status == 'pending'


@pytest.mark.parametrize('copies', [0, -1, 101, 1.5, True, '1'])
def test_quantity_must_be_bounded_positive_integer(replenishment_env, copies):
    factory, client, ids = replenishment_env
    body = request_body(factory, client, ids[:1])
    body['items'][0]['copies'] = copies
    assert client.post(URL + '/confirm', json=body).status_code == 422
    no_writes(factory, ids[:1], [(5, 0, 5)])


@pytest.mark.parametrize('field', EXPECTED)
@pytest.mark.parametrize('value', [None, True, 1.5, '0'])
def test_stock_conference_requires_explicit_integer_snapshot(replenishment_env, field, value):
    factory, client, ids = replenishment_env
    body = request_body(factory, client, ids[:1])
    body['items'][0][field] = value
    assert client.post(URL + '/confirm', json=body).status_code == 422


@pytest.mark.parametrize('field', EXPECTED)
def test_missing_stock_snapshot_is_rejected(replenishment_env, field):
    factory, client, ids = replenishment_env
    body = request_body(factory, client, ids[:1])
    body['items'][0].pop(field)
    assert client.post(URL + '/confirm', json=body).status_code == 422


def test_confirmation_and_batch_limits_are_enforced_before_writes(replenishment_env):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    assert client.post(URL + '/confirm', json={**body, 'confirm': False}).status_code == 422
    repeated = {**body, 'items': body['items'] * 2}
    assert client.post(URL + '/confirm', json=repeated).status_code == 422
    assert client.post(URL + '/confirm', json={**body, 'items': body['items'] * 101}).status_code == 422
    too_many = [{**body['items'][0], 'item_id': str(uuid.uuid4()), 'copies': 100} for _ in range(21)]
    assert client.post(URL + '/confirm', json={**body, 'items': too_many}).status_code == 422
    insufficient = deepcopy(body)
    insufficient['items'][0]['copies'] = 6
    assert client.post(URL + '/confirm', json=insufficient).status_code == 409
    no_writes(factory, ids[:1], [(5, 0, 5)])


@pytest.mark.parametrize('role', [UsuarioRole.GERENTE, UsuarioRole.VENDEDOR, UsuarioRole.LIMPEZA])
def test_authenticated_read_and_manager_only_confirmation(replenishment_env, role):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    with factory() as db:
        user = Usuario(nome='Pessoa sintética', email='fixture@example.com', role=role, senha_hash='unused')
        db.add(user)
        db.commit()
        user_id = user.id
    def current_user():
        with factory() as db:
            return db.get(Usuario, user_id)
    client.app.dependency_overrides[get_current_active_user] = current_user
    assert client.get(URL + '/items').status_code == 200
    response = client.post(URL + '/confirm', json=body)
    expected = 200 if role == UsuarioRole.GERENTE else 403
    assert response.status_code == expected, response.text
    if expected == 403:
        no_writes(factory, ids[:1], [(5, 0, 5)])


def test_unauthenticated_requests_never_disclose_products_or_transfer(replenishment_env):
    factory, client, ids = replenishment_env
    body = request_body(factory, client, ids[:1])
    client.app.dependency_overrides.pop(get_current_active_user)
    assert client.get(URL + '/items').status_code == 401
    assert client.post(URL + '/confirm', json=body).status_code == 401
    no_writes(factory, ids[:1], [(5, 0, 5)])


@pytest.mark.parametrize('field', ['sale_price', 'sale_currency'])
@pytest.mark.parametrize('missing', [True, False])
def test_label_price_and_currency_must_be_reviewed(replenishment_env, field, missing):
    factory, client, ids = replenishment_env
    body = request_body(factory, client, ids[:1])
    if missing:
        body['items'][0].pop(field)
    else:
        body['items'][0][field] = None
    assert client.post(URL + '/confirm', json=body).status_code == 422
    no_writes(factory, ids[:1], [(5, 0, 5)])


def enable_request_audit(factory, client):
    from app.database import get_db
    from app.services.user_audit import bind_actor
    def audited_session():
        with factory() as db:
            db.info['audit_enabled'] = True
            user = db.query(Usuario).filter_by(email='lucas@eleven.com').one()
            bind_actor(db, user, route=URL + '/confirm', method='POST')
            yield db
    client.app.dependency_overrides[get_db] = audited_session


def test_audit_commits_stock_and_print_together_without_photo_or_snapshot_content(replenishment_env):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    enable_request_audit(factory, client)
    result = confirm(client, body)
    with factory() as db:
        logs = db.query(AuditEvent).all()
        assert {'stock_movements', 'inventory_items', 'print_jobs'} <= {log.entity for log in logs}
        changed = next(log for log in logs if log.entity == 'inventory_items')
        assert changed.changes['stock_loja'] == {'before': 0, 'after': 1}
        assert changed.changes['stock_deposito'] == {'before': 5, 'after': 4}
        assert all('snapshot' not in log.changes and 'image_data' not in log.changes for log in logs)
        count = len(logs)
    assert confirm(client, body) == result
    with factory() as db:
        assert db.query(AuditEvent).count() == count


def test_failure_after_first_movement_rolls_back_stock_print_and_audit(replenishment_env, monkeypatch):
    from app.services import inventory_replenishment as replenishment
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:2])
    enable_request_audit(factory, client)
    original = replenishment.create_movement
    calls = []
    def fail_after_first(*args, **kwargs):
        calls.append(args[1])
        if len(calls) == 2:
            raise RuntimeError('Synthetic second movement failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(replenishment, 'create_movement', fail_after_first)
    with pytest.raises(RuntimeError, match='Synthetic second movement failure'):
        client.post(URL + '/confirm', json=body)
    assert len(calls) == 2
    no_writes(factory, ids[:2], [(5, 0, 5), (8, 0, 8)])


def test_replay_returns_original_stock_snapshot_after_a_later_stock_change(replenishment_env):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    original = confirm(client, body)
    with factory() as db:
        row = db.get(Item, uuid.UUID(ids[0]))
        row.stock_loja, row.stock_deposito = 3, 2
        db.commit()
    assert confirm(client, body) == original
    with factory() as db:
        assert stock(db, ids[0]) == (5, 3, 2)
        assert db.query(StockMovement).count() == db.query(PrintJob).count() == 1


def test_manager_cannot_reuse_another_users_confirmation_key(replenishment_env):
    factory, client, ids = replenishment_env
    setup_device(client)
    body = request_body(factory, client, ids[:1])
    confirm(client, body)
    with factory() as db:
        manager = Usuario(nome='Gerente sintético', email='manager@example.com',
                          role=UsuarioRole.GERENTE, senha_hash='unused')
        db.add(manager)
        db.commit()
        manager_id = manager.id
    def current_manager():
        with factory() as db:
            return db.get(Usuario, manager_id)
    client.app.dependency_overrides[get_current_active_user] = current_manager
    assert client.post(URL + '/confirm', json=body).status_code == 409
    with factory() as db:
        assert stock(db, ids[0]) == (5, 1, 4)
        assert db.query(StockMovement).count() == db.query(PrintJob).count() == 1
