"""Isolated gallery storage, lazy reads and preservation across existing workflows."""
import uuid

import pytest
import sqlalchemy as sa
from test_assistant import setup
from test_inventory_ocr import stock_app, picture
from test_product_intake_grade import manager_stock_app
from test_inventory_variants import payload
from test_inventory_duplicate import draft
from test_access_postgres import pg, upgrade
from app.models.inventory import Item


def create(client):
    images = [picture('JPEG', (160 + i, 100)) for i in range(5)]
    response = client.post('/api/inventory/items', json={
        'name': 'Camiseta galeria S', 'size': 'S', 'image_data': images[0], 'additional_images': images[1:]})
    assert response.status_code == 201, response.text
    return response.json()['id'], images


def test_gallery_is_separate_from_all_catalog_and_detail_reads(manager_stock_app):
    factory, client, _ = manager_stock_app
    id, images = create(client)
    with factory() as db:
        row = db.get(Item, uuid.UUID(id))
        assert 'additional_images' in sa.inspect(row).unloaded
        engine = db.bind
    statements = []
    def capture(conn, cursor, sql, *args): statements.append(sql)
    sa.event.listen(engine, 'before_cursor_execute', capture)
    try:
        for path in ('items?include_images=false', 'groups?include_images=false', 'suggestions?include_images=false', f'items/{id}'):
            result = client.get('/api/inventory/' + path)
            assert result.status_code == 200
            assert 'additional_images' not in result.text
            assert images[1] not in result.text
    finally:
        sa.event.remove(engine, 'before_cursor_execute', capture)
    assert not any('additional_images' in sql for sql in statements if not sql.startswith('SELECT count('))
    assert client.get(f'/api/inventory/items/{id}/photos').json() == {'additional_images': images[1:]}
    # Old clients editing unrelated fields must never erase the new gallery.
    assert client.put(f'/api/inventory/items/{id}', json={'name': 'Nome corrigido'}).status_code == 200
    assert client.get(f'/api/inventory/items/{id}/photos').json()['additional_images'] == images[1:]
    assert client.put(f'/api/inventory/items/{id}', json={'additional_images': []}).status_code == 200
    assert client.get(f'/api/inventory/items/{id}/photos').json()['additional_images'] == []


@pytest.mark.parametrize('photos', [
    [picture()] * 5, ['https://example.com/image.jpg'], ['data:image/svg+xml;base64,PHN2Zy8+'],
    ['data:image/jpeg;base64,invalid'], [picture('JPEG', (1201, 20))],
    ['data:image/jpeg;base64,' + 'A' * 340000],
])
def test_gallery_rejects_over_limit_or_invalid_media_atomically(manager_stock_app, photos):
    factory, client, _ = manager_stock_app
    response = client.post('/api/inventory/items', json={'name': 'Invalid photos', 'additional_images': photos})
    assert response.status_code == 422
    with factory() as db: assert db.query(Item).count() == 0


def test_gallery_requires_auth_and_hides_deleted_products(manager_stock_app):
    factory, client, _ = manager_stock_app
    id, _ = create(client)
    with factory() as db:
        from datetime import datetime
        db.get(Item, uuid.UUID(id)).deleted_at = datetime.now(); db.commit()
    assert client.get(f'/api/inventory/items/{id}/photos').status_code == 404
    assert client.get(f'/api/inventory/items/{uuid.uuid4()}/photos').status_code == 404
    from app.dependencies import get_current_active_user
    del client.app.dependency_overrides[get_current_active_user]
    assert client.get(f'/api/inventory/items/{id}/photos').status_code == 401


def test_new_grade_and_existing_grade_keep_gallery_and_source_version(manager_stock_app):
    factory, client, _ = manager_stock_app
    id, images = create(client)
    request = payload(client, id)
    request['sizes'] = ['M', 'L']
    response = client.post(f'/api/inventory/items/{id}/variants', json=request)
    assert response.status_code == 201, response.text
    for row in response.json()['created']:
        assert client.get(f'/api/inventory/items/{row["id"]}/photos').json()['additional_images'] == images[1:]
    request = payload(client, id); request['sizes'] = ['XL']
    client.put(f'/api/inventory/items/{id}', json={'additional_images': images[1:2]})
    assert client.post(f'/api/inventory/items/{id}/variants', json=request).status_code == 409
    response = client.post('/api/inventory/items/grade/quantities', json={
        'name': 'Outra camiseta', 'sizes': ['M', 'L'], 'image_data': images[0], 'additional_images': images[1:]})
    assert response.status_code == 201, response.text
    for row in response.json()['items']:
        assert client.get(f'/api/inventory/items/{row["id"]}/photos').json()['additional_images'] == images[1:]


def test_editable_duplicate_inherits_or_replaces_gallery(manager_stock_app):
    factory, client, _ = manager_stock_app
    id, images = create(client)
    request = draft(client, id, size='M'); request['initial_stock'] = 0
    response = client.post(f'/api/inventory/items/{id}/duplicate', json=request)
    assert response.status_code == 201, response.text
    assert client.get(f'/api/inventory/items/{response.json()["id"]}/photos').json()['additional_images'] == images[1:]
    request = draft(client, id, size='L', additional_images=images[2:3]); request['initial_stock'] = 0
    response = client.post(f'/api/inventory/items/{id}/duplicate', json=request)
    assert response.status_code == 201, response.text
    assert client.get(f'/api/inventory/items/{response.json()["id"]}/photos').json()['additional_images'] == images[2:3]
    assert client.get(f'/api/inventory/items/{id}/photos').json()['additional_images'] == images[1:]


def test_pg_gallery_migration_preserves_primary_photos_and_nullable_legacy_rows(pg):
    engine, schema = pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE inventory_items (id integer PRIMARY KEY, image_data text)')
        conn.exec_driver_sql("INSERT INTO inventory_items VALUES (1, 'legacy-original')")
        upgrade(conn, 'k3f4a5b6c7d8_product_photo_gallery.py')
        assert conn.exec_driver_sql('SELECT image_data, additional_images FROM inventory_items').one() == ('legacy-original', None)
        conn.execute(sa.text('UPDATE inventory_items SET additional_images=CAST(:data AS json) WHERE id=1'), {'data': '["gallery-fixture"]'})
        assert conn.exec_driver_sql('SELECT additional_images FROM inventory_items').scalar() == ['gallery-fixture']
