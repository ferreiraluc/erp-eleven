import re
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
import sqlalchemy as sa
from test_access_postgres import pg
from alembic.migration import MigrationContext
from alembic.operations import Operations
import importlib.util
from pathlib import Path

def upgrade(conn, filename):
    spec = importlib.util.spec_from_file_location("code_migration", Path(__file__).parents[1] / "alembic/versions" / filename)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    context = MigrationContext.configure(conn)
    with context.begin_transaction(), Operations.context(context): migration.upgrade()
from app.inventory_codes import encode_number, CAPACITY


def test_short_codes_have_six_readable_symbols_and_do_not_collide():
    codes = {encode_number(n) for n in range(1, 50001)}
    assert len(codes) == 50000
    assert all(re.fullmatch(r'INV-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}', code) for code in codes)
    assert encode_number(CAPACITY) not in codes
    for n in (0, CAPACITY + 1):
        with pytest.raises(ValueError): encode_number(n)


def test_backfill_preserves_identity_history_and_codes_survive_restart_and_concurrent_inserts(pg):
    engine, schema = pg
    with engine.connect() as conn:
        conn.exec_driver_sql(f'SET search_path TO {schema}, public')
        conn.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public')
        conn.exec_driver_sql('''CREATE TABLE inventory_items(id uuid PRIMARY KEY, sku_internal text UNIQUE,
            name text, stock_loja integer, image_data text, updated_at timestamp, deleted_at timestamp)''')
        conn.exec_driver_sql('''INSERT INTO inventory_items SELECT md5(g::text)::uuid, 'OLD-'||g, 'Produto '||g,
            g, 'photo-'||g, '2026-01-01'::timestamp, NULL FROM generate_series(1,1203) g''')
        conn.exec_driver_sql('CREATE TABLE history(item_id uuid REFERENCES inventory_items(id), detail text)')
        conn.exec_driver_sql("INSERT INTO history SELECT id, 'Histórico' FROM inventory_items")
        before = conn.exec_driver_sql('SELECT * FROM inventory_items ORDER BY id').all()
        conn.commit()
        upgrade(conn, 'm5b6c7d8e9f0_inventory_public_codes.py')
        codes = conn.exec_driver_sql('SELECT inventory_code FROM inventory_items ORDER BY id').scalars().all()
        assert len(set(codes)) == 1203 and None not in codes
        assert conn.exec_driver_sql('SELECT id,sku_internal,name,stock_loja,image_data,updated_at,deleted_at FROM inventory_items ORDER BY id').all() == before
        assert conn.exec_driver_sql('SELECT count(*) FROM history JOIN inventory_items ON item_id=id').scalar() == 1203
        conn.commit()
        upgrade(conn, 'm5b6c7d8e9f0_inventory_public_codes.py')
        assert conn.exec_driver_sql('SELECT inventory_code FROM inventory_items ORDER BY id').scalars().all() == codes
        # PostgreSQL and Python encode the same sequence values.
        n = conn.exec_driver_sql('SELECT last_value FROM inventory_code_seq').scalar() + 1
        assert conn.exec_driver_sql('SELECT next_inventory_code()').scalar() == encode_number(n)
        conn.commit()
    def insert(n):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}, public')
            return conn.execute(sa.text('INSERT INTO inventory_items(id,sku_internal) VALUES(:id,:sku) RETURNING inventory_code'),
                                {'id': uuid.uuid4(), 'sku': f'NEW-{n}'}).scalar()
    with ThreadPoolExecutor(max_workers=8) as pool:
        new_codes = list(pool.map(insert, range(80)))
    assert len(set(new_codes)) == 80
    assert not set(codes) & set(new_codes)
