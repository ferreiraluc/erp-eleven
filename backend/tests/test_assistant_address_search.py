"""Typos suggest real addresses without matching sender blocks or creating prints."""
from datetime import datetime, timedelta, timezone
import uuid

import pytest

from test_access_postgres import pg
from test_assistant_tracking_name_search import tracking_db
from app.database import Base
from app.models import Usuario
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente
from app.models.printing import PrintDevice, PrintJob
from app.services.assistant_address_search import address_queries


@pytest.fixture
def address_db(tracking_db):
    db = tracking_db
    Base.metadata.create_all(db.get_bind(), tables=[m.__table__ for m in (PdvCliente, SavedAddress, PrintDevice, PrintJob)])
    user = Usuario(nome='Synthetic', email='synthetic@example.test', senha_hash='not-used')
    device = PrintDevice(name='Synthetic offline', token_hash='synthetic-only')
    db.add_all([user, device]); db.flush()
    def add(name, *, active=True, source='erp', sender='Outro nome', street='Rua Exemplo 100'):
        address = SavedAddress(label=name, data={'nome': name, 'endereco': street}, created_by=user.id, active=active)
        db.add(address); db.flush()
        db.add(PrintJob(device_id=device.id, user_id=user.id, request_key=uuid.uuid4(), source=source,
            snapshot={'editor': {'nome': name, 'endereco': street}, 'remetente': {'nome': sender}},
            pdf=b'synthetic', sha256='test', status='printed', expires_at=datetime.now(timezone.utc)+timedelta(days=1)))
        db.flush()
        return address
    return db, add


def test_shortened_and_misspelled_recipient_search_both_real_sources(address_db):
    db, add = address_db
    address = add('Murillo de Almeida Muniz')
    for term, expected_approximate in [('Murillo Muniz', False), ('Murilo Muniz', True)]:
        addresses, jobs, approximate = address_queries(db, term)
        assert [row.id for row in addresses] == [address.id]
        assert jobs.count() == 1 and approximate == expected_approximate
    assert db.query(PrintJob).count() == 1  # read-only lookup


def test_exact_addresses_suppress_similar_other_recipients(address_db):
    db, add = address_db
    exact = add('Murilo Almeida')
    add('Murillo Souza')
    addresses, jobs, approximate = address_queries(db, 'Murilo')
    assert [row.id for row in addresses] == [exact.id]
    assert jobs.count() == 1 and not approximate


def test_fuzzy_lookup_never_matches_sender_or_street_only(address_db):
    db, add = address_db
    add('Pedro Souza', sender='Murillo Almeida', street='Rua Murillo 100')
    addresses, jobs, _ = address_queries(db, 'Murilo')
    assert addresses.count() == jobs.count() == 0


def test_inactive_and_other_print_sources_are_not_suggested(address_db):
    db, add = address_db
    add('Murillo Almeida', active=False, source='inventory_list')
    addresses, jobs, _ = address_queries(db, 'Murilo')
    assert addresses.count() == jobs.count() == 0


def test_approximate_results_preserve_candidates_instead_of_selecting_one(address_db):
    db, add = address_db
    add('Murillo Almeida'); add('Murilo Souza')
    addresses, jobs, approximate = address_queries(db, 'Murilio')
    assert approximate and addresses.count() == jobs.count() == 2
