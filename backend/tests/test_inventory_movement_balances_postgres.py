"""The additive movement migration never invents or removes historical balances."""
import importlib.util
from datetime import datetime
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa

from test_access_postgres import pg


def migration_module():
    path = (Path(__file__).parents[1] / 'alembic' / 'versions' /
            'w5f6a7b8c9d0_stock_movement_store_balances.py')
    spec = importlib.util.spec_from_file_location('store_balances_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_store_balances_upgrade_preserves_legacy_rows_and_rolling_old_writers(pg):
    engine, schema = pg
    migration = migration_module()
    item_id = uuid.uuid4()
    legacy_rows = [
        dict(id=uuid.uuid4(), item_id=item_id, movement_type='exit', quantity=1,
             quantity_before=6, quantity_after=5, location_from='loja', location_to=None,
             reason='Venda sintética', reference_type='pdv_sale', reference_id='fixture-sale',
             notes='Histórico original', created_at=datetime(2026, 10, 20, 12, 30)),
        # These combined totals cannot distinguish a store depletion from repair
        # of an inconsistent combined total while the store was already empty.
        dict(id=uuid.uuid4(), item_id=item_id, movement_type='adjustment', quantity=0,
             quantity_before=7, quantity_after=5, location_from='loja', location_to=None,
             reason='Ajuste sintético', reference_type=None, reference_id=None,
             notes=None, created_at=datetime(2026, 10, 21, 12, 30)),
        dict(id=uuid.uuid4(), item_id=item_id, movement_type='entry', quantity=5,
             quantity_before=0, quantity_after=5, location_from=None, location_to=None,
             reason='Importação CSV', reference_type=None, reference_id=None,
             notes='Sem localização no registro antigo', created_at=datetime(2026, 10, 22, 12, 30)),
    ]
    original_columns = tuple(legacy_rows[0])
    insert = sa.text('INSERT INTO stock_movements (' + ','.join(original_columns) + ') VALUES (' +
                     ','.join(':' + name for name in original_columns) + ')')
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('''CREATE TABLE stock_movements(
            id uuid PRIMARY KEY, item_id uuid NOT NULL, movement_type text NOT NULL,
            quantity integer NOT NULL, quantity_before integer NOT NULL, quantity_after integer NOT NULL,
            location_from text, location_to text, reason text, reference_type text,
            reference_id text, notes text, created_at timestamp)''')
        conn.execute(insert, legacy_rows)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()

        columns = {column['name']: column for column in sa.inspect(conn).get_columns('stock_movements')}
        for name in ('stock_loja_before', 'stock_loja_after'):
            assert columns[name]['nullable'] is True
            assert columns[name]['default'] is None
            assert isinstance(columns[name]['type'], sa.Integer)
        before = {row['id']: row for row in legacy_rows}
        result = conn.execute(sa.text('SELECT * FROM stock_movements')).mappings().all()
        assert len(result) == len(legacy_rows)
        for row in result:
            assert {name: row[name] for name in original_columns} == before[row['id']]
            assert row['stock_loja_before'] is row['stock_loja_after'] is None

        # During a rolling release the old application can still insert its
        # original shape. Missing store evidence remains unknown, never zero.
        old_writer = dict(legacy_rows[0], id=uuid.uuid4())
        conn.execute(insert, old_writer)
        assert conn.execute(sa.text('''SELECT stock_loja_before, stock_loja_after
            FROM stock_movements WHERE id=:id'''), {'id': old_writer['id']}).one() == (None, None)

        # New explicit evidence and all old rows survive a refused downgrade.
        new_writer = dict(legacy_rows[0], id=uuid.uuid4())
        conn.execute(insert, new_writer)
        conn.execute(sa.text('''UPDATE stock_movements SET stock_loja_before=1, stock_loja_after=0
            WHERE id=:id'''), {'id': new_writer['id']})
        snapshot = conn.execute(sa.text('SELECT * FROM stock_movements ORDER BY id')).all()
        with Operations.context(MigrationContext.configure(conn)), pytest.raises(RuntimeError, match='Preserve recorded store balances'):
            migration.downgrade()
        assert conn.execute(sa.text('SELECT * FROM stock_movements ORDER BY id')).all() == snapshot
