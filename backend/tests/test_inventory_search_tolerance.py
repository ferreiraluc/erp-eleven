"""User-reported search examples against synthetic catalogs, including PostgreSQL."""
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier
from app.services.inventory_search import build_search
from test_access_postgres import pg
from test_assistant import setup
from test_inventory_ocr import stock_app


def seed(db):
    rows = [
        ('FULL', 'Tshirt Armani AF16548 UB102 2XL', 'Emporio Armani', '2XL', 'Camisetas', 'full'),
        ('PREFIX', 'T-shirt Armani 8UB102 S', 'Emporio Armani', 'S', 'Camisetas', 'prefix'),
        ('DIFFERENT', 'T-shirt Armani AF16548 UB103 S', 'Emporio Armani', 'S', 'Camisetas', None),
        ('OTHER-BRAND', 'T-shirt 8UB102 S', 'Prada', 'S', 'Camisetas', None),
        ('HYPHEN', 'T-shirt Boss Y-26-09 L', 'Boss', 'L', 'Camisetas', 'hyphen'),
        ('SPACE', 'Camiseta Boss Y 26 S', 'Boss', 'S', 'Camisetas', None),
        ('PANTS', 'Calça casual', 'Emporio Armani', 'L', 'Calças', None),
        ('SHOES', 'Tênis Runner', 'Emporio Armani', '11 US', 'Calçados', None),
        ('SHIRT', 'Camisa social', 'Emporio Armani', 'M', 'Camisas', None),
        ('MODEL1', 'Camiseta DN0281 S', 'Givenchy', 'S', 'Camisetas', None),
        ('MODEL2', 'Camiseta DN0282 S', 'Givenchy', 'S', 'Camisetas', None),
        ('DELETED', 'T-shirt 8UB102 S', 'Emporio Armani', 'S', 'Camisetas', None),
    ]
    for sku, name, brand, size, category, group in rows:
        db.add(Item(sku_internal=sku, name=name, brand=brand, size=size, category=category,
                    group_key=group, color='Preto', barcode='999900001111' if sku == 'FULL' else None,
                    stock_loja=2, stock_deposito=0, current_stock=2,
                    deleted_at=datetime(2026, 1, 1) if sku == 'DELETED' else None))
    db.commit()


SHIRTS = {'FULL', 'PREFIX', 'DIFFERENT', 'OTHER-BRAND', 'HYPHEN', 'SPACE', 'MODEL1', 'MODEL2'}
CASES = [
    ('8UB102', {'FULL', 'PREFIX', 'OTHER-BRAND'}),
    ('UB102', {'FULL', 'PREFIX', 'OTHER-BRAND'}),
    ('UB 102', {'FULL', 'PREFIX', 'OTHER-BRAND'}),
    ('AF16548 UB102', {'FULL', 'PREFIX', 'DIFFERENT', 'OTHER-BRAND'}),
    ('T-shirt Emprio Armani 8UB102', {'FULL', 'PREFIX'}),
    ('8UB103', {'DIFFERENT'}),
    ('8UB999', set()),
    ('Y 26', {'HYPHEN', 'SPACE'}),
    ('Y-26', {'HYPHEN', 'SPACE'}),
    ('Y26', {'HYPHEN', 'SPACE'}),
    ('Y - 26', {'HYPHEN', 'SPACE'}),
    ('tsirt Y 26 G', {'HYPHEN'}),
    ('y 26 tamanho P', {'SPACE'}),
    ('calsa', {'PANTS'}),
    ('CALÇA', {'PANTS'}),
    ('calçados', {'SHOES'}),
    ('camisa', {'SHIRT'}),
    ('tsirt', SHIRTS),
    ('camseta', SHIRTS),
    ('Emprio Armani', {'FULL', 'PREFIX', 'DIFFERENT', 'PANTS', 'SHOES', 'SHIRT'}),
    ('Emporio Armnai', {'FULL', 'PREFIX', 'DIFFERENT', 'PANTS', 'SHOES', 'SHIRT'}),
    ('DN0281', {'MODEL1'}),
    ('DN0283', set()),
    ('999900001111', {'FULL'}),
    ('999900001112', set()),
    ("%'; OR true --", set()),
    ('Y.*26', set()),
    ('[a-z]+', set()),
]


@pytest.mark.parametrize('term,expected', CASES)
def test_search_tolerance(stock_app, term, expected):
    factory, client, _ = stock_app
    with factory() as db:
        seed(db)
    response = client.get('/api/inventory/items', params={'search': term, 'include_images': False})
    assert response.status_code == 200, response.text
    assert {row['sku_internal'] for row in response.json()['items']} == expected
    assert response.json()['total'] == len(expected)


def test_suggestions_rank_after_literal_matches_and_keep_filters_pagination_groups(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        seed(db)
    params = {'search': '8UB102', 'brand': 'Emporio Armani', 'page_size': 1, 'include_images': False}
    first = client.get('/api/inventory/items', params=params).json()
    second = client.get('/api/inventory/items', params={**params, 'page': 2}).json()
    assert first['total'] == second['total'] == 2
    assert first['items'][0]['sku_internal'] == 'PREFIX'
    assert second['items'][0]['sku_internal'] == 'FULL'
    full_query = client.get('/api/inventory/items', params={'search': 'AF16548 UB102'}).json()
    assert full_query['items'][0]['sku_internal'] == 'FULL'
    assert client.get('/api/inventory/items', params={**params, 'size': 'S'}).json()['total'] == 1
    assert client.get('/api/inventory/items', params={**params, 'category': 'Calças'}).json()['total'] == 0
    assert client.get('/api/inventory/items', params={**params, 'location_stock': 'deposito'}).json()['total'] == 0
    groups = client.get('/api/inventory/groups', params={'search': 'Emprio armani 8UB102', 'include_images': False}).json()
    assert {g['group_key'] for g in groups} == {'full', 'prefix'}
    assert sum(g['matching_count'] for g in groups) == 2


def test_assistant_uses_same_tolerant_queries_without_mutating_product_identity(stock_app):
    from app.services.assistant_queries import StockArgs, query_stock
    factory, _, _ = stock_app
    with factory() as db:
        seed(db)
        before = db.query(Item.id, Item.name, Item.barcode, Item.size, Item.current_stock).order_by(Item.id).all()
        result = query_stock(db, StockArgs(termo='tsirt Emprio Armani 8UB102'))
        assert {r['sku'] for r in result['resultados']} == {'FULL', 'PREFIX'}
        assert result['unidades'] == 4
        assert db.query(Item.id, Item.name, Item.barcode, Item.size, Item.current_stock).order_by(Item.id).all() == before


def test_postgres_tolerance_matches_sqlite_and_ranking(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema},public'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item)])
        with sessionmaker(bind=isolated)() as db:
            seed(db)
            for term, expected in CASES:
                searched = build_search(db, term)
                rows = db.query(Item.sku_internal).filter(Item.deleted_at.is_(None), searched.condition).order_by(searched.rank).all()
                assert {r[0] for r in rows} == expected, term
            searched = build_search(db, 'AF16548 UB102')
            assert db.query(Item.sku_internal).filter(Item.deleted_at.is_(None), searched.condition).order_by(searched.rank).first()[0] == 'FULL'
    finally:
        isolated.dispose()
