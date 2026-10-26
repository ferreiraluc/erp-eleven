"""Related products are bounded catalog suggestions, never barcode identities."""
import uuid
from datetime import datetime

import sqlalchemy as sa
from test_assistant import setup
from test_inventory_ocr import stock_app
from app.models.inventory import Item


def seed(db):
    rows = [
        Item(id=uuid.UUID(f'a0000000-0000-0000-0000-{i+1:012x}'), sku_internal=f'RELATED-{i}', name=f'Fixture {i}',
             brand=brand, category=category, group_key=group, size='M', color='Azul',
             current_stock=3, stock_loja=3, stock_deposito=0, image_data='ORIGINAL-LARGE-PHOTO',
             additional_images=['ORIGINAL-GALLERY'], is_active=active,
             deleted_at=datetime.now() if deleted else None)
        for i, (brand, category, group, active, deleted) in enumerate([
            ('Boss', 'Camisetas', 'family', True, False),  # source
            ('Boss', 'Camisetas', 'family', True, False),
            ('Boss', 'Camisetas', 'family', True, False),
            ('Boss', 'Camisetas', 'another', True, False),
            ('Boss', 'Calçados', None, True, False),
            ('Prada', 'Camisetas', None, True, False),
            ('Prada', 'Calçados', None, True, False),  # unrelated
            ('Boss', 'Camisetas', 'family', False, False),
            ('Boss', 'Camisetas', 'family', True, True),
            (None, 'Camisetas', None, True, False),
            (None, None, None, True, False),
        ])]
    db.add_all(rows); db.commit()
    return [str(row.id) for row in rows]


def test_related_prioritizes_family_and_paginates_without_duplicates_or_photos(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        ids = seed(db)
    results, params = [], {'limit': 2}
    for _ in range(5):
        response = client.get(f'/api/inventory/items/{ids[0]}/related', params=params)
        assert response.status_code == 200, response.text
        assert 'ORIGINAL' not in response.text
        page = response.json()
        assert len(page['items']) <= 2
        results += page['items']
        if not page['next_cursor']:
            break
        params.update(page['next_cursor'])
    assert [row['item']['id'] for row in results] == [ids[i] for i in (1, 2, 3, 4, 5, 9)]
    assert [row['relation'] for row in results] == ['family', 'family', 'brand_category', 'brand', 'category', 'category']
    assert all(row['item']['image_data'] is None and row['item']['has_image'] for row in results)
    assert client.get(f'/api/inventory/items/{ids[10]}/related').json()['items'] == []


def test_related_validation_authentication_and_missing_sources(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        ids = seed(db)
    path = f'/api/inventory/items/{ids[0]}/related'
    for params in ({'limit': 0}, {'limit': 25}, {'after_rank': 6}, {'after_rank': 0}, {'after_id': ids[1]}, {'after_id': 'bad'}):
        assert client.get(path, params=params).status_code == 422
    for id in (ids[7], ids[8], str(uuid.uuid4())):
        assert client.get(f'/api/inventory/items/{id}/related').status_code == 404
    from app.dependencies import get_current_active_user
    del client.app.dependency_overrides[get_current_active_user]
    assert client.get(path).status_code == 401


def test_related_does_not_count_catalog_or_materialize_gallery(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        ids = seed(db); engine = db.bind
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    sa.event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.get(f'/api/inventory/items/{ids[0]}/related', params={'limit': 1})
        assert response.status_code == 200
    finally:
        sa.event.remove(engine, 'before_cursor_execute', capture)
    selects = [sql for sql in statements if 'SELECT' in sql and 'inventory_items' in sql]
    assert len(selects) == 4  # source, color vocabulary, bounded IDs, metadata batch
    assert all('count(' not in sql.lower() and 'additional_images' not in sql and 'thumbnail_data' not in sql for sql in selects)
    assert all('inventory_items.image_data AS' not in sql for sql in selects)
