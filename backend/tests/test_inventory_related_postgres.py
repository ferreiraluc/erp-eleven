"""Measure actual PostgreSQL reads using 50k synthetic products, never production."""
import json
import time
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session
from test_access_postgres import pg
from test_pdv_unknown_stock import TABLES
from app.database import Base
from app.services.inventory_related import related_products


def test_related_catalog_stays_bounded_on_50000_products(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in TABLES])
        with isolated.begin() as conn:
            conn.exec_driver_sql('''INSERT INTO inventory_items
                (id,name,sku_internal,brand,category,group_key,is_active,
                 current_stock,stock_loja,stock_deposito,created_at,updated_at)
                SELECT md5(g::text)::uuid, 'Produto sintético '||g, 'PERF-'||g,
                    'Marca '||mod(g,100), 'Categoria '||mod(g,50), 'Grade '||(g/20), true,
                    10,10,0,now(),now() FROM generate_series(1,50000) g''')
            # These indexes already exist in production migrations; no new DDL is shipped.
            for column in ('brand', 'category'):
                conn.exec_driver_sql(f'CREATE INDEX ix_inventory_live_{column} ON inventory_items ({column}) WHERE deleted_at IS NULL')
            conn.exec_driver_sql('ANALYZE inventory_items')
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append((statement, parameters))
        sa.event.listen(isolated, 'before_cursor_execute', capture)
        with Session(isolated) as db:
            source_id = uuid.UUID('c4ca4238-a0b9-2382-0dcc-509a6f75849b')  # md5('1')
            start = time.perf_counter()
            first = related_products(db, source_id)
            elapsed = (time.perf_counter() - start) * 1000
            second = related_products(db, source_id, **first['next_cursor'])
        sa.event.remove(isolated, 'before_cursor_execute', capture)
        assert len(first['items']) == len(second['items']) == 12
        assert all(row['relation'] == 'family' for row in first['items'])
        assert any(row['relation'] == 'brand_category' for row in second['items'])
        assert not ({row['item'].id for row in first['items']} & {row['item'].id for row in second['items']})
        assert len(statements) <= 8  # two pages, not one query per product
        assert all('count(' not in sql.lower() and 'additional_images' not in sql for sql, _ in statements)
        with isolated.connect() as conn:
            sql, params = statements[1]
            plan = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + sql, params).scalar()[0]
            assert 'ix_inventory_items_group_key' in json.dumps(plan)
            assert plan['Plan']['Actual Rows'] <= 13
        print(json.dumps({'catalog_size': 50000, 'first_page_ms': round(elapsed, 2),
                          'family_query_ms': plan['Execution Time'], 'queries_for_two_pages': len(statements)}))
    finally:
        isolated.dispose()
