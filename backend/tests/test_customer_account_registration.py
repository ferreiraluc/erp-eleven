"""Checkout customer registration preserves credit and canonical identity."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
import uuid

import pytest
from test_access_postgres import pg
from test_pdv_unknown_stock import pdv_app
from test_pdv_stock_postgres import pdv_pg
from app.models import Cliente, Usuario
from app.models.pdv import PdvCliente


def ci(name='Ana Correia Silva', number='1234567', **extra):
    return {'nome': name, 'doc': number, 'doc_tipo': 'CI', 'doc_pais': 'PY', **extra}


def test_create_and_reuse_return_correct_status_without_resetting_credit(pdv_app):
    factory, client, _ = pdv_app
    made = client.post('/api/pdv/clients', json=ci(limite_fiado_gs=5000, notas='Original'))
    assert made.status_code == 201, made.text
    account_id = uuid.UUID(made.json()['id'])
    assert made.json()['doc_tipo'] == 'CI' and made.json()['doc_pais'] == 'PY'
    with factory() as db:
        db.get(PdvCliente, account_id).saldo_fiado_gs = 777
        db.commit()
    again = client.post('/api/pdv/clients', json=ci(name='Ana Silva', limite_fiado_gs=0, notas='Replacement'))
    assert again.status_code == 200, again.text
    assert again.json()['id'] == str(account_id)
    assert again.json()['saldo_fiado_gs'] == 777
    assert again.json()['limite_fiado_gs'] == 5000
    assert again.json()['notas'] == 'Original'
    assert again.json()['nome'] == 'Ana Correia Silva'
    with factory() as db:
        assert db.query(Cliente).count() == 1
        assert db.query(PdvCliente).filter_by(cadastro_cliente_id=uuid.UUID(made.json()['cadastro_cliente_id'])).count() == 1


def test_name_only_and_conflicting_document_names_require_selection(pdv_app):
    factory, client, _ = pdv_app
    first = client.post('/api/pdv/clients', json=ci())
    assert first.status_code == 201
    assert client.post('/api/pdv/clients', json={'nome': 'Ana Correia Silva'}).status_code == 409
    assert client.post('/api/pdv/clients', json=ci(name='Maria Santos')).status_code == 409
    assert client.post('/api/pdv/clients', json={'nome': 'Ana'}).status_code == 422
    with factory() as db:
        assert db.query(PdvCliente).count() == 2  # Includes the unrelated fixture.
        assert db.query(Cliente).count() == 1


def test_different_typed_document_namespaces_do_not_merge_distinct_people(pdv_app):
    factory, client, _ = pdv_app
    first = client.post('/api/pdv/clients', json=ci())
    second = client.post('/api/pdv/clients', json={
        'nome': 'Maria Santos', 'doc': '1234567', 'doc_tipo': 'RG', 'doc_pais': 'BR',
    })
    assert first.status_code == second.status_code == 201, second.text
    assert first.json()['id'] != second.json()['id']
    with factory() as db:
        assert db.query(Cliente).count() == 2


def test_known_directory_identity_is_reused_across_address_and_checkout(pdv_app):
    factory, client, _ = pdv_app
    with factory() as db:
        main = Cliente(nome='Ana Correia Silva', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}],
                       endereco='Calle Prueba, 25, Asunción, PY')
        db.add(main); db.flush(); main_id = main.id; db.commit()
    response = client.post('/api/pdv/clients', json=ci(name='Ana Silva'))
    assert response.status_code == 201, response.text
    assert response.json()['cadastro_cliente_id'] == str(main_id)
    with factory() as db:
        assert db.query(Cliente).count() == 1
        assert db.get(Cliente, main_id).endereco == 'Calle Prueba, 25, Asunción, PY'


def test_owner_confirmed_alias_reuses_existing_checkout_account(pdv_app):
    factory, client, _ = pdv_app
    with factory() as db:
        main = Cliente(nome='Ana Correia')
        db.add(main); db.flush()
        alias = Cliente(nome='Ana Correa Silva', cpf='12345678909', merged_into_id=main.id, ativo=False)
        account = PdvCliente(nome='Ana Correia', cadastro_cliente_id=main.id, saldo_fiado_gs=150, limite_fiado_gs=200)
        db.add_all([alias, account]); db.flush(); account_id = account.id; db.commit()
    response = client.post('/api/pdv/clients', json={'nome': 'Ana Correa Silva', 'doc': '12345678909', 'doc_tipo': 'CPF', 'doc_pais': 'BR'})
    assert response.status_code == 200, response.text
    assert response.json()['id'] == str(account_id)
    assert response.json()['saldo_fiado_gs'] == 150 and response.json()['limite_fiado_gs'] == 200


def test_matching_account_cannot_hide_a_conflicting_explicit_directory_link(pdv_app):
    factory, client, _ = pdv_app
    with factory() as db:
        main = Cliente(nome='Ana Correia Silva', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}])
        other = Cliente(nome='Maria Santos', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '7654321'}])
        db.add_all([main, other]); db.flush()
        account = PdvCliente(nome='Ana Correia Silva', doc='1234567', doc_tipo='CI', doc_pais='PY',
                             cadastro_cliente_id=other.id, saldo_fiado_gs=95)
        db.add(account); db.flush(); account_id, other_id = account.id, other.id; db.commit()
    response = client.post('/api/pdv/clients', json=ci())
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.get(PdvCliente, account_id).cadastro_cliente_id == other_id
        assert db.get(PdvCliente, account_id).saldo_fiado_gs == 95


@pytest.mark.parametrize('second_name', ['Ana Correia Silva', 'Maria Santos'])
def test_direct_account_match_does_not_override_ambiguous_canonical_documents(pdv_app, second_name):
    factory, client, _ = pdv_app
    with factory() as db:
        first = Cliente(nome='Ana Correia Silva', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}])
        second = Cliente(nome=second_name, documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}])
        db.add_all([first, second]); db.flush()
        account = PdvCliente(nome=first.nome, doc='1234567', doc_tipo='CI', doc_pais='PY',
                             cadastro_cliente_id=first.id, saldo_fiado_gs=195)
        db.add(account); db.flush(); account_id, principal_id = account.id, first.id; db.commit()
    response = client.post('/api/pdv/clients', json=ci())
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.query(Cliente).count() == 2
        assert db.query(PdvCliente).count() == 2
        assert db.get(PdvCliente, account_id).cadastro_cliente_id == principal_id
        assert db.get(PdvCliente, account_id).saldo_fiado_gs == 195
    # The existing financial account still accepts unrelated maintenance.
    response = client.put('/api/pdv/clients/' + str(account_id), json={'notas': 'Conferir documento'})
    assert response.status_code == 200, response.text
    assert response.json()['saldo_fiado_gs'] == 195
    # Changing an identity field cannot bypass canonical review either.
    response = client.put('/api/pdv/clients/' + str(account_id), json={'telefone': '+595981123456'})
    assert response.status_code == 409, response.text


def test_direct_account_match_cannot_override_a_known_document_with_another_name(pdv_app):
    factory, client, _ = pdv_app
    with factory() as db:
        main = Cliente(nome='Maria Santos', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}])
        account = PdvCliente(nome='Ana Correia Silva', doc='1234567', doc_tipo='CI', doc_pais='PY', saldo_fiado_gs=195)
        db.add_all([main, account]); db.commit()
    response = client.post('/api/pdv/clients', json=ci())
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.query(Cliente).count() == 1
        assert db.query(PdvCliente).filter_by(doc='1234567').one().cadastro_cliente_id is None


@pytest.mark.parametrize('patch', [{'doc_tipo': 'CPF'}, {'doc_pais': 'BR'}, {'nome': None}, {'ativo': None}])
def test_partial_update_validates_complete_document_and_returns_422(pdv_app, patch):
    factory, client, _ = pdv_app
    made = client.post('/api/pdv/clients', json=ci())
    account_id = made.json()['id']
    result = client.put('/api/pdv/clients/' + account_id, json=patch)
    assert result.status_code == 422, result.text
    with factory() as db:
        row = db.get(PdvCliente, uuid.UUID(account_id))
        assert row.doc_tipo == 'CI' and row.doc_pais == 'PY' and row.doc == '1234567'
        assert row.nome == 'Ana Correia Silva' and row.ativo


def test_update_can_clear_optional_data_without_resetting_balances(pdv_app):
    factory, client, _ = pdv_app
    made = client.post('/api/pdv/clients', json=ci(telefone='+595981123456', notas='To remove', limite_fiado_gs=1000))
    account_id = uuid.UUID(made.json()['id'])
    with factory() as db:
        db.get(PdvCliente, account_id).saldo_fiado_gs = 750; db.commit()
    response = client.put('/api/pdv/clients/' + str(account_id), json={'telefone': None, 'notas': None})
    assert response.status_code == 200, response.text
    assert response.json()['telefone'] is None and response.json()['notas'] is None
    assert response.json()['saldo_fiado_gs'] == 750 and response.json()['limite_fiado_gs'] == 1000


def test_historical_distinct_accounts_can_edit_notes_without_merging_credit(pdv_app):
    factory, client, _ = pdv_app
    with factory() as db:
        main = Cliente(nome='Ana Correia')
        db.add(main); db.flush()
        accounts = [PdvCliente(nome='Ana Correia', cadastro_cliente_id=main.id, saldo_fiado_gs=value) for value in (150, 250)]
        db.add_all(accounts); db.flush(); account_ids = [row.id for row in accounts]; db.commit()
    response = client.put('/api/pdv/clients/' + str(account_ids[0]), json={'notas': 'Conferido'})
    assert response.status_code == 200, response.text
    with factory() as db:
        assert [db.get(PdvCliente, row_id).saldo_fiado_gs for row_id in account_ids] == [150, 250]
        assert db.get(PdvCliente, account_ids[0]).notas == 'Conferido'
        assert db.get(PdvCliente, account_ids[1]).notas is None


def test_update_to_another_checkout_identity_is_rejected_without_partial_changes(pdv_app):
    factory, client, _ = pdv_app
    first = client.post('/api/pdv/clients', json=ci())
    second = client.post('/api/pdv/clients', json=ci(name='Maria Santos', number='7654321'))
    result = client.put('/api/pdv/clients/' + first.json()['id'], json=ci(name='Maria Santos', number='7654321', limite_fiado_gs=999))
    assert result.status_code == 409, result.text
    with factory() as db:
        row = db.get(PdvCliente, uuid.UUID(first.json()['id']))
        assert row.nome == 'Ana Correia Silva' and row.doc == '1234567' and row.limite_fiado_gs == 0
        assert db.get(PdvCliente, uuid.UUID(second.json()['id'])).doc == '7654321'


def test_employee_response_includes_document_namespace_but_hides_balance(pdv_app):
    factory, client, _ = pdv_app
    with factory() as db:
        db.query(Usuario).first().sales_scope = 'own'; db.commit()
    response = client.post('/api/pdv/clients', json=ci())
    assert response.status_code == 201, response.text
    assert response.json()['saldo_fiado_gs'] is None
    assert response.json()['doc_tipo'] == 'CI' and response.json()['doc_pais'] == 'PY'


def test_postgres_concurrent_registration_creates_one_account_and_one_person(pdv_pg):
    factory, client, _, control, _ = pdv_pg
    barrier = Barrier(2)
    control['before_request'] = lambda db: barrier.wait(timeout=10)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: client.post('/api/pdv/clients', json=ci()), range(2)))
    finally:
        control.clear()
    assert sorted(result.status_code for result in results) == [200, 201], [result.text for result in results]
    assert len({result.json()['id'] for result in results}) == 1
    with factory() as db:
        assert db.query(PdvCliente).filter_by(doc='1234567', doc_tipo='CI', doc_pais='PY').count() == 1
        assert db.query(Cliente).count() == 1


def test_postgres_partial_update_reads_after_lock_and_preserves_concurrent_changes(pdv_pg):
    factory, client, cid, control, _ = pdv_pg
    with factory() as db:
        row = db.get(PdvCliente, cid); row.telefone = '+595981111223'; row.limite_fiado_gs = 100
        db.commit()
    def preload(db):
        stale = db.get(PdvCliente, cid)
        assert stale.telefone == '+595981111223'
        db.info['held_stale_customer'] = stale
        with factory() as writer:
            row = writer.get(PdvCliente, cid)
            row.telefone = '+595981111224'; row.limite_fiado_gs = 999; row.saldo_fiado_gs = Decimal('123')
            writer.commit()
    control['before_request'] = preload
    try:
        response = client.put('/api/pdv/clients/' + str(cid), json={'notas': 'New note'})
    finally:
        control.clear()
    assert response.status_code == 200, response.text
    assert response.json()['telefone'] == '+595981111224'
    assert response.json()['limite_fiado_gs'] == 999 and response.json()['saldo_fiado_gs'] == 123
    assert response.json()['notas'] == 'New note'
