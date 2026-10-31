"""Legacy freight documents cannot be replaced by a homonymous current owner."""
from types import SimpleNamespace

import pytest

from test_assistant import setup
from app.database import Base
from app.models import Cliente
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente
from app.services.customer_shipping_identity import freight_customer


NAME = 'Pessoa Sintética QA'
ORIGINAL_CPF = '12345678909'
CURRENT_CPF = '52998224725'


@pytest.fixture
def identity_env(setup):
    factory, _, user_id = setup
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[SavedAddress.__table__])
    return factory, user_id


def linked_address(db, user_id, source, document):
    person = Cliente(nome=NAME)
    db.add(person); db.flush()
    data = {'nome': NAME, 'pais': 'BR'}
    account = None
    if source == 'address':
        data.update(cpf=document, documento_tipo='CPF')
    else:
        account = PdvCliente(nome=NAME, cadastro_cliente_id=person.id,
                             doc=document, doc_tipo='CPF', doc_pais='BR')
        db.add(account); db.flush()
    address = SavedAddress(label='Destino QA', data=data, created_by=user_id,
        cliente_id=person.id if account is None else None,
        pdv_cliente_id=account.id if account else None)
    db.add(address); db.flush()
    return person, address, account


def historical_freight(address):
    return SimpleNamespace(address_id=address.id, payload={
        'to': {'name': NAME, 'document': ORIGINAL_CPF},
    })


@pytest.mark.parametrize('source', ['address', 'pdv-account'])
def test_legacy_freight_rejects_current_document_conflict_without_directory_documents(identity_env, source):
    factory, user_id = identity_env
    with factory() as db:
        person, address, account = linked_address(db, user_id, source, CURRENT_CPF)
        freight = historical_freight(address)
        assert person.cpf is None and not person.documentos
        assert freight_customer(db, freight) is None
        assert not db.new and not db.dirty and not db.deleted
        assert freight.payload['to']['document'] == ORIGINAL_CPF
        assert (address.data['cpf'] if account is None else account.doc) == CURRENT_CPF
        assert (address.cliente_id if account is None else account.cadastro_cliente_id) == person.id


@pytest.mark.parametrize('source', ['address', 'pdv-account'])
def test_legacy_freight_keeps_compatible_explicit_owner_without_directory_documents(identity_env, source):
    factory, user_id = identity_env
    with factory() as db:
        person, address, _ = linked_address(db, user_id, source, ORIGINAL_CPF)
        assert freight_customer(db, historical_freight(address)).id == person.id
        assert not db.dirty


def test_legacy_freight_checks_current_address_after_following_confirmed_address_alias(identity_env):
    factory, user_id = identity_env
    with factory() as db:
        _, address, _ = linked_address(db, user_id, 'address', CURRENT_CPF)
        old_address = SavedAddress(label='Destino antigo QA', created_by=user_id,
            data={'nome': NAME, 'pais': 'BR', 'cpf': ORIGINAL_CPF, 'documento_tipo': 'CPF'},
            merged_into_id=address.id, active=False)
        db.add(old_address); db.flush()
        freight = historical_freight(old_address)
        assert freight_customer(db, freight) is None
        assert freight.address_id == old_address.id
        assert old_address.merged_into_id == address.id


@pytest.mark.parametrize('captured', [True, False])
def test_captured_customer_id_or_null_does_not_reinterpret_a_later_address_document(identity_env, captured):
    factory, user_id = identity_env
    with factory() as db:
        person, address, _ = linked_address(db, user_id, 'address', CURRENT_CPF)
        freight = historical_freight(address)
        freight.payload['_customer_id'] = str(person.id) if captured else None
        assert freight_customer(db, freight) == (person if captured else None)
        assert not db.dirty
