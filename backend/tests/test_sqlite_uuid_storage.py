"""Test-only SQLite UUID storage must preserve all valid PostgreSQL UUIDs."""
import uuid

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, Table, create_engine, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql import UUID


@pytest.mark.parametrize('value', [
    '1475e396-4548-4354-9038-630928050254',  # SQLite NUMERIC affinity reads the hex as infinity.
    '00000000-0000-4000-8000-000000000001',  # Numeric hex must preserve leading zeros.
    '12345678-1234-4123-8123-123456789123',
])
def test_sqlite_uuid_round_trip_keeps_text_and_foreign_key_identity(value):
    key = uuid.UUID(value)
    metadata = MetaData()
    parent = Table('uuid_parent', metadata, Column('id', UUID(as_uuid=True), primary_key=True))
    child = Table('uuid_child', metadata, Column('id', UUID(as_uuid=True), primary_key=True),
                  Column('parent_id', UUID(as_uuid=True), ForeignKey('uuid_parent.id'), nullable=False))
    engine = create_engine('sqlite://')
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(parent.insert().values(id=key))
            connection.execute(child.insert().values(id=uuid.uuid4(), parent_id=key))
        with engine.connect() as connection:
            assert connection.execute(select(parent.c.id)).scalar_one() == key
            assert connection.execute(select(child.c.parent_id).join(parent).where(parent.c.id == key)).scalar_one() == key
            assert connection.execute(text('SELECT typeof(id), id FROM uuid_parent')).one() == ('text', key.hex)
    finally:
        engine.dispose()


def test_sqlite_compatibility_compiler_does_not_change_postgresql_uuid_type():
    assert UUID(as_uuid=True).compile(dialect=sqlite.dialect()) == 'CHAR(32)'
    assert UUID(as_uuid=True).compile(dialect=postgresql.dialect()) == 'UUID'
