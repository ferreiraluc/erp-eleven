"""Typed, cross-module identity evidence without conflating homonyms or ledgers."""
import pytest
from pydantic import ValidationError

from test_address_manager import env
from test_assistant import setup
from app.models import Cliente, Usuario
from app.models.pdv import PdvCliente
from app.schemas.cliente import ClienteCreate
from app.schemas.address_book import AddressData
from app.schemas.pdv import PdvClienteCreate
from app.services.address_book import save_or_reuse
from app.services.customer_identity import find_customer, ensure_pdv_customer
from app.services.customer_documents import input_documents


def typed(kind, number, country='PY', issuer=None):
    return {'tipo': kind, 'pais': country, 'numero': number, **({'emissor': issuer} if issuer else {})}


def test_same_ci_and_compatible_full_name_reuse_across_address_and_pdv(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome='María Elena López', documentos=[typed('CI', '3.456.789')])
        db.add(customer); db.flush()
        address, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Maria Lopez', 'cpf': '3456789',
            'documento_tipo': 'CI', 'cidade': 'Asunción'}, uid)
        account = PdvCliente(nome='MARIA LOPEZ', doc='3.456.789', doc_tipo='CI', doc_pais='PY',
            saldo_fiado_gs=777, limite_fiado_gs=999)
        db.add(account); db.flush()
        assert ensure_pdv_customer(db, account)
        assert address.cliente_id == account.cadastro_cliente_id == customer.id
        assert not address.customer_link_review and db.query(Cliente).count() == 1
        assert account.saldo_fiado_gs == 777 and account.limite_fiado_gs == 999


def test_document_namespace_and_rg_issuer_cannot_be_guessed(env):
    factory, _, _, _ = env
    with factory() as db:
        customer = Cliente(nome='Maria Lopez', documentos=[typed('CI', '3456789')])
        rg = Cliente(nome='Bruno Silva', documentos=[typed('RG', '1234567', 'BR', 'SSP-SP')])
        db.add_all([customer, rg]); db.flush()
        assert find_customer(db, {'nome': 'Maria Lopez', 'documentos': [typed('RUC', '3456789')]})[0] is None
        assert find_customer(db, {'nome': 'Bruno Silva', 'documentos': [typed('RG', '1234567', 'BR')]})[0] is None
        assert find_customer(db, {'nome': 'Bruno Silva', 'documentos': [typed('RG', '1234567', 'BR', 'SSP-SP')]})[0] == rg
        assert not input_documents({'doc': '12345678909'})  # Old untyped PDV text is not automatically CPF.
        assert not input_documents({'cpf': '12345678909', 'pais': 'PY'})


def test_name_postal_code_or_street_alone_do_not_link_and_do_not_make_duplicate(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome='Ana Silva', endereco='Rua Teste, 25, Centro, Foz, PR, 85865310, BR')
        db.add(customer); db.flush()
        for city in ('Asunción', 'Encarnación'):
            address, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'ANA SILVA', 'cidade': city}, uid)
            assert address.cliente_id is None and address.customer_link_review
        assert db.query(Cliente).count() == 1
        assert find_customer(db, {'nome': 'Ana Silva', 'cep': '85865310'})[0] is None
        assert find_customer(db, {'nome': 'Ana Silva', 'endereco': 'Rua Teste'})[0] is None
        assert find_customer(db, {'nome': 'Silva', 'endereco_livre': customer.endereco})[0] is None
        assert find_customer(db, {'nome': 'Ana Silva', 'endereco_livre': 'Rua Teste, 25, Centro, Foz, PR, 85865-310, BR'})[0] == customer


def test_known_document_with_another_name_stays_pending_not_another_person(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome='Maria Lopez', documentos=[typed('RUC', '80012345-6')])
        db.add(customer); db.flush()
        address, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Outro Nome', 'cpf': '80012345-6',
            'documento_tipo': 'RUC', 'cidade': 'Asunción'}, uid)
        assert address.cliente_id is None and address.customer_link_review
        assert address.customer_link_reason == 'document_name_conflict' and db.query(Cliente).count() == 1


def test_confirmed_alias_names_and_documents_resolve_principal_and_ignore_self_update(env):
    factory, _, _, _ = env
    with factory() as db:
        principal = Cliente(nome='Maria Lopez', documentos=[typed('CI', '3456789')])
        db.add(principal); db.flush()
        alias = Cliente(nome='Maria Gomez', documentos=[typed('RUC', '80012345-6')], ativo=False,
            merged_into_id=principal.id)
        db.add(alias); db.flush()
        data = {'nome': alias.nome, 'documentos': alias.documentos}
        assert find_customer(db, data)[0] == principal
        assert find_customer(db, data, exclude_id=principal.id)[0] is None
        assert find_customer(db, data, exclude_id=principal.id)[2] == []
        assert principal.nome == 'Maria Lopez' and alias.documentos == [typed('RUC', '80012345-6')]


def test_short_name_preserves_py_print_input_without_creating_placeholder_customer(env):
    factory, _, uid, _ = env
    with factory() as db:
        address, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Maria', 'cidade': 'Asunción'}, uid)
        assert address.data['nome'] == 'Maria' and address.cliente_id is None and address.customer_link_review
        assert db.query(Cliente).count() == 0


def test_explicit_address_document_conflict_is_flagged_without_changing_identity(env):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome='Maria Lopez', documentos=[typed('CI', '3456789')])
        db.add(customer); db.flush()
        address, _ = save_or_reuse(db, {'pais': 'PY', 'nome': 'Maria Lopez', 'cpf': '7654321',
            'documento_tipo': 'CI', 'cidade': 'Asunción'}, uid, cliente_id=customer.id)
        assert address.cliente_id == customer.id and address.customer_link_review
        assert address.customer_link_reason == 'document_conflict'
        assert customer.documentos == [typed('CI', '3456789')] and address.data['cpf'] == '7654321'


@pytest.mark.parametrize('document', [typed('CPF', '12345678909'), typed('CI', '3456789', 'BR'),
    typed('CPF', '00000000000', 'BR'), typed('RG', '12', 'BR')])
def test_invalid_typed_document_is_rejected_at_api_contract(document):
    with pytest.raises(ValidationError):
        ClienteCreate(nome='Pessoa Fixture', documentos=[document])


def test_address_and_pdv_contract_preserve_typed_values_and_reject_cross_country():
    assert AddressData(pais='PY', nome='Fixture Nome', cpf='3456789', documento_tipo='CI').documento_tipo == 'CI'
    assert PdvClienteCreate(nome='Fixture Nome', doc='3.456.789', doc_tipo='CI').doc_pais == 'PY'
    with pytest.raises(ValidationError):
        AddressData(pais='BR', cpf='3456789', documento_tipo='CI')
    with pytest.raises(ValidationError):
        PdvClienteCreate(nome='Fixture Nome', doc='3456789', doc_tipo='CI', doc_pais='BR')
