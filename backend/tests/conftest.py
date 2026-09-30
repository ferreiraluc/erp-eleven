import pytest


@pytest.fixture(autouse=True)
def offline_postal_codes(monkeypatch):
    """No public lookup in unit tests; provider tests explicitly restore the client."""
    from app.services import postal_codes
    monkeypatch.setattr(postal_codes, 'lookup_cep', lambda cep: {'status':'unavailable', 'aviso':'Consulta indisponível no teste.'})
    monkeypatch.setattr('app.services.assistant_tools.lookup_cep', postal_codes.lookup_cep)
