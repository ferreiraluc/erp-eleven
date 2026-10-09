"""Actual migrations/plans on disposable PostgreSQL, never production."""
import importlib.util
import json
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from test_access_postgres import pg
from app.models.inventory import Item
from app.services.inventory_search import build_search


def test_indexed_search_and_photo_cache_invalidation(pg):
    engine, schema = pg
    with engine.connect() as conn:
        conn.exec_driver_sql(f'SET search_path TO {schema}, public')
        conn.exec_driver_sql('''CREATE TABLE inventory_items (
            id uuid PRIMARY KEY, name varchar(200), brand varchar(100), category varchar(100),
            color varchar(50), size varchar(50), group_key varchar(100), sku_internal varchar(50),
            barcode varchar(200), image_data text, updated_at timestamp, deleted_at timestamptz)''')
        conn.exec_driver_sql('''INSERT INTO inventory_items
            SELECT md5(g::text)::uuid, CASE WHEN g=77 THEN 'Tênis Givenchy DN0281' ELSE 'Camiseta modelo '||g END,
            CASE WHEN g=77 THEN 'Givenchy' ELSE 'Boss' END, 'Vestuário', 'Preto', 'M', NULL,
            'INV-'||g, NULL, NULL, now(), NULL FROM generate_series(1,10000) g''')
        conn.exec_driver_sql('ANALYZE inventory_items')
        conn.commit()
        def plan():
            with Session(bind=conn) as db:
                searched = build_search(db, 'DN0281')
                query = sa.select(Item.id).where(Item.deleted_at.is_(None), searched.condition)
                sql = str(query.compile(conn, compile_kwargs={'literal_binds': True}))
                return conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql).scalar()[0]
        before = plan()
        conn.commit()
        path = Path(__file__).parents[1] / 'alembic/versions/e7f8a9b0c1d2_inventory_performance.py'
        spec = importlib.util.spec_from_file_location('perf_migration', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        context = MigrationContext.configure(conn)
        with context.begin_transaction(), Operations.context(context):
            migration.upgrade()
        after = plan()
        assert before['Plan']['Actual Rows'] == after['Plan']['Actual Rows'] == 1
        assert 'ix_inventory_search_trgm' in json.dumps(after), after
        print(json.dumps({'rows': 10000, 'before_ms': before['Execution Time'], 'after_ms': after['Execution Time'],
                          'indexed_plan': after['Plan']['Node Type']}))
        assert not conn.exec_driver_sql('''SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() AND NOT i.indisvalid''').scalar()
        conn.exec_driver_sql("UPDATE inventory_items SET thumbnail_data='cached', thumbnail_ready=true WHERE sku_internal='INV-77'")
        conn.exec_driver_sql("UPDATE inventory_items SET name='Novo nome' WHERE sku_internal='INV-77'")
        assert conn.exec_driver_sql("SELECT thumbnail_ready FROM inventory_items WHERE sku_internal='INV-77'").scalar()
        conn.exec_driver_sql("UPDATE inventory_items SET image_data='new original' WHERE sku_internal='INV-77'")
        assert conn.exec_driver_sql("SELECT thumbnail_data IS NULL AND NOT thumbnail_ready FROM inventory_items WHERE sku_internal='INV-77'").scalar()
        conn.commit()
        # Startup can retry after a concurrent index build committed independently.
        with context.begin_transaction(), Operations.context(context):
            migration.upgrade()
        assert conn.exec_driver_sql('SELECT count(*) FROM inventory_items').scalar() == 10000
        conn.commit()
