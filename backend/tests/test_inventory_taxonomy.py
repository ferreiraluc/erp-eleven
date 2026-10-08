import importlib.util
import uuid

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg
from app.models.inventory import Item
from app.services.inventory_taxonomy_v1 import canonical, key, vocabulary


@pytest.mark.parametrize('value,field,expected', [
    ('pRADA', 'brand', 'Prada'), ('  PRADA ', 'brand', 'Prada'),
    ('EA7 Empório  Armani', 'brand', 'Emporio Armani'),
    ('Empório Armani', 'brand', 'Emporio Armani'),
    ('CALÇADOS> tênis', 'category', 'Calçados > Tênis'),
    ('calcados > TENIS', 'category', 'Calçados > Tênis'),
    (' AZUL  MARINHO ', 'color', 'Azul Marinho'), ('EA7', 'brand', 'EA7'),
])
def test_canonical(value, field, expected):
    assert canonical(value, field) == expected


def test_conservative_aliases_and_accents():
    assert key('Armani Exchange', 'brand') != key('Emporio Armani', 'brand')
    assert key('Navy', 'color') != key('Azul', 'color')
    assert vocabulary(['HERMES', 'Hermès', 'hermes'], 'brand') == {'hermes': 'Hermès'}


def test_all_orm_writes_normalize_and_api_filters_find_legacy_spellings(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        rows = [Item(name=f'Peça {n}', sku_internal=f'TAX-{n}', brand=brand,
                     category='CALÇADOS> tênis', color='PRETO', group_key=f'grade-{n}')
                for n, brand in enumerate(['PRADA', 'pRADA', 'EA7 Empório Armani', 'Emporio Armani', 'Armani Exchange'])]
        db.add_all(rows); db.commit()
        assert [x.brand for x in rows] == ['Prada', 'Prada', 'Emporio Armani', 'Emporio Armani', 'Armani Exchange']
        assert {x.category for x in rows} == {'Calçados > Tênis'}
        # Simulate old values bypassing ORM; read paths must also handle these.
        db.execute(sa.text("UPDATE inventory_items SET brand='PRADA', category='Calçados > tênis' WHERE sku_internal='TAX-1'")); db.commit()
    assert client.get('/api/inventory/items/distinct-values').json()['brands'] == ['Armani Exchange', 'Emporio Armani', 'Prada']
    for params, count in [({'brand': 'pRADA'}, 2), ({'brand': 'EA7 Empório Armani'}, 2),
                          ({'category': 'calcados > tenis', 'color': 'preto'}, 5),
                          ({'category': 'Calçados'}, 5), ({'brand': '%'}, 0),
                          ({'search': 'EA7 Empório Armani'}, 2)]:
        response = client.get('/api/inventory/items', params=params)
        assert response.status_code == 200, response.text
        assert response.json()['total'] == count, response.text
    assert len(client.get('/api/inventory/groups', params={'brand': 'prada'}).json()) == 2
    with factory() as db:
        row = db.query(Item).filter_by(sku_internal='TAX-0').one()
        row.brand = 'EA7 EMPORIO ARMANI'; db.commit()
        assert row.brand == 'Emporio Armani'
        assert db.query(Item).count() == 5
        assert row.group_key == 'grade-0'


def test_migration_preserves_identity_stock_history_and_deleted_rows(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    from pathlib import Path
    file = Path(__file__).parents[1] / 'alembic/versions/d6e7f8a9b0c1_inventory_taxonomy.py'
    spec = importlib.util.spec_from_file_location('taxonomy_migration', file)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    try:
        with isolated.begin() as conn:
            conn.execute(sa.text('CREATE TABLE inventory_items (id uuid PRIMARY KEY, brand text, category text, color text, deleted_at timestamp, current_stock int, group_key text, updated_at timestamp)'))
            ids = [uuid.uuid4() for _ in range(3)]
            for n, brand in enumerate(['PRADA', 'pRADA', 'PRADA']):
                conn.execute(sa.text("INSERT INTO inventory_items VALUES (:id,:brand,'Calçados> tênis','PRETO',:deleted,7,:grp,'2025-01-01')"),
                             dict(id=ids[n], brand=brand, deleted='2025-02-01' if n == 2 else None, grp=f'g{n}'))
            before = conn.execute(sa.text('SELECT id,current_stock,group_key,updated_at FROM inventory_items ORDER BY id')).all()
            with Operations.context(MigrationContext.configure(conn)):
                module.upgrade()
            assert conn.execute(sa.text('SELECT id,current_stock,group_key,updated_at FROM inventory_items ORDER BY id')).all() == before
            assert conn.execute(sa.text('SELECT DISTINCT brand,category,color FROM inventory_items WHERE deleted_at IS NULL')).all() == [('Prada', 'Calçados > Tênis', 'Preto')]
            assert conn.execute(sa.text('SELECT brand FROM inventory_items WHERE deleted_at IS NOT NULL')).scalar() == 'PRADA'
            assert conn.execute(sa.text('SELECT count(*) FROM inventory_taxonomy_snapshot_v1')).scalar() == 2
    finally:
        isolated.dispose()


def test_bot_and_variant_color_checks_share_taxonomy(manager_stock_app):
    from app.services.assistant_queries import query_stock, StockArgs
    from app.services.assistant_inventory import identity
    from app.services.inventory_variants import same_color_members
    factory, _, _ = manager_stock_app
    with factory() as db:
        rows = [Item(name='Tênis', sku_internal=f'BOT-TAX-{n}', brand='EA7 Empório Armani',
                     category='Calçados > Tênis', color=color, size=size, group_key='same-model',
                     current_stock=1, stock_loja=1, stock_deposito=0)
                for n, (color, size) in enumerate([('AZÚL', 'P'), ('azul', 'M'), ('Preto', 'L')])]
        db.add_all(rows); db.commit()
        result = query_stock(db, StockArgs(termo='EA7 Emporio Armani', categoria='calcados > tenis', cor='azul'))
        assert len(result['resultados']) == 2
        assert len(same_color_members(db, rows[0])) == 2
    assert identity(dict(nome='Polo', marca='EA7 Empório Armani', tamanho='M', cor='AZÚL')) == identity(dict(nome='Polo', marca='Emporio Armani', tamanho='M', cor='azul'))
