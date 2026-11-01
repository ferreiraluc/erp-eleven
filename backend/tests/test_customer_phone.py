import uuid

import pytest

from test_assistant import setup
from test_address_manager import env
from test_directory_duplicate_review import review_app
from test_customer_identity_endpoints import directory
from app.models import Cliente
from app.services.customer_phone import normalize_customer_phone


@pytest.mark.parametrize(('phone', 'country', 'expected'), [
    ('(11) 91234-5678', 'BR', '+5511912345678'),
    ('(55) 91234-5678', 'BR', '+5555912345678'),
    ('011 3456-7890', 'BR', '+551134567890'),
    ('0981 234567', 'PY', '+595981234567'),
    ('981234567', 'PY', '+595981234567'),
    ('+595 (0981) 234567', 'BR', '+595981234567'),
    ('00595981234567', 'PY', '+595981234567'),
    ('+55 (11) 91234-5678', 'PY', '+5511912345678'),
    ('+55 (011) 91234-5678', 'PY', '+5511912345678'),
    ('0055 (011) 3456-7890', 'BR', '+551134567890'),
    ('+1 (202) 555-0123', 'BR', '+12025550123'),
    ('', 'BR', None),
])
def test_country_is_explicit_and_existing_international_numbers_are_preserved(phone, country, expected):
    assert normalize_customer_phone(phone, country) == expected


@pytest.mark.parametrize(('phone', 'country'), [
    ('0981234567', 'BR'), ('11912345678', 'PY'), ('912345678', 'BR'),
    ('+55 11 00000000', 'PY'), ('5511912345678?text=oi', 'BR'),
    ('+55 (0011) 91234-5678', 'BR'),
    ('https://wa.me/5511912345678', 'BR'), ('0981234567', 'AR'),
])
def test_invalid_phone_is_not_reinterpreted(phone, country):
    with pytest.raises(ValueError):
        normalize_customer_phone(phone, country)


def test_create_normalizes_phone_and_update_can_correct_existing_local_number(review_app):
    factory, client, _ = directory(review_app)
    response = client.post('/api/clientes/', json={
        'nome': 'Cliente Paraguai QA', 'telefone': '0981 234567', 'telefone_pais': 'PY',
    })
    assert response.status_code == 201, response.text
    assert response.json()['telefone'] == '+595981234567'
    assert 'telefone_pais' not in response.json()
    with factory() as db:
        customer = Cliente(nome='Cliente Brasil QA', telefone='(55) 91234-5678')
        db.add(customer); db.commit(); customer_id = str(customer.id)
    response = client.put('/api/clientes/' + customer_id, json={'telefone_pais': 'BR'})
    assert response.status_code == 200, response.text
    assert response.json()['telefone'] == '+5555912345678'
    with factory() as db:
        assert db.get(Cliente, uuid.UUID(customer_id)).telefone == '+5555912345678'


def test_invalid_correction_does_not_overwrite_original_or_block_unrelated_legacy_edits(review_app):
    factory, client, _ = directory(review_app)
    with factory() as db:
        customer = Cliente(nome='Cliente legado QA', telefone='0981234567')
        db.add(customer); db.commit(); customer_id = str(customer.id)
    response = client.put('/api/clientes/' + customer_id, json={'telefone_pais': 'BR'})
    assert response.status_code == 422
    response = client.put('/api/clientes/' + customer_id, json={'email': 'cliente@example.test'})
    assert response.status_code == 200, response.text
    assert response.json()['telefone'] == '0981234567'
    response = client.put('/api/clientes/' + customer_id, json={'telefone_pais': 'PY', 'telefone': ''})
    assert response.status_code == 200, response.text
    assert response.json()['telefone'] is None
