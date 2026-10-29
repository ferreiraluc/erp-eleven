"""Customer pages search the full directory without exposing merged aliases."""
import uuid

import pytest

from test_assistant import setup
from test_customer_links import logistics
from app.models import Cliente
from app.database import Base
from app.models.address_book import SavedAddress
from app.models.printing import PrintDevice, PrintJob


@pytest.fixture(autouse=True)
def activity_tables(logistics):
    factory, _, _ = logistics
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[SavedAddress.__table__, PrintDevice.__table__, PrintJob.__table__])


def seed(factory):
    with factory() as db:
        active = [Cliente(nome=f'Cliente QA {i:03}', ativo=True) for i in range(225)]
        inactive = [Cliente(nome=f'Inativo QA {i:03}', ativo=False) for i in range(25)]
        active[-1].telefone = 'Telefone final QA'
        active[-2].cpf = 'DOC-FINAL-QA'
        active[-3].email = 'final@example.test'
        active[-4].endereco = 'Rua final QA 100%_\\'
        inactive[-1].email = 'final@example.test'
        db.add_all(active + inactive); db.flush()
        db.add_all([
            Cliente(nome='Alias QA com e-mail', email='final@example.test', ativo=False, merged_into_id=active[0].id),
            Cliente(nome='Alias QA inativo', ativo=False, merged_into_id=active[0].id),
        ])
        db.commit()


def page(client, **params):
    response = client.get('/api/clientes/pagina', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_customer_pages_cover_beyond_two_hundred_with_no_overlaps(logistics):
    factory, client, _ = logistics
    seed(factory)
    seen = set()
    for number in range(1, 13):
        result = page(client, page=number)
        assert result['total'] == 225
        assert result['page'] == number and result['page_size'] == 20
        assert len(result['items']) == (20 if number < 12 else 5)
        ids = {row['id'] for row in result['items']}
        assert seen.isdisjoint(ids)
        seen |= ids
    assert len(seen) == 225
    assert result['items'][-1]['nome'] == 'Cliente QA 224'
    outside = page(client, page=13)
    assert outside['total'] == 225 and outside['items'] == []


@pytest.mark.parametrize(('params', 'total', 'last_count'), [
    ({}, 225, 5),
    ({'ativo': False}, 25, 5),
    ({'include_inactive': True}, 250, 10),
    ({'include_inactive': True, 'ativo': False}, 250, 10),
])
def test_status_filters_count_the_complete_set_and_hide_aliases(logistics, params, total, last_count):
    factory, client, _ = logistics
    seed(factory)
    result = page(client, page=(total + 19) // 20, **params)
    assert result['total'] == total and len(result['items']) == last_count
    assert not any('Alias' in row['nome'] for row in result['items'])
    # Confirmed alias names are searchable, but only the active principal card
    # is returned. An inactive-only filter never reveals the merged aliases.
    aliases = page(client, search='Alias', **params)
    expected = 0 if params.get('ativo') is False and not params.get('include_inactive') else 1
    assert aliases['total'] == expected
    assert [row['nome'] for row in aliases['items']] == (['Cliente QA 000'] if expected else [])


@pytest.mark.parametrize(('search', 'name'), [
    ('Cliente QA 224', 'Cliente QA 224'),
    ('telefone final qa', 'Cliente QA 224'),
    ('DOC-FINAL-QA', 'Cliente QA 223'),
    ('final@example.test', 'Cliente QA 222'),
    ('  Rua final QA  ', 'Cliente QA 221'),
    ('%', 'Cliente QA 221'),
    ('_', 'Cliente QA 221'),
    ('\\', 'Cliente QA 221'),
])
def test_search_covers_all_fields_before_counting_and_paging(logistics, search, name):
    factory, client, _ = logistics
    seed(factory)
    result = page(client, search=search, page_size=1)
    expected_names = ['Cliente QA 000', name] if search == 'final@example.test' else [name]
    assert result['total'] == len(expected_names) and result['items'][0]['nome'] == expected_names[0]
    if len(expected_names) == 2:
        assert page(client, search=search, page=2, page_size=1)['items'][0]['nome'] == expected_names[1]
    assert page(client, search=search, page=len(expected_names) + 1, page_size=1)['items'] == []


def test_combined_search_and_status_legacy_contract_and_literal_queries(logistics):
    factory, client, _ = logistics
    seed(factory)
    all_matches = page(client, search='final@example.test', include_inactive=True, page_size=1)
    assert all_matches['total'] == 3
    assert all_matches['items'][0]['nome'] == 'Cliente QA 000'
    inactive = page(client, search='final@example.test', ativo=False)
    assert inactive['total'] == 1 and inactive['items'][0]['nome'] == 'Inativo QA 024'
    assert page(client, search="' OR 1=1 --")['total'] == 0
    assert page(client, search='   ')['total'] == 225
    legacy = client.get('/api/clientes/', params={'skip': 200, 'limit': 100}).json()
    assert isinstance(legacy, list) and len(legacy) == 25
    assert legacy[-1]['nome'] == 'Cliente QA 224'


def test_same_name_order_has_stable_id_tiebreaker(logistics):
    factory, client, _ = logistics
    with factory() as db:
        for i in (3, 1, 2):
            db.add(Cliente(id=uuid.UUID(f'aa000000-0000-0000-0000-{i:012d}'), nome='Homônimo QA', ativo=True))
        db.commit()
    for number in (1, 2, 3):
        result = page(client, page=number, page_size=1)
        assert result['total'] == 3
        assert result['items'][0]['id'] == f'aa000000-0000-0000-0000-{number:012d}'


def test_customer_page_validation_and_auth(logistics):
    _, client, _ = logistics
    for params in ({'page': 0}, {'page_size': 0}, {'page_size': 101}, {'search': 'x' * 201},
                   {'ativo': 'invalid'}, {'include_inactive': 'invalid'}):
        assert client.get('/api/clientes/pagina', params=params).status_code == 422
    client.app.dependency_overrides.clear()
    assert client.get('/api/clientes/pagina').status_code in (401, 403)
