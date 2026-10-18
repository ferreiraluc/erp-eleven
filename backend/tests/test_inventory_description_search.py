"""Description keywords share the catalog's filtering/counting semantics."""
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
        dict(sku_internal='DETAIL-S', name='Essential S', brand='Boss', size='S', color='Preto',
             description='Camiseta de Placa de metal, com logo emborrachado. Algodão; referência UB102.', group_key='essential'),
        dict(sku_internal='DETAIL-M', name='Essential M', brand='Boss', size='M', color='Azul',
             description='Camiseta, placa de METAL com logo emborrachado', group_key='essential'),
        dict(sku_internal='DETAIL-L', name='Essential L', brand='Boss', size='L', color='Branco',
             description='Camiseta lisa de algodão', group_key='essential'),
        dict(sku_internal='PANTS', name='Classic', brand='Prada', size='L', description='Calça com zíper metálico'),
        dict(sku_internal='SHOES', name='Runner', description='Calçados com cadarço'),
        dict(sku_internal='EMPTY', name='Simple', description=None),
        dict(sku_internal='LITERAL', name='Literal', description='Composição: 100% algodão, ref_azul'),
        dict(sku_internal='REMOVED', name='Removed', description='placa metal logo emborrachado', deleted_at=datetime(2026, 1, 1)),
    ]
    db.add_all(Item(**row, current_stock=2, stock_loja=2, stock_deposito=0) for row in rows)
    db.commit()


CASES = [
    ('Placa', {'DETAIL-S', 'DETAIL-M'}),
    ('metal logo emborrachado', {'DETAIL-S', 'DETAIL-M'}),
    ('BOSS placa tamanho P', {'DETAIL-S'}),
    ('placa azul M', {'DETAIL-M'}),
    ('placa branco', set()),  # Color on another size in the grade does not qualify.
    ('ALGODAO', {'DETAIL-S', 'DETAIL-L', 'LITERAL'}),
    ('t-shirt metal', {'DETAIL-S', 'DETAIL-M'}),  # Type aliases also work in descriptions.
    ('tsirt S', {'DETAIL-S'}),
    ('calsa', {'PANTS'}),  # Whole-word types do not include "calçados".
    ('ziper', {'PANTS'}),
    ('8UB102', {'DETAIL-S'}),
    ('%', {'LITERAL'}),
    ('ref_', {'LITERAL'}),
    ("' OR 1=1 --", set()),
]


@pytest.mark.parametrize('term,expected', CASES)
def test_description_keywords_in_catalog(stock_app, term, expected):
    factory, client, _ = stock_app
    with factory() as db:
        seed(db)
    response = client.get('/api/inventory/items', params={'search': term, 'include_images': False})
    assert response.status_code == 200, response.text
    assert {row['sku_internal'] for row in response.json()['items']} == expected
    assert response.json()['total'] == len(expected)


def test_description_pagination_filters_groups_and_bot(stock_app):
    from app.services.assistant_queries import StockArgs, query_stock
    from app.models.usuario import UsuarioRole
    factory, client, user_id = stock_app
    with factory() as db:
        user = db.get(Usuario, user_id)
        user.email = 'lucas@eleven.com'
        user.role = UsuarioRole.ADMIN
        seed(db)
        result = query_stock(db, StockArgs(termo='placa metal'))
        assert {row['sku'] for row in result['resultados']} == {'DETAIL-S', 'DETAIL-M'}
        assert result['unidades'] == 4
    params = {'search': 'placa', 'page_size': 1, 'include_images': False}
    first = client.get('/api/inventory/items', params=params).json()
    second = client.get('/api/inventory/items', params={**params, 'page': 2}).json()
    assert first['total'] == second['total'] == 2
    assert first['items'][0]['id'] != second['items'][0]['id']
    assert client.get('/api/inventory/items', params={**params, 'brand': 'Prada'}).json()['total'] == 0
    assert client.get('/api/inventory/items', params={**params, 'location_stock': 'deposito'}).json()['total'] == 0
    assert client.get('/api/inventory/items', params={**params, 'color': 'Azul'}).json()['total'] == 1
    groups = client.get('/api/inventory/groups', params={'search': 'placa', 'include_images': False}).json()
    assert len(groups) == 1 and groups[0]['matching_count'] == 2
    assert len(groups[0]['items']) == 3  # Context sizes are not counted as matches.

    # Saving a description changes search immediately, without sync or a stale cache.
    item_id = first['items'][0]['id']
    updated = client.put(f'/api/inventory/items/{item_id}', json={'description': 'Bordado exclusivo'})
    assert updated.status_code == 200, updated.text
    assert client.get('/api/inventory/items', params=params).json()['total'] == 1
    assert client.get('/api/inventory/items', params={'search': 'bordado'}).json()['items'][0]['id'] == item_id
    assert client.put(f'/api/inventory/items/{item_id}', json={'description': None}).status_code == 200
    assert client.get('/api/inventory/items', params={'search': 'bordado'}).json()['total'] == 0


def test_description_keywords_match_on_postgresql(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema},public'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item)])
        factory = sessionmaker(bind=isolated)
        with factory() as db:
            seed(db)
            for term, expected in CASES:
                searched = build_search(db, term)
                rows = db.query(Item.sku_internal).filter(Item.deleted_at.is_(None), searched.condition).all()
                assert {row[0] for row in rows} == expected, term
    finally:
        isolated.dispose()
