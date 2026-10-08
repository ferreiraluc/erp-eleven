import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg
from test_inventory_variants import source, pg_variants
from app.models.inventory import Item, StockMovement
from app.schemas.inventory_duplicate import DuplicateItemRequest
from app.services import inventory_duplicate as service
from app.services.inventory_variants import variant_context


def draft(client, source_id, **changes):
    context = client.get(f'/api/inventory/items/{source_id}/variants').json()
    item = {key: value for key, value in context['source'].items() if key in DuplicateItemRequest.model_fields['item'].annotation.model_fields}
    item.update(size='8', name='Tênis Branco 8', group_key=None)
    item.update(changes)
    return dict(request_id=str(uuid.uuid4()), source_version=context['source_version'], item=item, confirm=True, initial_stock=2, stock_location='deposito')


def test_full_edited_copy_and_retry_preserve_original_and_do_not_repeat_stock(manager_stock_app):
    factory, client, user_id = manager_stock_app
    source_id = source(factory, user_id)
    payload = draft(client, source_id, name='Modelo diferente', size='P', brand='Outra marca', color='Azul', category='Camisetas', description='Nova descrição', image_data='data:image/png;base64,edited', barcode='CUSTOM', sale_price=80, sale_currency='EUR', unit='par', min_stock=2, max_stock=20)
    payload['keep_group'] = False
    url = f'/api/inventory/items/{source_id}/duplicate'
    first = client.post(url, json=payload)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['image_data'] == payload['item']['image_data'] and result['name'] == 'Modelo diferente'
    assert result['group_key'] is None and result['sale_currency'] == 'EUR'
    assert result['id'] != str(source_id)
    retry = client.post(url, json=payload)
    assert retry.status_code == 201 and retry.json()['id'] == result['id']
    payload['item']['name'] = 'Changed after confirmation'
    assert client.post(url, json=payload).status_code == 409
    with factory() as db:
        old = db.get(Item, source_id)
        assert old.name == 'Tênis Branco 9' and old.image_data == 'data:image/png;base64,fixture'
        assert old.current_stock == 7 and old.group_key is None
        assert db.query(Item).count() == 2 and db.query(StockMovement).count() == 1


def test_only_size_change_keeps_shared_data_groups_source_and_rejects_duplicate_variant(manager_stock_app):
    factory, client, user_id = manager_stock_app
    source_id = source(factory, user_id)
    data = draft(client, source_id)
    response = client.post(f'/api/inventory/items/{source_id}/duplicate', json=data)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['image_data'] == data['item']['image_data'] and result['barcode'] == data['item']['barcode']
    assert result['stock_deposito'] == 2 and result['group_key']
    data['request_id'] = str(uuid.uuid4())
    assert client.post(f'/api/inventory/items/{source_id}/duplicate', json=data).status_code == 409
    with factory() as db:
        assert db.get(Item, source_id).group_key == result['group_key']
        assert db.query(StockMovement).count() == 1


@pytest.mark.parametrize('change', [{'current_stock': 99}, {'sku_internal': 'arbitrary'}, {'id': str(uuid.uuid4())}, {'sale_price': -1}, {'name': '  '}, {'group_key': 'unrelated'}])
def test_rejects_identity_stock_injection_and_invalid_fields(manager_stock_app, change):
    factory, client, user_id = manager_stock_app
    source_id = source(factory, user_id); data = draft(client, source_id, **change)
    assert client.post(f'/api/inventory/items/{source_id}/duplicate', json=data).status_code == 422
    with factory() as db: assert db.query(Item).count() == 1


def test_confirmation_permission_and_source_version_required(manager_stock_app):
    factory, client, user_id = manager_stock_app
    source_id = source(factory, user_id); data = draft(client, source_id)
    data['confirm'] = False
    assert client.post(f'/api/inventory/items/{source_id}/duplicate', json=data).status_code == 422
    data['confirm'] = True
    with factory() as db: db.get(Item, source_id).brand = 'Changed'; db.commit()
    assert client.post(f'/api/inventory/items/{source_id}/duplicate', json=data).status_code == 409


def test_unauthorized_role(stock_app):
    factory, client, user_id = stock_app
    source_id = source(factory, user_id)
    data = dict(request_id=str(uuid.uuid4()), source_version='a'*64, item={'name': 'Test'}, confirm=True)
    assert client.post(f'/api/inventory/items/{source_id}/duplicate', json=data).status_code == 403


def test_pg_repeated_concurrent_request_creates_single_item_and_entry(pg_variants):
    factory, user_id = pg_variants; source_id = source(factory, user_id)
    with factory() as db: version = variant_context(db, source_id)['source_version']
    data = DuplicateItemRequest(request_id=uuid.uuid4(), source_version=version, item={'name': 'Copy', 'size': '8'}, confirm=True, initial_stock=3)
    barrier = Barrier(2)
    def duplicate(_):
        with factory() as db:
            barrier.wait(timeout=10)
            return service.duplicate_item(db, source_id, data, user_id).id
    with ThreadPoolExecutor(max_workers=2) as pool: assert len(set(pool.map(duplicate, [1, 2]))) == 1
    with factory() as db:
        assert db.query(Item).count() == 2 and db.query(StockMovement).count() == 1


def test_pg_failure_rolls_back_item_and_group(pg_variants, monkeypatch):
    factory, user_id = pg_variants; source_id = source(factory, user_id)
    def fail(*args, **kwargs): raise RuntimeError('injected')
    monkeypatch.setattr(service, 'create_movement', fail)
    with factory() as db:
        data = DuplicateItemRequest(request_id=uuid.uuid4(), source_version=variant_context(db, source_id)['source_version'], item={'name': 'Copy', 'size': '8'}, confirm=True, initial_stock=3)
        with pytest.raises(RuntimeError): service.duplicate_item(db, source_id, data, user_id)
    with factory() as db:
        assert db.get(Item, source_id).group_key is None
        assert db.query(Item).count() == 1 and db.query(StockMovement).count() == 0
