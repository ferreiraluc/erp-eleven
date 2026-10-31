"""Quote HTTP waits finish before the shared customer/address identity lock."""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, update

from test_assistant import setup
from test_address_manager import env
from app.models import Cliente
from app.models.address_book import FreightOrder, SavedAddress
from app.services import address_book, customer_identity, postal_codes, superfrete


ADDRESS = {'pais': 'BR', 'nome': 'Pessoa Sintética', 'cpf': '12345678909',
           'endereco': 'Rua Central', 'numero': '40', 'bairro': 'Centro',
           'cidade': 'São Paulo', 'estado': 'SP', 'cep': '01001000'}


def quote_input(db, user_id):
    address = SavedAddress(label='Destino sintético', data=ADDRESS.copy(), created_by=user_id)
    db.add(address); db.flush()
    body = superfrete.QuoteInput(request_key=uuid.uuid4(), address_id=address.id, remetente=ADDRESS,
        package={'weight': 1, 'height': 10, 'width': 15, 'length': 20},
        products=[{'name': 'Camiseta sintética', 'quantity': 1, 'unitary_value': '10.00'}], non_commercial=True)
    return address, body


def test_postcode_and_calculator_finish_before_identity_lock_without_committing(env, monkeypatch):
    factory, _, user_id, _ = env
    events, locked = [], False

    def complete(data):
        assert not locked
        events.append('postcode')
        return {'data': data, 'warnings': []}

    def calculate(db, row):
        assert not locked and inspect(row).transient
        assert db.query(FreightOrder).count() == 0
        events.append('calculator')
        row.state = 'quoted'
        row.rates = [{'id': 1, 'price': '20.00'}]
        return row

    def lock(db):
        nonlocal locked
        locked = True
        events.append('lock')

    original_ensure = customer_identity.ensure_customer
    def ensure(db, address):
        assert locked
        events.append('identity')
        return original_ensure(db, address)

    monkeypatch.setattr(postal_codes, 'complete_address', complete)
    monkeypatch.setattr(superfrete, 'calculate', calculate)
    monkeypatch.setattr(address_book, 'lock_addresses', lock)
    monkeypatch.setattr(customer_identity, 'ensure_customer', ensure)
    with factory() as db:
        address, body = quote_input(db, user_id)
        def no_commit():
            raise AssertionError('The caller owns the transaction')
        monkeypatch.setattr(db, 'commit', no_commit)
        row = superfrete.quote_order(db, body, user_id)
        assert row.state == 'quoted' and row.payload['_customer_id'] == str(address.cliente_id)
        assert events == ['postcode', 'postcode', 'calculator', 'lock', 'identity']
        assert superfrete.quote_order(db, body, user_id).id == row.id
        assert len(events) == 5


@pytest.mark.parametrize('change', ['data', 'active', 'alias'])
def test_address_changed_during_external_quote_requires_review_without_partial_freight(env, monkeypatch, change):
    factory, _, user_id, _ = env
    monkeypatch.setattr(postal_codes, 'complete_address', lambda data: {'data': data, 'warnings': []})
    monkeypatch.setattr(superfrete, 'calculate', lambda db, row: row)
    with factory() as db:
        address, body = quote_input(db, user_id)
        replacement = SavedAddress(label='Novo destino', data={**ADDRESS, 'numero': '99'}, created_by=user_id)
        db.add(replacement); db.commit()
        original_id, replacement_id = address.id, replacement.id
        def lock(session):
            values = {'data': {**ADDRESS, 'numero': '99'}} if change == 'data' else {'active': False}
            if change == 'alias':
                values = {'merged_into_id': replacement_id, 'active': False}
            # Bypass the identity map, as another transaction would do while the
            # calculator waits; quote_order must reload under its lock.
            session.execute(update(SavedAddress).where(SavedAddress.id == original_id).values(**values),
                            execution_options={'synchronize_session': False})
        monkeypatch.setattr(address_book, 'lock_addresses', lock)
        with pytest.raises(HTTPException) as error:
            superfrete.quote_order(db, body, user_id)
        assert error.value.status_code == 409
        assert db.query(FreightOrder).count() == db.query(Cliente).count() == 0
        db.rollback()
        assert db.query(FreightOrder).count() == 0


def test_concurrent_identical_request_is_reused_after_the_identity_lock(env, monkeypatch):
    factory, _, user_id, _ = env
    monkeypatch.setattr(postal_codes, 'complete_address', lambda data: {'data': data, 'warnings': []})
    monkeypatch.setattr(superfrete, 'calculate', lambda db, row: row)
    with factory() as db:
        address, body = quote_input(db, user_id)
        winner = FreightOrder(request_key=body.request_key, user_id=user_id, address_id=address.id,
            environment='production', state='quoted', rates=[],
            payload={'_request': body.model_dump(mode='json', exclude={'request_key'}), '_customer_id': None})
        def lock(session):
            session.add(winner); session.flush()
        monkeypatch.setattr(address_book, 'lock_addresses', lock)
        result = superfrete.quote_order(db, body, user_id)
        assert result.id == winner.id and db.query(FreightOrder).count() == 1
        assert db.query(Cliente).count() == 0
