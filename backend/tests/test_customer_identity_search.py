"""Portable literal lookup of typed documents and confirmed identity chains."""
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_customer_links import logistics
from test_assistant import setup
from app.database import Base
from app.models import Cliente, Usuario, Vendedor
from app.models.pdv import PdvCliente
from app.models.address_book import SavedAddress
from app.models.printing import PrintDevice, PrintJob
from app.services.customer_search import directory_match
from app.services.pdv_customers import search


@pytest.fixture(params=['sqlite', 'postgres'])
def identity_search_db(request):
    if request.param == 'postgres':
        engine, schema = request.getfixturevalue('pg')
        isolated = sa.create_engine(engine.url, connect_args={
            'options': f'-csearch_path={schema} -cstatement_timeout=5000'})
    else:
        isolated = sa.create_engine('sqlite://')
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
        Usuario, Vendedor, Cliente, PdvCliente, SavedAddress,
    )])
    try:
        with sessionmaker(bind=isolated, autoflush=False)() as db:
            yield db
    finally:
        isolated.dispose()


def seed(db):
    ci = Cliente(nome='Ana Lopez', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '3.456.789'}])
    ruc = Cliente(nome='Diego Gomez', documentos=[{'tipo': 'RUC', 'pais': 'PY', 'numero': '800.12345-6'}])
    rg = Cliente(nome='Bruno Souza', documentos=[{'tipo': 'RG', 'pais': 'BR', 'numero': 'AB-12.345-X', 'emissor': 'SSP-SP'}])
    cpf = Cliente(nome='Pedro Ramos', cpf='529.982.247-25')
    principal = Cliente(nome='Maria Gomez')
    literal = Cliente(nome='Oferta 123%_\\ Original')
    db.add_all([ci, ruc, rg, cpf, principal, literal]); db.flush()
    middle = Cliente(nome='Maria Intermediaria', ativo=False, merged_into_id=principal.id,
        documentos=[{'tipo': 'RUC', 'pais': 'PY', 'numero': '900.87654-3'}])
    db.add(middle); db.flush()
    old = Cliente(nome='Nome Antigo Confirmado', ativo=False, merged_into_id=middle.id,
        documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': 'B-98.765'}])
    db.add(old); db.flush()
    return {'ci': ci, 'ruc': ruc, 'rg': rg, 'cpf': cpf, 'principal': principal,
        'middle': middle, 'old': old, 'literal': literal}


def lookup(db, query):
    return db.query(Cliente).filter(Cliente.merged_into_id.is_(None), directory_match(query)).order_by(Cliente.id).all()


@pytest.mark.parametrize('query,kind', [('3456789', 'ci'), ('3.456.789', 'ci'), ('800123456', 'ruc'),
    ('800.12345-6', 'ruc'), ('AB12345X', 'rg'), ('ab-12.345-x', 'rg'), ('52998224725', 'cpf'),
    ('529.982.247-25', 'cpf')])
def test_typed_documents_and_formatted_legacy_cpf_match_with_or_without_punctuation(identity_search_db, query, kind):
    db = identity_search_db
    rows = seed(db)
    assert [row.id for row in lookup(db, query)] == [rows[kind].id]
    assert [(row['source'], row['id']) for row in search(db, query)['items']] == [('cadastro', rows[kind].id)]


@pytest.mark.parametrize('query', ['Nome Antigo Confirmado', 'Maria Intermediaria', 'B98765', 'B-98.765',
    '900876543', '900.87654-3'])
def test_alias_chain_name_and_document_return_only_principal_before_and_after_pdv_link(identity_search_db, query):
    db = identity_search_db
    rows = seed(db)
    principal = rows['principal']
    assert [row.id for row in lookup(db, query)] == [principal.id]
    assert [(row['source'], row['id']) for row in search(db, query)['items']] == [('cadastro', principal.id)]
    account = PdvCliente(nome='Maria Gomez', cadastro_cliente_id=principal.id, saldo_fiado_gs=777)
    db.add(account); db.flush()
    assert [(row['source'], row['id']) for row in search(db, query)['items']] == [('pdv', account.id)]
    assert account.saldo_fiado_gs == 777 and db.query(Cliente).count() == 8


@pytest.mark.parametrize('query', ['CI', 'RUC', 'RG', '%', '_', "' OR 1=1 --", '12345678%', '3456789_', '80012345%'])
def test_search_does_not_match_json_keys_or_expand_wildcard_input(identity_search_db, query):
    db = identity_search_db
    rows = seed(db)
    expected = [rows['literal'].id] if query in {'%', '_'} else []
    assert [row.id for row in lookup(db, query)] == expected
    # PDV intentionally requires at least two normalized characters, so lone
    # wildcard input cannot be used to enumerate the customer directory.
    assert search(db, query)['items'] == []


@pytest.mark.parametrize('query', ['123%', '123%_', '123%_\\'])
def test_literals_with_digits_do_not_turn_into_document_number_search(identity_search_db, query):
    db = identity_search_db
    rows = seed(db)
    assert [row.id for row in lookup(db, query)] == [rows['literal'].id]
    assert [(row['source'], row['id']) for row in search(db, query)['items']] == [('cadastro', rows['literal'].id)]


def test_invalid_alias_cycle_terminates_without_matching_another_customer(identity_search_db):
    db = identity_search_db
    rows = seed(db)
    rows['middle'].merged_into_id = rows['old'].id
    db.flush()
    assert lookup(db, 'Nome Antigo Confirmado') == []
    assert search(db, 'B-98.765')['items'] == []


def test_client_endpoints_search_alias_without_exposing_duplicate_card(logistics):
    factory, client, _ = logistics
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[SavedAddress.__table__, PrintDevice.__table__, PrintJob.__table__])
        principal = seed(db)['principal'].id
        db.commit()
    for endpoint in ('/api/clientes/', '/api/clientes/pagina'):
        response = client.get(endpoint, params={'search': 'B-98.765'})
        assert response.status_code == 200, response.text
        items = response.json()['items'] if endpoint.endswith('pagina') else response.json()
        assert [row['id'] for row in items] == [str(principal)]
        assert items[0]['nome'] == 'Maria Gomez'
