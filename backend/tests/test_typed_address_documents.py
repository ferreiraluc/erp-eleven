"""Typed documents on paper and compatibility with historical idempotency keys."""
from copy import deepcopy
from io import BytesIO
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader

from test_address_manager import env, setup
from app.models import Cliente
from app.models.address_book import FreightOrder
from app.models.printing import PrintJob
from app.models.assistant import utcnow
from app.schemas.address_book import PrintInput, LayoutConfig, AddressData
from app.services import address_manager, superfrete
from app.services.address_book import save_or_reuse
from app.services.assistant_printing import AddressArgs, document_line, render_address
from app.services.document_snapshot import comparable_document_snapshot


BR = {'pais': 'BR', 'nome': 'Pessoa Sintética', 'endereco': 'Rua Exemplo', 'numero': '12',
      'bairro': 'Centro', 'cidade': 'Foz do Iguaçu', 'estado': 'PR', 'cep': '85865310'}
PY = {'pais': 'PY', 'nome': 'Persona Sintética', 'cidade': 'Asunción'}


def text(content):
    document = PdfReader(BytesIO(content))
    assert len(document.pages) == 1
    return document.pages[0].extract_text()


@pytest.mark.parametrize('template', ['classic', 'table', 'cards', 'columns', 'compact'])
@pytest.mark.parametrize('kind,number,country', [('CPF', '12345678909', 'BR'),
    ('CNPJ', '12.345.678/0001-95', 'BR'), ('RG', '12.345.678-X', 'BR'),
    ('CI', 'A-123.456', 'PY'), ('RUC', '80012345-6', 'PY')])
def test_typed_documents_keep_value_namespace_and_country_in_all_layouts(template, kind, number, country):
    args = AddressArgs(**(BR if country == 'BR' else PY), cpf=number, documento_tipo=kind,
        documento_emissor='SSP-SP' if kind == 'RG' else None, remetente='fixture' if country == 'BR' else None)
    payload = {'endereco': args.model_dump(), 'layout': LayoutConfig(template=template).model_dump(),
        'remetente': {'nome': 'Remetente Sintético', 'linhas': ['Remetente Sintético', 'Rua Exemplo, 10']} if country == 'BR' else None}
    original = deepcopy(payload)
    printed = text(render_address(payload))
    expected = '123.456.789-09' if kind == 'CPF' else number
    assert f'{kind}: {expected}' in printed
    assert document_line(args.model_dump(), preview=True) == f'{kind} do destinatário: {expected}'
    assert ('REMETENTE' in printed) == (country == 'BR')
    assert payload == original


@pytest.mark.parametrize('kind,country,number', [('CPF', 'PY', '12345678909'), ('CI', 'BR', '3456789'),
    ('RUC', 'BR', '80012345-6'), ('CNPJ', 'BR', '00000000000000')])
def test_typed_print_validation_rejects_wrong_country_and_invalid_numbers(kind, country, number):
    with pytest.raises(ValidationError):
        AddressArgs(**(BR if country == 'BR' else PY), cpf=number, documento_tipo=kind, remetente='fixture')


def test_address_data_validates_country_for_preselected_type_without_number():
    with pytest.raises(ValidationError):
        AddressData(pais='BR', documento_tipo='CI', cpf='')
    assert AddressData(pais='PY', documento_tipo='CI', cpf='').cpf == ''
    assert AddressData(pais='BR', cpf='').documento_tipo is None
    assert AddressData(pais='PY', cpf='').documento_tipo is None


def test_reusing_same_address_with_another_document_preserves_primary_and_enriches_customer(env):
    factory, _, uid, _ = env
    with factory() as db:
        first, _ = save_or_reuse(db, BR | {'cpf': '12345678909', 'documento_tipo': 'CPF'}, uid)
        original = deepcopy(first.data)
        again, reused = save_or_reuse(db, BR | {'cpf': '12.345.678-X', 'documento_tipo': 'RG', 'documento_emissor': 'SSP-SP'}, uid)
        assert reused and again.id == first.id and again.data == original
        customer = db.get(Cliente, first.cliente_id)
        assert customer.cpf == '12345678909'
        assert {document['tipo'] for document in customer.documentos} == {'CPF', 'RG'}
        with pytest.raises(HTTPException) as error:
            save_or_reuse(db, BR | {'cpf': '98765432100', 'documento_tipo': 'CPF'}, uid)
        assert error.value.status_code == 409 and first.data == original


def test_reusing_equal_digits_different_namespace_does_not_relabel_primary(env):
    factory, _, uid, _ = env
    with factory() as db:
        first, _ = save_or_reuse(db, PY | {'cpf': '3456789', 'documento_tipo': 'CI'}, uid)
        again, reused = save_or_reuse(db, PY | {'cpf': '3456789', 'documento_tipo': 'RUC'}, uid)
        assert reused and again.id == first.id and again.data['documento_tipo'] == 'CI'
        assert {document['tipo'] for document in db.get(Cliente, first.cliente_id).documentos} == {'CI', 'RUC'}


@pytest.mark.parametrize('incoming', [{'cpf': '80012345-6', 'documento_tipo': 'RUC'}, {'cpf': 'A-4.567.890'}])
def test_preselected_type_without_number_is_replaced_atomically_when_document_arrives(env, incoming):
    factory, _, uid, _ = env
    with factory() as db:
        first, _ = save_or_reuse(db, PY | {'cpf': '', 'documento_tipo': 'CI', 'documento_emissor': 'OLD'}, uid)
        again, reused = save_or_reuse(db, PY | incoming, uid)
        assert reused and again.id == first.id and again.data['cpf'] == incoming['cpf']
        assert again.data.get('documento_tipo') == incoming.get('documento_tipo')
        assert not again.data.get('documento_emissor')


def test_snapshot_comparison_ignores_only_new_null_metadata_without_mutating_history():
    legacy = {'editor': {'cpf': '3456789'}, 'price': None, 'items': [{'name': 'Original', 'optional': None}]}
    new = deepcopy(legacy)
    new['editor'].update(documento_tipo=None, documento_emissor=None)
    original = deepcopy(new)
    assert comparable_document_snapshot(legacy) == comparable_document_snapshot(new)
    assert new == original and legacy['price'] is None
    new['editor']['documento_tipo'] = 'CI'
    assert comparable_document_snapshot(legacy) != comparable_document_snapshot(new)


def test_old_print_snapshot_retry_reuses_job_without_pdf_render_or_rewriting_snapshot(env, monkeypatch):
    factory, _, uid, did = env
    body = PrintInput(request_key=uuid.uuid4(), device_id=uuid.UUID(did), data=PY)
    old_editor = body.data.model_dump(exclude={'documento_tipo', 'documento_emissor'})
    snapshot = {'editor': old_editor, 'sender_id': None, 'requested_address_id': None,
        'endereco': deepcopy(old_editor), 'layout': {'template': 'classic'}}
    with factory() as db:
        job = PrintJob(user_id=uid, device_id=uuid.UUID(did), request_key=body.request_key, source='erp',
            snapshot=snapshot, pdf=b'%PDF-fixture', sha256='0' * 64, expires_at=utcnow())
        db.add(job); db.flush()
        monkeypatch.setattr('app.services.assistant_printing.render_address', lambda _: pytest.fail('An idempotent retry must not render or enqueue another print.'))
        assert address_manager.enqueue_address(db, body, uid).id == job.id
        assert job.snapshot == snapshot and db.query(PrintJob).count() == 1
        changed = body.model_copy(update={'data': body.data.model_copy(update={'cpf': '3456789', 'documento_tipo': 'CI'})})
        with pytest.raises(HTTPException) as error:
            address_manager.enqueue_address(db, changed, uid)
        assert error.value.status_code == 409


def test_old_quote_request_retry_reuses_order_without_provider_call_or_changing_history(env, monkeypatch):
    factory, _, uid, _ = env
    body = superfrete.QuoteInput(request_key=uuid.uuid4(), address_id=uuid.uuid4(), remetente=BR,
        package={'weight': 1, 'height': 10, 'width': 10, 'length': 15},
        products=[{'name': 'Peça sintética', 'quantity': 1, 'unitary_value': '10.00'}], non_commercial=True)
    request = body.model_dump(mode='json', exclude={'request_key'})
    request['remetente'].pop('documento_tipo'); request['remetente'].pop('documento_emissor')
    snapshot = {'_request': request}
    with factory() as db:
        order = FreightOrder(user_id=uid, request_key=body.request_key, environment='sandbox',
            state='quoted', payload=snapshot, rates=[])
        db.add(order); db.flush()
        monkeypatch.setattr(superfrete, 'call', lambda *args, **kwargs: pytest.fail('Idempotent quote must not contact provider.'))
        assert superfrete.quote_order(db, body, uid).id == order.id
        assert order.payload == snapshot and db.query(FreightOrder).count() == 1
        changed = body.model_copy(update={'remetente': body.remetente.model_copy(update={'documento_tipo': 'RG', 'cpf': '1234567'})})
        with pytest.raises(HTTPException) as error:
            superfrete.quote_order(db, changed, uid)
        assert error.value.status_code == 409


def test_superfrete_accepts_only_tax_documents_and_keeps_brazilian_validation():
    for kind, number in [('RG', '12345678909'), ('CI', '12345678909'), ('RUC', '12345678909')]:
        with pytest.raises(HTTPException) as error:
            superfrete.party(BR | {'cpf': number, 'documento_tipo': kind}, recipient=True)
        assert error.value.status_code == 400 and 'CPF/CNPJ' in error.value.detail
    # Actual CPF/CNPJ check digits are already enforced in the freight flow.
    with pytest.raises(HTTPException):
        superfrete.party(BR | {'cpf': '12345678900', 'documento_tipo': 'CPF'}, recipient=True)
    assert superfrete.party(BR | {'cpf': '52998224725', 'documento_tipo': 'CPF'}, recipient=True)['document'] == '52998224725'
    assert superfrete.party(BR | {'cpf': '11222333000181', 'documento_tipo': 'CNPJ'}, recipient=True)['document'] == '11222333000181'
