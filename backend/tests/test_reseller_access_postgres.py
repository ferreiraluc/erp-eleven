import uuid

import sqlalchemy as sa
from test_access_postgres import pg, upgrade


def test_reseller_migration_preserves_accounts_and_defaults_existing_and_new_rows(pg):
    engine, schema = pg
    existing, created = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE usuarios(id uuid PRIMARY KEY, nome text NOT NULL, sales_scope text NOT NULL)')
        conn.execute(sa.text('INSERT INTO usuarios VALUES(:id,:name,:scope)'), {'id': existing, 'name': 'Fixture', 'scope': 'own'})
        upgrade(conn, 'c1l2m3n4o5p6_reseller_access.py')
        assert conn.execute(sa.text('SELECT id,nome,sales_scope,access_profile FROM usuarios')).one() == (existing, 'Fixture', 'own', 'standard')
        conn.execute(sa.text('INSERT INTO usuarios(id,nome,sales_scope) VALUES(:id,:name,:scope)'), {'id': created, 'name': 'New fixture', 'scope': 'all'})
        assert conn.execute(sa.text('SELECT access_profile FROM usuarios WHERE id=:id'), {'id': created}).scalar_one() == 'standard'
        column = next(col for col in sa.inspect(conn).get_columns('usuarios', schema=schema) if col['name'] == 'access_profile')
        assert column['nullable'] is False
