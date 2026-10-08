"""Store-specific shoe chart, including explicit units, ranking and real SQL."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier
from app.services.inventory_search import build_search
from app.services.inventory_footwear_sizes import OFFSETS


def seed_chart(db):
    # Interleaved names deliberately put equivalent labels before US labels in
    # alphabetical order, so ordering tests cannot accidentally pass by name.
    for us in range(6, 14):
        for half in (0, .5):
            for system, brand in [('US', 'Armani'), ('BR', 'Havaianas'), ('BOSS', 'Hugo Boss'), ('EU', 'D&G')]:
                value = us + half + int(OFFSETS[system])
                label = f'{value:g}'
                db.add(Item(sku_internal=f'{system}-{us+half:g}', name='Chinelo ' + ('Zulu' if system == 'US' else 'Alpha'),
                            size=label, brand=brand, category='Calçados > Chinelos',
                            group_key=f'{system}-{us+half:g}', current_stock=1, stock_loja=1, stock_deposito=0))
    db.add_all([
        Item(name='Calça', sku_internal='CLOTHES-43', size='43', brand='Boss', category='Roupas'),
        Item(name='Camiseta', sku_internal='CLOTHES-11', size='11', brand='Boss', category='Roupas'),
        Item(name='Camiseta', sku_internal='CLOTHES-115', size='11.5', brand='Boss', category='Roupas'),
        Item(name='Tênis', sku_internal='BOSS-BR43', size='43 BR', brand='Boss'),
        Item(name='Tênis', sku_internal='BOSS-BR44', size='BR44', brand='Boss'),
        Item(name='Tênis', sku_internal='GENERIC-EU45', size='EU/IT 45', brand='Outra'),
        Item(name='Tênis', sku_internal='EXPLICIT-US115', size='US 11,5', brand='Outra'),
        Item(name='Tênis', sku_internal='EXPLICIT-US11', size='11US', brand='Outra'),
        Item(name='Tênis', sku_internal='NAME-DG', size='45', brand='Dolce & Gabbana'),
        Item(name='Tênis', sku_internal='RAW-44', size='44', brand='Outra'),
        Item(name='Tênis', sku_internal='SIZE-14', size='14', brand='Armani'),
        Item(name='Boné', sku_internal='chinelo 11', size='U'),
    ])
    db.commit()


def row_skus(us):
    return {f'{system}-{us+half:g}' for system in OFFSETS for half in (0, .5)}


@pytest.mark.parametrize('us', range(6, 14))
def test_every_chart_row_is_searchable_from_every_scale(stock_app, us):
    factory, client, _ = stock_app
    with factory() as db:
        seed_chart(db)
    for system, offset in OFFSETS.items():
        query = f'chinelos tamanho {us+int(offset)}{system}'
        data = client.get('/api/inventory/items', params={'search': query, 'page_size': 100}).json()
        assert {r['sku_internal'] for r in data['items']} == row_skus(us), query
        assert data['items'][0]['sku_internal'] == f'{system}-{us}', query


def test_exact_then_equivalents_then_halves_before_pagination(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        seed_chart(db)
    params = {'search': 'chinelos 11', 'page_size': 1}
    first = client.get('/api/inventory/items', params=params).json()
    assert first['total'] == 8 and first['items'][0]['sku_internal'] == 'US-11'
    assert first['total_pages'] == 8
    all_skus = []
    for page in range(1, 9):
        data = client.get('/api/inventory/items', params={**params, 'page': page}).json()
        all_skus.append(data['items'][0]['sku_internal'])
    assert len(set(all_skus)) == 8
    assert set(all_skus[:4]) == {f'{system}-11' for system in OFFSETS}
    halves = client.get('/api/inventory/items', params={'search': 'chinelos 11,5'}).json()['items']
    assert halves[0]['sku_internal'] == 'US-11.5'
    assert {r['sku_internal'] for r in halves[:4]} == {f'{system}-11.5' for system in OFFSETS}


def test_explicit_scale_wins_over_brand_and_clothes_are_never_converted(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        seed_chart(db)
    for term in ['tenis 11', 'tenis US 11', 'tenis 43BR', 'tenis 44BOSS', 'tenis 45 EU/IT']:
        data = client.get('/api/inventory/items', params={'search': term}).json()
        assert {r['sku_internal'] for r in data['items']} == {
            'BOSS-BR43', 'GENERIC-EU45', 'EXPLICIT-US115', 'EXPLICIT-US11', 'NAME-DG'}, term
    for term, expected in [('calca 43', {'CLOTHES-43'}), ('camiseta 11', {'CLOTHES-11'}),
                           ('camiseta 11.5', {'CLOTHES-115'}), ('tenis 14', {'SIZE-14'}),
                           ('tenis DG 11', {'NAME-DG'}), ('tenis Dolce & Gabbana 45', {'NAME-DG'})]:
        data = client.get('/api/inventory/items', params={'search': term}).json()
        assert {r['sku_internal'] for r in data['items']} == expected, term
    literal = client.get('/api/inventory/items', params={'search': 'chinelo 11'}).json()['items']
    assert literal[0]['sku_internal'] == 'chinelo 11'


def test_brand_filter_groups_and_assistant_share_equivalences(stock_app):
    from app.services.assistant_queries import StockArgs, query_stock
    factory, client, _ = stock_app
    with factory() as db:
        seed_chart(db)
        for args in [StockArgs(termo='chinelos 11'), StockArgs(termo='chinelos', tamanho='11')]:
            result = query_stock(db, args)
            assert result['unidades'] == 8
            assert result['resultados'][0]['sku'] == 'US-11'
    params = {'search': 'chinelos 44', 'brand': 'Hugo Boss'}
    data = client.get('/api/inventory/items', params=params).json()
    assert {r['sku_internal'] for r in data['items']} == {'BOSS-11', 'BOSS-11.5'}
    groups = client.get('/api/inventory/groups', params={'search': 'chinelos 11'}).json()
    assert {g['group_key'] for g in groups} == row_skus(11)
    assert groups[0]['group_key'] == 'US-11'


def test_literal_custom_sizes_and_whitespace_search_keep_working(stock_app):
    from app.services.assistant_queries import StockArgs, query_stock
    factory, client, _ = stock_app
    with factory() as db:
        db.add(Item(name='Boné', sku_internal='CUSTOM', size='One Size', group_key='custom'))
        db.commit()
        result = query_stock(db, StockArgs(tamanho='One Size'))
        assert [item['sku'] for item in result['resultados']] == ['CUSTOM']
    assert client.get('/api/inventory/items', params={'search': '  '}).json()['total'] == 1
    assert len(client.get('/api/inventory/groups', params={'search': '  '}).json()) == 1


def test_equivalences_and_ranking_on_postgresql(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item)])
        with sessionmaker(bind=isolated)() as db:
            seed_chart(db)
            for us in range(6, 14):
                for system, offset in OFFSETS.items():
                    term = f'chinelos {us+int(offset)}{system}'
                    search = build_search(db, term)
                    rows = db.query(Item).filter(search.condition).order_by(search.rank, Item.sku_internal).all()
                    assert {r.sku_internal for r in rows} == row_skus(us), term
                    assert rows[0].sku_internal == f'{system}-{us}', term
                    keys = db.query(Item.group_key).filter(search.condition).group_by(Item.group_key).order_by(sa.func.min(search.rank)).all()
                    assert keys[0][0] == f'{system}-{us}'
    finally:
        isolated.dispose()
