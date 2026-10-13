"""Migration validation in isolated PostgreSQL, preserving legacy jobs/snapshots."""
from test_access_postgres import pg, upgrade


def test_print_diagnostic_migration_preserves_history(pg):
    engine, schema = pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE print_jobs (id integer, status text, snapshot json, pdf bytea)')
        conn.exec_driver_sql("INSERT INTO print_jobs VALUES (1,'uncertain','{\"layout\":{}}','\\x25504446')")
        before = conn.exec_driver_sql('SELECT id,status,snapshot,pdf FROM print_jobs').one()
        upgrade(conn, 'g9b0c1d2e3f4_print_diagnostics.py')
        assert conn.exec_driver_sql('SELECT id,status,snapshot,pdf FROM print_jobs').one() == before
        assert conn.exec_driver_sql('SELECT diagnostic FROM print_jobs').scalar() is None
        conn.exec_driver_sql("UPDATE print_jobs SET diagnostic='{\"code\":\"renderer_timeout\"}'")
        assert conn.exec_driver_sql('SELECT diagnostic FROM print_jobs').scalar() == {'code': 'renderer_timeout'}
