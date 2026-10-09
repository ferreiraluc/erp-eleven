"""Catalog reads must not materialize originals; all fixtures are disposable."""
import base64
import io
import uuid
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from PIL import Image
from test_assistant import setup
from test_inventory_ocr import stock_app, picture
from app.models.inventory import Item
from app.services import inventory_images as images


def seed(db):
    photo = picture('JPEG', (1600, 900))
    rows = [Item(name='Camiseta M', sku_internal=str(i), image_data=photo, current_stock=3,
                 stock_loja=3, stock_deposito=0, group_key='grade' if i < 2 else None) for i in range(4)]
    db.add_all(rows); db.commit()
    return [str(row.id) for row in rows], photo


def test_light_catalog_omits_originals_but_full_detail_is_preserved(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        ids, photo = seed(db)
    for route in ('items', 'groups', 'suggestions'):
        response = client.get(f'/api/inventory/{route}', params={'include_images': False})
        assert response.status_code == 200, response.text
        body = response.json()
        rows = body['items'] if route == 'items' else [item for group in body for item in group['items']]
        assert rows and all(row['has_image'] and row['image_data'] is None for row in rows)
        assert photo not in response.text
    assert client.get('/api/inventory/items/' + ids[0]).json()['image_data'] == photo
    assert client.get('/api/inventory/items').json()['items'][0]['image_data'] == photo


def test_catalog_defers_photo_column_and_summary_only_aggregates(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        seed(db)
        query = images.catalog_query(db.query(Item), False)
        row, has_image = query.first()
        assert has_image and 'image_data' in sa.inspect(row).unloaded
        with pytest.raises(sa.exc.InvalidRequestError):
            _ = row.image_data
        assert images.catalog_response(row, has_image, False).image_data is None
        engine = db.bind
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany): statements.append(statement)
    sa.event.listen(engine, 'before_cursor_execute', capture)
    try:
        summary = client.get('/api/inventory/alerts/summary').json()
    finally:
        sa.event.remove(engine, 'before_cursor_execute', capture)
    assert summary['total_active_items'] == 4
    assert summary['group_count'] == 1 and summary['grouped_items_count'] == 2
    assert not any('image_data' in sql for sql in statements)


def test_thumbnail_is_small_cached_invalidated_and_does_not_change_original(stock_app, monkeypatch):
    factory, client, _ = stock_app
    with factory() as db: ids, photo = seed(db)
    images._thumbnails.clear()
    calls = []
    original = images._thumbnail
    def encode(data): calls.append(True); return original(data)
    monkeypatch.setattr(images, '_thumbnail', encode)
    path = '/api/inventory/items/' + ids[0] + '/thumbnail'
    result = client.get(path)
    assert result.status_code == 200
    thumbnail = result.json()['image_data']
    with Image.open(io.BytesIO(base64.b64decode(thumbnail.split(',')[1]))) as img:
        assert img.size == (256, 144) and img.format == 'JPEG'
    assert len(thumbnail) < len(photo) and len(thumbnail) <= 48 * 1024
    assert client.get(path).json()['image_data'] == thumbnail and len(calls) == 1
    assert client.get('/api/inventory/items/' + ids[0]).json()['image_data'] == photo
    with factory() as db:
        row = db.query(Item).filter(Item.sku_internal == '0').one()
        row.image_data = None; row.updated_at += timedelta(seconds=1); db.commit()
    assert client.get(path).json()['image_data'] is None and len(calls) == 2
    with factory() as db:
        row = db.query(Item).filter(Item.sku_internal == '0').one(); row.deleted_at = datetime.now(); db.commit()
    assert client.get(path).status_code == 404  # Even if its thumbnail was previously cached.


def test_thumbnail_cache_is_bounded_and_requires_authentication(stock_app, monkeypatch):
    factory, client, _ = stock_app
    with factory() as db: ids, _ = seed(db)
    images._thumbnails.clear(); monkeypatch.setattr(images, 'MAX_CACHE', 2)
    for id in ids:
        assert client.get('/api/inventory/items/' + id + '/thumbnail').status_code == 200
    assert len(images._thumbnails) == 2
    from app.dependencies import get_current_active_user
    del client.app.dependency_overrides[get_current_active_user]
    assert client.get('/api/inventory/items/' + ids[-1] + '/thumbnail').status_code == 401


def test_invalidated_preview_ignores_memory_cache_even_without_date_change(stock_app):
    factory, client, _ = stock_app
    with factory() as db: ids, _ = seed(db)
    path = '/api/inventory/items/' + ids[0] + '/thumbnail'
    assert client.get(path).json()['image_data']
    with factory() as db:
        # Mimic the PostgreSQL trigger when a bulk photo update preserves the date.
        db.connection().execute(Item.__table__.update().where(Item.id == uuid.UUID(ids[0])).values(
            image_data=None, thumbnail_data=None, thumbnail_ready=False, updated_at=Item.updated_at))
        db.commit()
    assert client.get(path).json()['image_data'] is None


@pytest.mark.parametrize('value', [None, '', 'https://example.com/not-fetched.jpg',
    'data:image/png;base64,!!', 'data:image/png;base64,YWJj',
    'data:image/png;base64,' + 'x' * images.MAX_ENCODED])
def test_invalid_photos_are_safe_placeholders(value):
    assert images._thumbnail(value) is None


def test_thumbnail_releases_auth_connection_before_wait_and_decode(stock_app, monkeypatch):
    factory, _, _ = stock_app
    with factory() as db:
        ids, _ = seed(db)
    images._thumbnails.clear()
    with factory() as db:
        db.execute(sa.text('SELECT 1'))  # Authentication has already opened a transaction.
        assert db.in_transaction()

        class CheckedLock:
            def acquire(self, timeout):
                assert not db.in_transaction(), 'Waiting image retained an authentication connection'
                return True
            def release(self):
                assert not db.in_transaction()

        def decode(data):
            assert not db.in_transaction(), 'Image decoding retained a database connection'
            return 'small-preview'

        monkeypatch.setattr(images, '_thumbnail_lock', CheckedLock())
        monkeypatch.setattr(images, '_thumbnail', decode)
        assert images.product_thumbnail(db, uuid.UUID(ids[0])) == {'image_data': 'small-preview'}


def test_busy_thumbnail_returns_bounded_retry_without_holding_connection(stock_app):
    from fastapi import HTTPException
    factory, _, _ = stock_app
    images._thumbnail_lock.acquire()
    try:
        with factory() as db:
            db.execute(sa.text('SELECT 1'))
            with pytest.raises(HTTPException) as error:
                images.product_thumbnail(db, uuid.uuid4())
            assert error.value.status_code == 503
            assert error.value.headers['Retry-After'] == '2'
            assert not db.in_transaction()
    finally:
        images._thumbnail_lock.release()


def test_batch_thumbnails_persist_and_survive_memory_cache_eviction(stock_app, monkeypatch):
    factory, client, _ = stock_app
    with factory() as db:
        ids, photo = seed(db)
        row = db.get(Item, uuid.UUID(ids[0])); original_date = row.updated_at
    images._thumbnails.clear()
    first = client.get('/api/inventory/items/thumbnails', params=[('ids', id) for id in ids])
    assert first.status_code == 200
    assert len(first.json()['thumbnails']) == 4 and not first.json()['retry_ids']
    images._thumbnails.clear()
    def no_decode(data): raise AssertionError('A prepared preview must not decode its original again')
    monkeypatch.setattr(images, '_thumbnail', no_decode)
    assert client.get('/api/inventory/items/thumbnails', params=[('ids', id) for id in ids]).json() == first.json()
    with factory() as db:
        row = db.get(Item, uuid.UUID(ids[0]))
        assert row.image_data == photo and row.updated_at == original_date
        assert row.thumbnail_ready and row.thumbnail_data
        row.name = 'Renamed'; db.commit()
        assert row.thumbnail_ready
        row.image_data = None; db.commit()
        assert not row.thumbnail_ready and row.thumbnail_data is None
    assert client.get('/api/inventory/items/thumbnails', params=[('ids', id) for id in ids]*4).status_code == 422
    from app.dependencies import get_current_active_user
    del client.app.dependency_overrides[get_current_active_user]
    assert client.get('/api/inventory/items/thumbnails', params={'ids':ids[0]}).status_code == 401
