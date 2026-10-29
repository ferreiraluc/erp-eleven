"""USDT migration on disposable PostgreSQL preserves historical payment units."""
import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from test_access_postgres import pg


def test_usdt_currency_migration(pg):
    engine, schema = pg
    with engine.connect() as conn:
        conn.exec_driver_sql(f'SET search_path TO {schema}, public')
        conn.exec_driver_sql('CREATE TABLE pdv_payments (method text, currency varchar(3))')
        conn.exec_driver_sql("INSERT INTO pdv_payments VALUES ('card','USD'),('cash_gs','GS')")
        conn.commit()
        path = Path(__file__).parents[1] / 'alembic/versions/f8a9b0c1d2e3_pdv_usdt_currency.py'
        spec = importlib.util.spec_from_file_location('usdt_migration', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        context = MigrationContext.configure(conn)
        with context.begin_transaction(), Operations.context(context):
            module.upgrade()
        conn.exec_driver_sql("INSERT INTO pdv_payments VALUES ('usdt','USDT')")
        assert conn.exec_driver_sql('SELECT method,currency FROM pdv_payments ORDER BY method').all() == [('card','USD'),('cash_gs','GS'),('usdt','USDT')]
        conn.commit()


def test_card_fee_migration_preserves_historical_payments(pg):
    from decimal import Decimal
    engine, schema = pg
    with engine.connect() as conn:
        conn.exec_driver_sql(f'SET search_path TO {schema}, public')
        conn.exec_driver_sql('CREATE TABLE pdv_payments (id integer PRIMARY KEY, amount_original numeric(15,2), amount_gs numeric(15,2))')
        conn.exec_driver_sql('INSERT INTO pdv_payments VALUES (1,100,100)')
        conn.commit()
        path = Path(__file__).parents[1] / 'alembic/versions/v4e5f6a7b8c9_pdv_card_fee.py'
        spec = importlib.util.spec_from_file_location('card_fee_migration', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with MigrationContext.configure(conn).begin_transaction(), Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert conn.exec_driver_sql('SELECT amount_original,amount_gs,card_fee_gs,card_fee_percent FROM pdv_payments').one() == (100,100,0,0)
        conn.exec_driver_sql('INSERT INTO pdv_payments VALUES (2,497873,468000,29873,6)')
        assert conn.exec_driver_sql('SELECT amount_original-amount_gs,card_fee_gs,card_fee_percent FROM pdv_payments WHERE id=2').one() == (Decimal('29873'),Decimal('29873'),Decimal('6'))
        conn.commit()
