"""Barcode lookups keep ambiguity while avoiding full catalog photos in PDV."""
from datetime import datetime, timezone

import sqlalchemy as sa

from test_assistant import setup
from test_access_postgres import pg
from test_inventory_ocr import stock_app
from test_inventory_variants import pg_variants
from app.models.inventory import Item


def test_light_barcode_preserves_every_match_stock_and_legacy_images(stock_app):
    factory, client, _ = stock_app
    photo = 'data:image/png;base64,' + 'a' * (256 * 1024)
    with factory() as db:
        rows = [Item(name=f'Calçado QA {i}', sku_internal=f'QA-BAR-{i}', barcode='0012',
                     size=str(i + 6), image_data=photo if i else None,
                     current_stock=i, stock_loja=i, stock_deposito=0,
                     sale_price=100, sale_currency='USD') for i in range(12)]
        db.add_all(rows + [
            Item(name='Inativo', sku_internal='QA-INACTIVE', barcode='0012', is_active=False),
            Item(name='Excluído', sku_internal='QA-DELETED', barcode='0012', deleted_at=datetime.now(timezone.utc)),
            Item(name='Outro código', sku_internal='QA-OTHER', barcode='12'),
        ]); db.commit()
        ids = {str(row.id) for row in rows}
        engine = db.bind
    queries = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'inventory_items' in statement:
            queries.append(statement)
    sa.event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.get('/api/inventory/items/barcode/0012', params={'include_images': False})
    finally:
        sa.event.remove(engine, 'before_cursor_execute', capture)
    assert response.status_code == 200, response.text
    items = response.json()
    assert {row['id'] for row in items} == ids
    assert len(queries) == 1
    assert 'image_data AS inventory_items_image_data' not in queries[0]
    assert all(row['image_data'] is None for row in items)
    assert sum(row['has_image'] for row in items) == 11
    assert all(row['stock_loja'] == row['current_stock'] == int(row['size']) - 6 for row in items)
    assert all(float(row['sale_price']) == 100 and row['sale_currency'] == 'USD' for row in items)
    assert len(response.content) < 30000
    legacy = client.get('/api/inventory/items/barcode/0012')
    assert {row['id'] for row in legacy.json()} == ids
    assert sum(row['image_data'] == photo for row in legacy.json()) == 11
    assert client.get('/api/inventory/items/barcode/unknown', params={'include_images': False}).json() == []


def test_light_barcode_projection_on_isolated_postgres(pg_variants):
    from app.api.endpoints.inventory import get_items_by_barcode
    factory, uid = pg_variants
    photo = 'data:image/png;base64,' + 'a' * (64 * 1024)
    with factory() as db:
        db.add_all([Item(name=f'QA {n}', sku_internal=f'PG-BAR-{n}', barcode='SHARED',
                         image_data=photo, created_by=uid) for n in range(20)])
        db.commit()
    with factory() as db:
        rows = get_items_by_barcode('SHARED', include_images=False, db=db, current_user=None)
        assert len(rows) == 20 and all(row.has_image and row.image_data is None for row in rows)
        originals = get_items_by_barcode('SHARED', include_images=True, db=db, current_user=None)
        assert len(originals) == 20 and all(row.image_data == photo for row in originals)
