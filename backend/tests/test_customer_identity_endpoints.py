"""Directory writes reuse strong identities and reject ambiguous duplication."""
import uuid
from test_assistant import setup
from test_address_manager import env
from test_directory_duplicate_review import review_app
from app.api.endpoints import clientes
from app.models import Cliente
from app.services.customer_maintenance import merge_customer_selection


def directory(review_app):
    factory, client, uid = review_app
    client.app.include_router(clientes.router, prefix='/api/clientes')
    return factory, client, uid


def test_manual_create_reuses_documented_customer_and_preserves_current_contacts(review_app):
    factory, client, _ = directory(review_app)
    with factory() as db:
        row = Cliente(nome='Ana Correia Silva', cpf='12345678909', telefone='+595981111223')
        db.add(row); db.commit(); customer_id = str(row.id)
    response = client.post('/api/clientes/', json={
        'nome': 'Ana Silva', 'cpf': '123.456.789-09', 'telefone': '+595981111224',
    })
    assert response.status_code == 200, response.text
    assert response.json()['id'] == customer_id
    assert response.json()['nome'] == 'Ana Correia Silva'
    assert response.json()['telefone'] == '+595981111223'
    with factory() as db:
        assert db.query(Cliente).count() == 1


def test_ambiguous_name_and_different_document_never_create_another_permanent_person(review_app):
    factory, client, _ = directory(review_app)
    with factory() as db:
        db.add(Cliente(nome='Ana Silva', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}]))
        db.commit()
    assert client.post('/api/clientes/', json={'nome': 'Ana Silva'}).status_code == 409
    assert client.post('/api/clientes/', json={
        'nome': 'Ana Silva', 'documentos': [{'tipo': 'CI', 'pais': 'PY', 'numero': '7654321'}],
    }).status_code == 409
    with factory() as db:
        assert db.query(Cliente).count() == 1


def test_selected_alias_documents_resolve_future_manual_registration(review_app):
    factory, client, _ = directory(review_app)
    with factory() as db:
        principal = Cliente(nome='Ana Correia')
        old = Cliente(nome='Ana Correa Silva', cpf='12345678909')
        db.add_all([principal, old]); db.flush()
        plan = merge_customer_selection(db, principal.id, [old.id])
        merge_customer_selection(db, principal.id, [old.id], apply=True,
                                 expected_plan=plan['plan_token'], reviewed_conflicts=True)
        customer_id = str(principal.id); db.commit()
    response = client.post('/api/clientes/', json={'nome': 'Ana Correa Silva', 'cpf': '12345678909'})
    assert response.status_code == 200, response.text
    assert response.json()['id'] == customer_id
    # CPF stays on its historical row; the merged identity remains searchable.
    assert response.json()['cpf'] is None
    with factory() as db:
        assert db.query(Cliente).count() == 2


def test_edit_checks_final_document_state_and_excludes_own_aliases(review_app):
    factory, client, _ = directory(review_app)
    with factory() as db:
        principal = Cliente(nome='Ana Silva', cpf='12345678909')
        old = Cliente(nome='ANA SILVA', telefone='+595981111223')
        other = Cliente(nome='Maria Santos', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}])
        db.add_all([principal, old, other]); db.flush()
        plan = merge_customer_selection(db, principal.id, [old.id])
        merge_customer_selection(db, principal.id, [old.id], apply=True, expected_plan=plan['plan_token'])
        customer_id = str(principal.id); db.commit()
    response = client.put('/api/clientes/' + customer_id, json={'telefone': '+595981111224'})
    assert response.status_code == 200, response.text
    assert client.put('/api/clientes/' + customer_id, json={'documentos': [
        {'tipo': 'CPF', 'pais': 'BR', 'numero': '98765432100'},
    ]}).status_code == 422
    response = client.put('/api/clientes/' + customer_id, json={'nome': 'Maria Santos', 'cpf': None,
        'documentos': [{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}]})
    assert response.status_code == 409
    with factory() as db:
        assert db.get(Cliente, uuid.UUID(customer_id)).nome == 'Ana Silva'


def test_explicit_null_documents_is_normalized_and_single_name_is_not_created(review_app):
    factory, client, _ = directory(review_app)
    with factory() as db:
        row = Cliente(nome='Ana Silva', documentos=[{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}])
        db.add(row); db.commit(); customer_id = str(row.id)
    response = client.put('/api/clientes/' + customer_id, json={'documentos': None})
    assert response.status_code == 200, response.text
    assert response.json()['documentos'] == []
    assert client.post('/api/clientes/', json={'nome': 'Ana'}).status_code == 422
