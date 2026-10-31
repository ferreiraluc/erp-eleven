import pytest

from test_assistant import setup
from test_address_manager import env
from app.models import Cliente
from app.services.customer_address_match import same_structured_address
from app.services.customer_identity import corroboration, ensure_customer
from app.models.address_book import SavedAddress


NAME = 'Marcos Almeida Teste'
DATA = {'pais': 'BR', 'nome': NAME, 'endereco': 'Rua Mário do Violão', 'numero': '42',
        'bairro': 'Liberdade', 'cidade': 'Boa Vista', 'estado': 'RR', 'cep': '69309211'}
TEXT = '\nRua Mário do violão\nN° 42\nBairro Liberdade\nCep 69309-211\nCidade Boa Vista\nEstado Roraima\n' + NAME


@pytest.mark.parametrize('text', [TEXT, 'R. Mario do Violao, 42, Liberdade, Boa Vista, RR, 69309211, BR',
    'CEP 69309-211; Endereço Rua Mario do Violao 42; Estado RR; Cidade Boa Vista; Bairro Liberdade'])
def test_equivalent_structured_and_labeled_addresses(text):
    assert same_structured_address(text, DATA, NAME)


@pytest.mark.parametrize('update', [{'numero': '43'}, {'endereco': 'Rua Outra'}, {'cep': '69309212'},
    {'cidade': 'Manaus'}, {'estado': 'AM'}, {'complemento': 'apto 3'}, {'pais': 'PY'},
    {'cep': ''}, {'numero': ''}, {'endereco': ''}])
def test_incomplete_or_conflicting_address_does_not_match(update):
    assert not same_structured_address(TEXT, {**DATA, **update}, NAME)


@pytest.mark.parametrize('extra', ['Apartamento 3', 'Fundos', 'Casa B', 'Outra pessoa', 'Estado Amazonas'])
def test_unknown_or_conflicting_free_text_fragments_fail_closed(extra):
    assert not same_structured_address(TEXT + '\n' + extra, DATA, NAME)


def test_unit_must_exist_and_match_on_both_sides():
    assert same_structured_address(TEXT + '\nAp. 3', {**DATA, 'complemento': 'Apartamento 3'}, NAME)
    assert not same_structured_address(TEXT + '\nAp. 4', {**DATA, 'complemento': 'Apartamento 3'}, NAME)
    assert not same_structured_address('Boa Vista, RR, 69309211', DATA, NAME)


def test_contact_and_document_conflicts_still_take_precedence():
    customer = Cliente(nome=NAME, endereco=TEXT, telefone='+5511999991234', cpf='12345678909')
    assert corroboration(customer, DATA) == 'name_address'
    assert corroboration(customer, {**DATA, 'telefone': '+5511988881234'}) is None
    assert corroboration(customer, {**DATA, 'cpf': '98765432100'}) is None


def test_confirmed_address_rechecks_existing_customer_without_duplicate(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome=NAME, endereco=TEXT)
        address = SavedAddress(label=NAME, data=DATA, created_by=uid, customer_link_review=True)
        db.add_all([customer, address]); db.flush()
        assert ensure_customer(db, address)
        assert address.cliente_id == customer.id
        assert address.customer_link_reason == 'name_address'
        assert not address.customer_link_review
        assert db.query(Cliente).count() == 1
        assert customer.endereco == TEXT


def test_identical_name_and_address_on_two_people_requires_review(env):
    factory, _, uid, _ = env
    with factory() as db:
        db.add_all([Cliente(nome=NAME, endereco=TEXT), Cliente(nome=NAME, endereco=TEXT)])
        address = SavedAddress(label=NAME, data=DATA, created_by=uid)
        db.add(address); db.flush()
        ensure_customer(db, address)
        assert address.cliente_id is None and address.customer_link_review
