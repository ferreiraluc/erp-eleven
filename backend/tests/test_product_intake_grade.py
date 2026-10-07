"""Unified intake uses the existing stock API with explicit, reviewed variant data."""
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_assistant import setup
from test_inventory_ocr import stock_app
from test_access_postgres import pg
from app.api.endpoints import inventory
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, Supplier, StockMovement
from app.schemas.inventory import GradeCreateRequest
from app.services.inventory_service import StockMovementError


@pytest.fixture
def manager_stock_app(stock_app):
    factory, _, user_id = stock_app
    with factory() as db:
        db.get(Usuario, user_id).role = UsuarioRole.GERENTE
        db.commit()
    return stock_app


def test_grade_creation_still_rejects_unauthorized_roles(stock_app):
    factory, client, _ = stock_app
    response = client.post('/api/inventory/items/grade', json={'name': 'Polo', 'sizes': ['P', 'M']})
    assert response.status_code == 403
    with factory() as db:
        assert db.query(Item).count() == 0


def test_intake_grade_uses_size_suffixed_barcode_and_shared_fields_and_deduplicates_sizes(manager_stock_app):
    factory, client, _ = manager_stock_app
    result = client.post('/api/inventory/items/grade', json={
        'name': 'Polo', 'brand': 'Marca teste', 'color': 'Branco', 'description': 'Modelo conferido',
        'sizes': [' P ', 'M', 'L', 'XL', '2XL', 'p'], 'base_barcode': '4006381333931',
        'initial_stock': 2, 'stock_location': 'deposito',
        'image_data': 'data:image/jpeg;base64,fixture', 'group_key': 'intake-reviewed-model',
    })
    assert result.status_code == 201, result.text
    rows = result.json()['items']
    assert len(rows) == 5
    assert [r['size'] for r in rows] == ['P', 'M', 'L', 'XL', '2XL']
    assert len({r['sku_internal'] for r in rows}) == 5
    for row in rows:
        assert row['barcode'] == '4006381333931' + row['size']
        assert row['color'] == 'Branco' and row['brand'] == 'Marca Teste'
        assert row['image_data'] == 'data:image/jpeg;base64,fixture'
        assert row['group_key'] == 'intake-reviewed-model'
        assert (row['current_stock'], row['stock_loja'], row['stock_deposito']) == (2, 0, 2)
    with factory() as db:
        assert db.query(StockMovement).count() == 5


def test_legacy_grade_barcode_contract_and_zero_stock_are_preserved(manager_stock_app):
    factory, client, _ = manager_stock_app
    result = client.post('/api/inventory/items/grade', json={'name': 'Modelo', 'sizes': ['P', 'M'], 'base_barcode': 'LEGACY'})
    assert result.status_code == 201, result.text
    assert [r['barcode'] for r in result.json()['items']] == ['LEGACYP', 'LEGACYM']
    with factory() as db:
        assert db.query(StockMovement).count() == 0


@pytest.mark.parametrize('fail_second', [False, True])
def test_grade_and_initial_movements_commit_or_rollback_together_on_postgresql(pg, monkeypatch, fail_second):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (Usuario, Vendedor, Supplier, Item, StockMovement)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        user_id = uuid.uuid4()
        with factory() as db:
            db.add(Usuario(id=user_id, nome='Fixture', email='fixture@example.com', senha_hash='unused'))
            db.commit()
        original = inventory.create_movement
        calls = 0
        def movement(**kwargs):
            nonlocal calls
            calls += 1
            if fail_second and calls == 2:
                raise StockMovementError('Simulated entry failure', status_code=409)
            return original(**kwargs)
        monkeypatch.setattr(inventory, 'create_movement', movement)
        with factory() as db:
            user = db.get(Usuario, user_id)
            args = GradeCreateRequest(name='Polo', color='Branco', sizes=['P', 'M'], initial_stock=3,
                                      base_barcode='4006381333931')
            if fail_second:
                with pytest.raises(StockMovementError):
                    inventory.create_grade(args, db, user)
            else:
                inventory.create_grade(args, db, user)
        with factory() as db:
            assert db.query(Item).count() == (0 if fail_second else 2)
            assert db.query(StockMovement).count() == (0 if fail_second else 2)
            for row in db.query(Item):
                assert (row.current_stock, row.stock_loja, row.stock_deposito) == (3, 3, 0)
    finally:
        isolated.dispose()
