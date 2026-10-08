import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier, StockMovement
from app.services import inventory_variants as service
from app.schemas.inventory_variants import VariantCreateRequest


def source(factory, user_id, **values):
    with factory() as db:
        item = Item(name='Tênis Branco 9', size='9', color='Branco', brand='Marca',
                    sku_internal=uuid.uuid4().hex, barcode='123459', image_data='data:image/png;base64,fixture',
                    current_stock=7, stock_loja=5, stock_deposito=2, cost_price=20, sale_price=40,
                    cost_currency='BRL', sale_currency='USD', created_by=user_id, **values)
        db.add(item); db.commit()
        return item.id


def payload(client, item_id, **values):
    response = client.get(f'/api/inventory/items/{item_id}/variants')
    assert response.status_code == 200, response.text
    context = response.json()
    return dict(sizes=['8'], model_name=context['model_name'], source_version=context['source_version'], confirm=True, **values)


def test_copy_photo_shared_data_new_identity_and_retry_without_double_stock(manager_stock_app):
    factory, client, user_id = manager_stock_app
    item_id = source(factory, user_id)
    data = payload(client, item_id, initial_stock=2, stock_location='deposito', base_barcode='12345')
    url = f'/api/inventory/items/{item_id}/variants'
    response = client.post(url, json=data)
    assert response.status_code == 201, response.text
    created = response.json()['created']
    assert len(created) == 1 and created[0]['size'] == '8' and created[0]['barcode'] == '123458'
    retry = client.post(url, json=data)
    assert retry.status_code == 201, retry.text
    assert retry.json()['created'] == [] and retry.json()['existing'][0]['id'] == created[0]['id']
    with factory() as db:
        original = db.get(Item, item_id); copy = db.get(Item, uuid.UUID(created[0]['id']))
        assert original.group_key == copy.group_key
        assert copy.name == 'Tênis Branco 8' and copy.sku_internal != original.sku_internal
        for field in service.COPY_FIELDS:
            assert getattr(copy, field) == getattr(original, field)
        assert (copy.current_stock, copy.stock_loja, copy.stock_deposito) == (2, 0, 2)
        assert (original.current_stock, original.stock_loja, original.stock_deposito) == (7, 5, 2)
        assert db.query(StockMovement).count() == 1


def test_grade_ignores_existing_sizes_and_unrelated_same_barcode(manager_stock_app):
    factory, client, user_id = manager_stock_app
    item_id = source(factory, user_id, group_key='explicit')
    source(factory, user_id)  # Same name/barcode is a different model, not a group identity.
    with factory() as db:
        db.add(Item(name='Inactive size', size='8', color=' branco ', is_active=False, group_key='explicit', sku_internal='inactive'))
        db.commit()
    data = payload(client, item_id)
    data['sizes'] = ['8', '9', '10', ' 10 ', '11']
    response = client.post(f'/api/inventory/items/{item_id}/variants', json=data)
    assert response.status_code == 201, response.text
    assert [r['size'] for r in response.json()['created']] == ['10', '11']
    assert {r['size'] for r in response.json()['existing']} == {'8', '9'}
    with factory() as db:
        rows = db.query(Item).filter(Item.size.in_(['10', '11'])).all()
        assert all(row.barcode is None and row.current_stock == 0 for row in rows)
        assert db.query(StockMovement).count() == 0


@pytest.mark.parametrize('change', [dict(confirm=False), dict(initial_stock=-1), dict(initial_stock=1.5), dict(sizes=['']), dict(stock_location='unknown'), dict(image_data='tampered')])
def test_validation_rejects_unreviewed_or_invalid_requests(manager_stock_app, change):
    factory, client, user_id = manager_stock_app
    item_id = source(factory, user_id)
    data = payload(client, item_id); data.update(change)
    assert client.post(f'/api/inventory/items/{item_id}/variants', json=data).status_code == 422
    with factory() as db:
        assert db.query(Item).count() == 1


def test_stale_preview_and_unauthorized_role_rejected(manager_stock_app):
    factory, client, user_id = manager_stock_app
    item_id = source(factory, user_id); data = payload(client, item_id)
    with factory() as db:
        db.get(Item, item_id).sale_price = 99; db.commit()
    assert client.post(f'/api/inventory/items/{item_id}/variants', json=data).status_code == 409


def test_employee_role_cannot_bypass_variant_authorization(stock_app):
    factory, client, user_id = stock_app
    item_id = source(factory, user_id)
    assert client.get(f'/api/inventory/items/{item_id}/variants').status_code == 403
    assert client.post(f'/api/inventory/items/{item_id}/variants', json=dict(sizes=['8'], model_name='Tênis', source_version='a'*64, confirm=True)).status_code == 403


@pytest.fixture
def pg_variants(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item, StockMovement)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    user_id = uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=user_id, nome='Fixture', email='fixture@example.com', senha_hash='unused')); db.commit()
    try: yield factory, user_id
    finally: isolated.dispose()


def test_postgres_two_source_sizes_concurrently_create_only_one_variant(pg_variants):
    factory, user_id = pg_variants
    first = source(factory, user_id, group_key='same-model')
    second = source(factory, user_id, group_key='same-model')
    with factory() as db:
        db.get(Item, second).size = '10'; db.commit()
    barrier = Barrier(2)
    def create(item_id):
        with factory() as db:
            context = service.variant_context(db, item_id)
            request = VariantCreateRequest(sizes=['8'], model_name='Tênis', source_version=context['source_version'], initial_stock=3, confirm=True)
            barrier.wait(timeout=10)
            result = service.create_variants(db, item_id, request, user_id)
            return len(result['created'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, [first, second])) == [0, 1]
    with factory() as db:
        assert db.query(Item).filter(Item.size == '8').count() == 1
        assert db.query(StockMovement).count() == 1
        assert db.query(Item).filter(Item.size == '8').one().current_stock == 3


def test_postgres_failure_rolls_back_grouping_products_and_movements(pg_variants, monkeypatch):
    factory, user_id = pg_variants
    item_id = source(factory, user_id)
    original = service.create_movement
    calls = 0
    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise RuntimeError('injected failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'create_movement', fail)
    with factory() as db:
        context = service.variant_context(db, item_id)
        request = VariantCreateRequest(sizes=['8', '10'], model_name='Tênis', source_version=context['source_version'], initial_stock=2, confirm=True)
        with pytest.raises(RuntimeError): service.create_variants(db, item_id, request, user_id)
    with factory() as db:
        assert db.query(Item).count() == 1 and db.get(Item, item_id).group_key is None
        assert db.query(StockMovement).count() == 0
