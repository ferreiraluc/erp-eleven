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
            barcode varchar(200), image_data text, updated_at timestamp, deleted_at timestamptz,
            description text, inventory_code varchar(10))''')
        conn.exec_driver_sql('''INSERT INTO inventory_items
            SELECT md5(g::text)::uuid, CASE WHEN g=77 THEN 'Tênis Givenchy DN0281' ELSE 'Camiseta modelo '||g END,
            CASE WHEN g=77 THEN 'Givenchy' ELSE 'Boss' END, 'Vestuário', 'Preto', 'M', NULL,
            'INV-'||g, NULL, NULL, now(), NULL,
            CASE WHEN g IN (80,81) THEN 'Camiseta de placa de metal, com logo emborrachado e algodão'
                 ELSE 'Peça com costura reforçada, modelo '||g END, NULL
            FROM generate_series(1,50000) g''')
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
        path = Path(__file__).parents[1] / 'alembic/versions/l4a5b6c7d8e9_inventory_description_search.py'
        spec = importlib.util.spec_from_file_location('description_migration', path)
        description_migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(description_migration)
        with context.begin_transaction(), Operations.context(context):
            description_migration.upgrade()
        from test_inventory_codes import upgrade
        upgrade(conn, 'm5b6c7d8e9f0_inventory_public_codes.py')
        after = plan()
        assert before['Plan']['Actual Rows'] == after['Plan']['Actual Rows'] == 1
        assert 'ix_inventory_search_trgm' in json.dumps(after), after
        print(json.dumps({'rows': 50000, 'before_ms': before['Execution Time'], 'after_ms': after['Execution Time'],
                          'indexed_plan': after['Plan']['Node Type']}))
        conn.exec_driver_sql("""UPDATE inventory_items SET name='Tshirt Armani AF16548 UB102 2XL',
            brand='Emporio Armani' WHERE sku_internal='INV-78'""")
        conn.exec_driver_sql("""UPDATE inventory_items SET name='T-shirt Boss Y-26-09 L'
            WHERE sku_internal='INV-79'""")
        conn.exec_driver_sql('ANALYZE inventory_items')
        conn.commit()
        for term in ('8UB102', 'AF 16548', 'Y 26', 'Emprio Armani'):
            with Session(bind=conn) as db:
                searched = build_search(db, term)
                query = sa.select(Item.id).where(Item.deleted_at.is_(None), searched.condition).order_by(searched.rank)
                sql = str(query.compile(conn, compile_kwargs={'literal_binds': True}))
                measured = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql).scalar()[0]
                assert measured['Plan']['Actual Rows'] == 1, (term, measured)
                # Longer code fragments remain indexable. Very short Y/26 has
                # no three-character fragment and can legitimately use a scan.
                if term in ('8UB102', 'AF 16548'):
                    assert 'ix_inventory_search_trgm' in json.dumps(measured), measured
                print(json.dumps({'search': term, 'rows': 50000, 'execution_ms': measured['Execution Time'],
                                  'planning_ms': measured['Planning Time']}))
        for term in ('placa', 'metal emborrachado', 'algodao', 'Boss placa M'):
            with Session(bind=conn) as db:
                searched = build_search(db, term)
                base = sa.select(Item.id).where(Item.deleted_at.is_(None), searched.condition)
                # Real pagination/order and total count both use the description index.
                for query in (base.order_by(searched.rank, Item.name, Item.id).limit(50),
                              sa.select(sa.func.count()).select_from(base.subquery())):
                    sql = str(query.compile(conn, compile_kwargs={'literal_binds': True}))
                    measured = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql).scalar()[0]
                    assert 'ix_inventory_description_trgm' in json.dumps(measured), measured
                    print(json.dumps({'search': term, 'rows': 50000, 'execution_ms': measured['Execution Time'],
                                      'planning_ms': measured['Planning Time']}))
                assert len(conn.execute(base).all()) == 2
        code = conn.exec_driver_sql("SELECT inventory_code FROM inventory_items WHERE sku_internal='INV-77'").scalar()
        for term in (code, code[4:].lower()):
            with Session(bind=conn) as db:
                searched = build_search(db, term)
                query = sa.select(Item.id).where(Item.deleted_at.is_(None), searched.condition)
                assert len(conn.execute(query).all()) == 1
                sql = str(query.compile(conn, compile_kwargs={'literal_binds': True}))
                measured = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql).scalar()[0]
                assert 'ix_inventory_public_code' in json.dumps(measured)
        conn.exec_driver_sql("UPDATE inventory_items SET description='Bordado exclusivo' WHERE sku_internal='INV-80'")
        with Session(bind=conn) as db:
            for term, expected in [('placa', 1), ('bordado', 1)]:
                searched = build_search(db, term)
                assert conn.execute(sa.select(sa.func.count()).select_from(Item).where(
                    Item.deleted_at.is_(None), searched.condition)).scalar() == expected
        conn.commit()
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
            description_migration.upgrade()
        assert conn.exec_driver_sql('SELECT count(*) FROM inventory_items').scalar() == 50000
        conn.commit()
