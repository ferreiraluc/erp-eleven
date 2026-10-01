"""Inventory findings are complete before pagination and never repair records."""
import pytest
from sqlalchemy import update

from test_inventory_ocr import stock_app, setup
from app.models.inventory import Item, StockMovement
from app.services.inventory_diagnostics import diagnose_inventory
from test_access_postgres import pg


def add(db, name, barcode=None, total=3, loja=2, deposito=1, active=True):
    item = Item(name=name, sku_internal=name, barcode=barcode, current_stock=total,
                stock_loja=loja, stock_deposito=deposito, is_active=active, image_data='private-image')
    db.add(item); db.flush()
    return item


def seed(factory):
    with factory() as db:
        add(db, 'Normal', 'ABC')
        add(db, 'Different-case', 'abc')
        add(db, 'Leading-zero', '0123')
        add(db, 'Without-zero', '123')
        add(db, 'Duplicate-A', ' 789\t012 ')
        add(db, 'Duplicate-B', '789012\u00a0')
        add(db, 'Inactive-duplicate', '789012', active=False, total=-9)
        add(db, 'Mismatch', total=10)
        add(db, 'Negative-and-mismatch', total=-1, loja=-2, deposito=0)
        missing = add(db, 'Missing')
        db.execute(update(Item).where(Item.id == missing.id).values(stock_loja=None))
        add(db, 'Blank-code', ' \t\n')
        add(db, 'No-code', None)
        db.commit()


def test_global_counts_pagination_and_unchanged_stock(stock_app):
    factory, client, _ = stock_app; seed(factory)
    response = client.get('/api/inventory/diagnostics?page_size=1')
    assert response.status_code == 200
    result = response.json()
    assert result['total_active_items'] == 11 and result['affected_items'] == 5
    assert result['total_items'] == 5 and len(result['items']) == 1
    assert result['counts'] == dict(stock_mismatch=2, negative_stock=1, missing_stock=1,
                                    duplicate_barcode=2, duplicate_barcode_groups=1)
    assert result['items'][0]['issues'] == ['negative_stock', 'stock_mismatch']
    assert 'image_data' not in result['items'][0] and 'cost_price' not in result['items'][0]
    ids = [client.get(f'/api/inventory/diagnostics?page_size=1&page={p}').json()['items'][0]['id'] for p in range(1, 6)]
    assert len(set(ids)) == 5
    assert client.get('/api/inventory/diagnostics?page=6&page_size=1').json()['items'] == []
    with factory() as db:
        assert db.query(StockMovement).count() == 0
        assert db.query(Item).filter_by(name='Mismatch').one().current_stock == 10
        assert db.query(Item).filter_by(name='Missing').one().stock_loja is None


def test_duplicate_group_survives_search_and_missing_is_not_zero(stock_app):
    factory, client, _ = stock_app; seed(factory)
    result = client.get('/api/inventory/diagnostics?issue=duplicate_barcode&q=Duplicate-A').json()
    assert result['total_items'] == 1 and result['counts']['duplicate_barcode'] == 2
    row = result['items'][0]
    assert row['duplicate_count'] == 2 and row['normalized_barcode'] == '789012'
    missing = client.get('/api/inventory/diagnostics?issue=missing_stock').json()['items'][0]
    assert missing['expected_stock'] is None and missing['delta'] is None
    assert missing['issues'] == ['missing_stock']


def test_literal_search_and_no_findings(stock_app):
    factory, client, _ = stock_app
    empty = client.get('/api/inventory/diagnostics').json()
    assert empty['total_active_items'] == 0 and not any(empty['counts'].values())
    with factory() as db:
        add(db, 'literal_%', total=10); add(db, 'ordinary', total=10); db.commit()
        assert diagnose_inventory(db, q='_%')['total_items'] == 1
        assert diagnose_inventory(db, q='not-present')['total_items'] == 0
    assert client.get('/api/inventory/diagnostics?q=NOT-PRESENT').json()['counts']['stock_mismatch'] == 2


@pytest.mark.parametrize('query', ['issue=unknown', 'page=0', 'page=20001', 'page_size=101', 'q='+'x'*151])
def test_bounded_inputs(stock_app, query):
    _, client, _ = stock_app
    assert client.get('/api/inventory/diagnostics?'+query).status_code == 422


def test_diagnostics_requires_authentication(stock_app):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.endpoints.inventory import router
    app = FastAPI(); app.include_router(router)
    assert TestClient(app).get('/diagnostics').status_code == 401


def test_postgres_diagnostic_keeps_large_sums_and_normalized_groups(pg):
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Usuario, Vendedor
    from app.models.inventory import Supplier
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (Usuario, Vendedor, Supplier, Item)])
        factory = sessionmaker(bind=isolated)
        with factory() as db:
            add(db, 'Large', '001\t23', total=2_147_483_647, loja=2_147_483_647, deposito=2_147_483_647)
            add(db, 'Second', '00123\u00a0')
            add(db, 'Different-code', '123')
            db.commit()
            data = diagnose_inventory(db, page_size=1)
            assert data['affected_items'] == 2 and data['counts']['duplicate_barcode_groups'] == 1
            assert data['items'][0]['expected_stock'] == 4_294_967_294
            assert data['items'][0]['delta'] == -2_147_483_647
            assert data['items'][0]['duplicate_count'] == 2
            assert not db.new and not db.dirty and not db.deleted
    finally:
        isolated.dispose()
