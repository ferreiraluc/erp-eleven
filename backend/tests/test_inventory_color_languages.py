"""Multilingual lookup keeps shades, identity, paging and stored names intact."""
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app
from app.models.inventory import Item
from app.services.inventory_colors import color_key


@pytest.mark.parametrize('a,b', [('Black','Preta'), ('Branco','Blanco'), ('Blue','Azul'),
    ('Azul marino','Navy blue'), ('Marrón','Brown'), ('Gris','Cinza'),
    ('Preto e Branco','White + Negro'), ('Beige / Black','Negra y Bege')])
def test_color_aliases(a,b):
    assert color_key(a) == color_key(b)


def test_shades_and_unknown_colors_are_not_inferred():
    assert color_key('Navy') != color_key('Azul')
    assert color_key('Off White') != color_key('White')
    assert color_key('Black') != color_key('Black + White')
    assert color_key('Green 260') != color_key('Green 270')


def test_search_filter_groups_and_related_share_equivalences(stock_app):
    factory,client,_=stock_app
    with factory() as db:
        rows=[Item(name='Camiseta',sku_internal=f'COLOR-{i}',color=color,brand='Boss',category='Camisetas',group_key='family',size='M',
                   current_stock=1,stock_loja=1,stock_deposito=0) for i,color in enumerate(['Preta','Black','Negro','White','Navy','Azul Marinho'])]
        db.add_all(rows);db.commit();ids=[str(row.id) for row in rows]
        names=[row.color for row in rows]
    for alias in ('preto','black','negra'):
        response=client.get('/api/inventory/items',params={'color':alias})
        assert response.status_code==200,response.text
        assert {r['id'] for r in response.json()['items']}==set(ids[:3])
        response=client.get('/api/inventory/items',params={'search':alias})
        assert response.json()['total']==3,response.text
    assert client.get('/api/inventory/items',params={'search':'navy blue'}).json()['total']==2
    related=client.get(f'/api/inventory/items/{ids[0]}/related',params={'limit':2}).json()
    assert {r['item']['id'] for r in related['items']}==set(ids[1:3])
    with factory() as db:
        assert [db.get(Item,id).color for id in [row.id for row in rows]]==names


def test_color_words_in_brand_or_model_remain_literal(stock_app):
    factory,client,_=stock_app
    with factory() as db:
        db.add(Item(name='Black Label Polo',brand='Red Valentino',sku_internal='BRAND-COLOR',color='Bege'))
        db.commit()
    for query in ('Black Label','Red Valentino'):
        result=client.get('/api/inventory/items',params={'search':query})
        assert result.status_code==200 and result.json()['total']==1,result.text
