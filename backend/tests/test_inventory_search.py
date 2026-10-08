"""Real queries on disposable catalogs; no production reads or AI requests."""
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier
from app.services.inventory_search import search_filter


def seed(db):
    rows = [
        dict(sku_internal='BOSS-40', name='Runner', brand='Boss', category='Calçados > Tênis', size='40', color='Preto', group_key='boss'),
        dict(sku_internal='BOSS-41', name='Runner', brand='Boss', category='Calçados > Tênis', size='41', color='Branco', group_key='boss'),
        dict(sku_internal='ARMANI-7', name='Casual', brand='EA7 Empório Armani', category='Calçados > Tênis', size='7', color='Preto'),
        dict(sku_internal='ARMANI-75', name='Tênis Clássico', brand='Emporio Armani', size='7,5'),
        dict(sku_internal='ARMANI-11', name='Tênis', brand='Emporio Armani', size='11'),
        dict(sku_internal='OTHER-17', name='Tênis modelo 7', brand='Emporio Armani', size='17', barcode='7777777777777'),
        dict(sku_internal='SHIRT-S', name='Camiseta', brand='Boss', size='S'),
        dict(sku_internal='SHIRT-M', name='Essentials', brand='Boss', category='Camisetas', size='m'),
        dict(sku_internal='TSHIRT-M', name='T-Shirt', brand='Prada', size='M'),
        dict(sku_internal='SHIRT-P', name='Camiseta', brand='Boss', size='P'),
        dict(sku_internal='EA7', name='Referência especial', size='XL'),
        dict(sku_internal='41', name='Código curto', size='XL'),
        dict(sku_internal='LITERAL_%', name='Código literal', size='XL'),
        dict(sku_internal='DELETED-11', name='Tênis', size='11', deleted_at=datetime(2026, 1, 1)),
    ]
    db.add_all(Item(**row, current_stock=2, stock_loja=2, stock_deposito=0) for row in rows)
    db.commit()


CASES = [
    ('Tenis tamanho 11', {'ARMANI-11'}),
    ('armani 7', {'ARMANI-7'}),
    ('Boss 40', {'BOSS-40'}),
    ('Tenis Boss 41', {'BOSS-41'}),
    ('Camiseta tamanho S', {'SHIRT-S'}),
    ('T-shirt tamanho M', {'SHIRT-M', 'TSHIRT-M'}),
    ('CAMISETAS tam. m', {'SHIRT-M', 'TSHIRT-M'}),
    ('t shirt M', {'SHIRT-M', 'TSHIRT-M'}),
    ('tenis da boss no tamanho: 40', {'BOSS-40'}),
    ('EA7 Empório Armani tamanho 7', {'ARMANI-7'}),
    ('Tênis classico 7.5', {'ARMANI-75'}),
    ('armani tamanho 7,50', {'ARMANI-75'}),
    ('boss tamanho 40.0', {'BOSS-40'}),
    ('camiseta size M', {'SHIRT-M', 'TSHIRT-M'}),
    ('sneakers boss talle 41', {'BOSS-41'}),
    ('S', {'SHIRT-S'}),
    ('7', {'ARMANI-7'}),
    ('41', {'BOSS-41', '41'}),
    ('7777777777777', {'OTHER-17'}),
    ('BOSS-41', {'BOSS-41'}),
    ('EA7', {'EA7'}),  # Literal identity, not size 7.
    ('LITERAL_%', {'LITERAL_%'}),
    ('%', {'LITERAL_%'}),
    ('tenis tamanho 12', set()),
    ('tenis boss 7', set()),
    ("' OR 1=1 --", set()),
]


@pytest.mark.parametrize('term,expected', CASES)
def test_search_examples_and_literal_codes(stock_app, term, expected):
    factory, client, _ = stock_app
    with factory() as db:
        seed(db)
    response = client.get('/api/inventory/items', params={'search': term})
    assert response.status_code == 200, response.text
    assert {x['sku_internal'] for x in response.json()['items']} == expected
    assert response.json()['total'] == len(expected)


def test_pagination_facets_and_groups_require_one_matching_variant(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        seed(db)
    result = client.get('/api/inventory/items', params={'search': 'camiseta M', 'page_size': 1, 'page': 2}).json()
    assert result['total'] == 2 and len(result['items']) == 1
    assert client.get('/api/inventory/items', params={'search': 'camiseta M', 'brand': 'Prada'}).json()['total'] == 1
    # Black exists, and 41 exists, but not on the same item in this grade.
    assert client.get('/api/inventory/groups', params={'search': 'tenis boss preto 41'}).json() == []
    assert client.get('/api/inventory/groups', params={'search': 'tenis boss 41', 'brand': 'Prada'}).json() == []
    groups = client.get('/api/inventory/groups', params={'search': 'tenis boss 41'}).json()
    assert len(groups) == 1
    assert {item['size'] for item in groups[0]['items']} == {'40', '41'}
    for path in ('items', 'groups'):
        assert client.get(f'/api/inventory/{path}', params={'search': 'a' * 257}).status_code == 422


def test_assistant_combines_attributes_without_broadening_stock_totals(stock_app):
    from app.services.assistant_queries import StockArgs, query_stock
    factory, _, _ = stock_app
    with factory() as db:
        seed(db)
        result = query_stock(db, StockArgs(termo='Tênis Boss 41'))
        assert [row['sku'] for row in result['resultados']] == ['BOSS-41']
        assert result['unidades'] == 2


def test_postgresql_search_matches_sqlite_semantics(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item)])
        factory = sessionmaker(bind=isolated)
        with factory() as db:
            seed(db)
            for term, expected in CASES:
                rows = db.query(Item.sku_internal).filter(Item.deleted_at.is_(None), search_filter(db, term)).all()
                assert {row[0] for row in rows} == expected, term
    finally:
        isolated.dispose()
