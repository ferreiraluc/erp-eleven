"""Address reuse across differently structured bot and editor input."""
import pytest
from fastapi import HTTPException

from test_address_manager import env
from test_assistant import setup, incoming
from app.models import Cliente
from app.models.address_book import SavedAddress
from app.services.address_book import save_or_reuse
from app.services.address_identity import equivalent


ADDRESS = {'pais': 'BR', 'nome': 'Marina Exemplo', 'endereco': 'Rua das Flores',
           'numero': '101', 'complemento': 'Casa 40', 'bairro': 'Centro',
           'cidade': 'Curitiba', 'estado': 'PR', 'cep': '82010-220', 'cpf': '12345678909'}
EMBEDDED = ADDRESS | {'endereco': 'Rua das Flores 101 casa 40'}
PY_ADDRESS = {'pais': 'PY', 'nome': 'Juan Exemplo', 'cidade': 'Asunción', 'telefone': '0972 111 222'}


@pytest.mark.parametrize('change', [
    {'endereco': 'R. das Flores, 101 - Casa 40'},
    {'endereco': 'Rua das Flores, 101'},
    {'endereco': 'Rua das Flores, 101 - Casa 40', 'numero': ''},
    {'endereco': 'Rua das Flores, 101 - Casa 40', 'complemento': ''},
    {'endereco': 'Rua das Flores, 101 - Casa 40', 'numero': '', 'complemento': ''},
    {'endereco': 'Rua das Flores, 101 - Casa 40', 'bairro': ''},
])
def test_embedded_structured_and_repeated_fields_represent_one_destination(change):
    variant = ADDRESS | change
    assert equivalent(ADDRESS, variant) and equivalent(variant, ADDRESS)


@pytest.mark.parametrize('change', [
    {'numero': '102'}, {'endereco': 'Rua das Flores 102 casa 40'},
    {'endereco': 'Rua das Flores 101 casa 41'}, {'complemento': 'Casa 41'},
    {'endereco': 'Rua das Flores', 'complemento': ''},
    {'endereco': 'Rua das Flores 101 casa 40 fundos'}, {'nome': 'Outra Pessoa'},
    {'cep': '82010221'}, {'cidade': 'Outra Cidade'}, {'estado': 'SP'}, {'bairro': 'Outro Bairro'},
])
def test_conflicting_and_missing_delivery_details_are_not_erased(change):
    assert not equivalent(ADDRESS, EMBEDDED | change)


def test_numbered_street_is_not_a_house_number_suffix():
    assert not equivalent(ADDRESS | {'endereco': 'Rua 25', 'numero': '25'},
                          ADDRESS | {'endereco': 'Rua', 'numero': '25'})


@pytest.mark.parametrize('embedded_first', [False, True])
def test_repeated_requests_share_address_customer_and_enrich_missing_fields(env, embedded_first):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        db.add(customer); db.flush()
        first = EMBEDDED if embedded_first else ADDRESS
        saved, reused = save_or_reuse(db, first | {'cpf': '', 'bairro': ''}, uid)
        assert not reused and saved.cliente_id == customer.id
        for index in range(10):
            data = ADDRESS if index % 2 else EMBEDDED
            row, reused = save_or_reuse(db, data, uid)
            assert reused and row.id == saved.id and row.cliente_id == customer.id
        assert row.data['cpf'] == ADDRESS['cpf'] and row.data['bairro'] == ADDRESS['bairro']
        assert db.query(Cliente).count() == db.query(SavedAddress).count() == 1
        with pytest.raises(HTTPException):
            save_or_reuse(db, EMBEDDED | {'cpf': '98765432100'}, uid)


@pytest.mark.parametrize('phone', ['+595 972 111 222', '00595 972111222', '972111222', ''])
def test_paraguay_phone_formats_and_omission_reuse_customer_and_address(env, phone):
    factory, _, uid, _ = env
    with factory() as db:
        first, _ = save_or_reuse(db, PY_ADDRESS, uid)
        second, reused = save_or_reuse(db, PY_ADDRESS | {'telefone': phone}, uid)
        assert reused and first.id == second.id and first.cliente_id == second.cliente_id
        assert second.data['telefone'] == PY_ADDRESS['telefone']
        assert db.query(Cliente).count() == db.query(SavedAddress).count() == 1
        other, reused = save_or_reuse(db, PY_ADDRESS | {'cidade': 'Encarnación'}, uid)
        assert not reused and other.cliente_id == first.cliente_id


def test_paraguay_different_phones_or_locations_and_short_names_stay_separate():
    for change in ({'telefone': '0972111223'}, {'cidade': 'Encarnación'}, {'endereco': 'Calle Otra 25'},
                   {'estado': 'Central'}, {'nome': 'Outro Cliente'}):
        assert not equivalent(PY_ADDRESS, PY_ADDRESS | change)
    assert not equivalent(PY_ADDRESS | {'nome': 'Juan'}, PY_ADDRESS | {'nome': 'Juan', 'telefone': ''})


def test_missing_phone_cannot_choose_between_two_destinations(env):
    factory, _, uid, _ = env
    with factory() as db:
        save_or_reuse(db, PY_ADDRESS, uid)
        save_or_reuse(db, PY_ADDRESS | {'telefone': '0972111223'}, uid)
        with pytest.raises(HTTPException):
            save_or_reuse(db, PY_ADDRESS | {'telefone': ''}, uid)
        assert db.query(SavedAddress).count() == 2


def test_bot_confirmation_reuses_editor_address_without_losing_print_history(env):
    from app.models.assistant import AssistantAction, AssistantIdentity
    from app.models.printing import PrintJob
    from app.services.assistant_printing import AddressArgs, prepare_print
    from app.services.assistant_schedule import confirm_action
    from app.services.address_usage import history
    factory, client, uid, _ = env
    created = client.post('/manager/addresses', json={'label': 'Casa', 'data': PY_ADDRESS})
    assert created.status_code == 200
    with factory() as db:
        identity = db.query(AssistantIdentity).filter_by(channel='telegram').one()
        for phone in ('+595972111222', ''):
            message = incoming(db, uid, 'Imprima este endereço', channel='telegram')
            args = AddressArgs(**(PY_ADDRESS | {'telefone': phone}))
            assert 'confirmacao' in prepare_print(db, message, identity, args)
            action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
            confirmation = incoming(db, uid, 'confirmo', channel='telegram')
            assert 'fila de impressão' in confirm_action(db, confirmation, identity, action)
            assert 'Nenhuma alteração' in confirm_action(db, confirmation, identity, action)
        saved = db.query(SavedAddress).one()
        assert str(saved.id) == created.json()['id']
        assert db.query(Cliente).count() == 1 and db.query(PrintJob).count() == 2
        assert history(db, saved)['summary']['prints'] == 2


def test_embedded_legacy_merge_preserves_usage_and_old_ids(env):
    from app.services.address_maintenance import merge_addresses
    from app.services.address_book import resolve_address
    factory, _, uid, _ = env
    with factory() as db:
        target, _ = save_or_reuse(db, ADDRESS, uid)
        source = SavedAddress(label='Duplicado antigo', data=EMBEDDED, created_by=uid, cliente_id=target.cliente_id)
        db.add(source); db.flush()
        original = dict(source.data)
        plan = merge_addresses(db, target.id, source.id)
        assert source.merged_into_id is None
        assert merge_addresses(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])['state'] == 'merged'
        assert source.data == original and resolve_address(db, source.id).id == target.id
        assert db.query(SavedAddress).filter_by(merged_into_id=None).count() == 1
        assert db.query(Cliente).count() == 1
