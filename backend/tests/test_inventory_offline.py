"""Offline stock snapshots remain a read-only, bounded projection."""
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import sqlalchemy as sa

from test_assistant import setup
from test_inventory_ocr import stock_app
from app.models.inventory import Item
from app.services.inventory_offline import catalog_page
from app.services.access_policy import require_profile_route


def seed(db, **changes):
    values = dict(id=uuid.uuid4(), name='Camiseta com placa', sku_internal=str(uuid.uuid4()),
                  inventory_code=None, description='Detalhe ' * 500, category='Roupas > Camisetas',
                  sale_price=80, sale_currency='USD', cost_price=123, cost_currency='BRL',
                  current_stock=5, stock_loja=2, stock_deposito=3,
                  reserved_loja=1, reserved_deposito=0, image_data='private-original',
                  additional_images=['private-gallery'])
    row = Item(**{**values, **changes}); db.add(row); db.flush(); return row


def test_projection_is_bounded_private_cache_and_never_returns_costs_originals_or_supplier(stock_app):
    factory, client, owner = stock_app
    with factory() as db:
        seed(db); seed(db); seed(db, deleted_at=datetime.now(timezone.utc))
        db.commit()
    response = client.get('/api/inventory/offline-catalog', params={'limit': 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers['cache-control'] == 'no-store'
    assert body['schema'] == 1 and body['owner_id'] == str(owner)
    assert body['observed_at'].endswith('+00:00')
    assert len(body['items']) == 1 and body['next_cursor']
    item = body['items'][0]
    assert item['stock_confirmed'] is True
    assert (item['stock_loja'], item['stock_deposito'], item['reserved_loja']) == (2, 3, 1)
    assert (item['available_loja'], item['available_deposito'], item['available_stock']) == (1, 3, 4)
    assert item['sale_price'] == 80 and len(item['description']) == 512 and item['has_image']
    for key in ('cost_price', 'cost_currency', 'supplier_id', 'image_data', 'additional_images', 'created_by'):
        assert key not in item
    second = client.get('/api/inventory/offline-catalog', params={'limit': 1, 'after_id': body['next_cursor']}).json()
    assert len(second['items']) == 1 and second['next_cursor'] is None
    assert second['items'][0]['id'] != item['id']
    assert client.get('/api/inventory/offline-catalog', params={'limit': 501}).status_code == 422
    assert client.get('/api/inventory/offline-catalog', params={'after_id': 'invalid'}).status_code == 422


def test_inconsistent_stock_stays_unknown_but_legitimate_negative_balance_is_preserved(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        mismatch = seed(db, current_stock=20)
        null = seed(db)
        reserved = seed(db, reserved_loja=3)
        negative = seed(db, current_stock=-1, stock_loja=-1, stock_deposito=0, reserved_loja=0)
        db.commit()
        db.execute(sa.update(Item).where(Item.id == null.id).values(stock_loja=None))
        ids = [str(row.id) for row in (mismatch, null, reserved, negative)]
        db.commit()
    rows = {row['id']: row for row in client.get('/api/inventory/offline-catalog').json()['items']}
    for item_id in ids[:3]:
        assert rows[item_id]['stock_confirmed'] is False
        assert all(rows[item_id][field] is None for field in ('stock_loja', 'stock_deposito', 'current_stock', 'reserved_loja', 'available_stock'))
    assert rows[ids[3]]['stock_confirmed'] is True
    assert rows[ids[3]]['stock_loja'] == -1 and rows[ids[3]]['available_stock'] == -1


def test_page_has_one_projection_query_and_fresh_copy_removes_hard_and_soft_deletions(stock_app):
    factory, _, owner = stock_app
    with factory() as db:
        first, second = seed(db), seed(db); db.commit()
        statements = []
        def capture(conn, cursor, sql, parameters, context, executemany): statements.append(sql)
        sa.event.listen(db.bind, 'before_cursor_execute', capture)
        try: result = catalog_page(db, SimpleNamespace(id=owner))
        finally: sa.event.remove(db.bind, 'before_cursor_execute', capture)
        assert len(statements) == 1 and len(result['items']) == 2
        assert 'additional_images' not in statements[0] and 'cost_price' not in statements[0]
        assert 'inventory_items.image_data AS' not in statements[0]
        db.delete(first); second.deleted_at = datetime.now(timezone.utc); db.commit()
        assert catalog_page(db, SimpleNamespace(id=owner))['items'] == []


def test_reseller_offline_projection_is_explicitly_read_only():
    import pytest
    from fastapi import HTTPException
    user = SimpleNamespace(access_profile='reseller')
    require_profile_route(user, 'GET', '/api/inventory/offline-catalog')
    with pytest.raises(HTTPException):
        require_profile_route(user, 'POST', '/api/inventory/offline-catalog')
