import pytest
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles


@compiles(UUID, 'sqlite')
def sqlite_uuid_as_text(element, compiler, **kwargs):
    """SQLite's UUID name has NUMERIC affinity and corrupts numeric/scientific hex.

    Only test schemas use this adapter; production PostgreSQL keeps native UUIDs.
    SQLAlchemy's existing UUID bind/result processors still validate each value.
    """
    return 'CHAR(32)'


@pytest.fixture(autouse=True)
def offline_postal_codes(monkeypatch):
    """No public lookup in unit tests; provider tests explicitly restore the client."""
    from app.services import postal_codes
    monkeypatch.setattr(postal_codes, 'lookup_cep', lambda cep: {'status':'unavailable', 'aviso':'Consulta indisponível no teste.'})
    monkeypatch.setattr('app.services.assistant_tools.lookup_cep', postal_codes.lookup_cep)
