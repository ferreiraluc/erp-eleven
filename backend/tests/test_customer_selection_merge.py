"""A selected customer group is reviewed and committed as one operation."""
import uuid

import pytest
from fastapi import HTTPException
from test_assistant import setup
from test_address_manager import env
from test_directory_duplicate_review import review_app
from test_customer_maintenance import pair
from app.models import Cliente, Pedido, Usuario
from app.models.address_book import SavedAddress
from app.models.access import AuditEvent
from app.models.pdv import PdvCliente
from app.models.usuario import UsuarioRole
from app.services.customer_maintenance import merge_customer_selection, resolve_customer


BASE = '/api/clientes/maintenance/customers'


def selection(db, uid):
    target, source, order, address, shipment = pair(db, uid)
    third = Cliente(nome='Ana Correa Silva', cpf='12345678909', documentos=[
        {'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'},
    ])
    db.add(third); db.flush()
    account = PdvCliente(nome='Nome no caixa', cadastro_cliente_id=third.id, saldo_fiado_gs=235)
    db.add(account); db.flush()
    return target, source, third, order, address, shipment, account


def body_for(target, *sources):
    return {'target_id': str(target.id), 'source_ids': [str(row.id) for row in sources]}


def test_selected_spelling_variants_need_explicit_review_and_keep_all_history(review_app):
    factory, client, uid = review_app
    with factory() as db:
        target, source, third, order, address, shipment, account = selection(db, uid)
        body = body_for(target, source, third)
        ids = (target.id, source.id, third.id, order.id, address.id, shipment.id, account.id)
        db.commit()
    preview = client.post(BASE + '/preview', json=body)
    assert preview.status_code == 200, preview.text
    plan = preview.json()
    assert plan['state'] == 'review_conflicts'
    assert plan['requires_reviewed_conflicts'] is True
    assert plan['conflicting_fields'] == ['nome']
    assert plan['links_to_move'] == {'orders': 1, 'tracking': 1, 'addresses': 1, 'pdv_customers': 1}
    assert next(row for row in plan['customers'] if row['id'] == str(ids[2]))['documents'] == [
        {'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}, {'tipo': 'CPF', 'pais': 'BR', 'numero': '12345678909'},
    ]
    request = {**body, 'confirm': True, 'plan_token': plan['plan_token']}
    assert client.post(BASE + '/confirm', json=request).status_code == 409
    with factory() as db:
        assert db.get(Cliente, ids[1]).merged_into_id is None
    response = client.post(BASE + '/confirm', json={**request, 'reviewed_conflicts': True})
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'merged'
    assert client.post(BASE + '/confirm', json={**request, 'reviewed_conflicts': True}).json()['state'] == 'already_merged'
    with factory() as db:
        principal = db.get(Cliente, ids[0])
        assert principal.nome == 'Ana Correia' and principal.cpf is None
        assert db.get(Cliente, ids[2]).cpf == '12345678909'
        assert db.get(Cliente, ids[2]).documentos[0]['numero'] == '1234567'
        assert resolve_customer(db, ids[1]).id == resolve_customer(db, ids[2]).id == principal.id
        assert db.get(Pedido, ids[3]).cliente_id == principal.id
        assert db.get(Pedido, ids[3]).cliente_nome == 'Recebedora original'
        assert db.get(SavedAddress, ids[4]).cliente_id == principal.id
        assert db.get(PdvCliente, ids[6]).cadastro_cliente_id == principal.id
        assert db.get(PdvCliente, ids[6]).saldo_fiado_gs == 235
        assert db.query(Cliente).count() == 3
        event = db.query(AuditEvent).filter_by(action='customers_merged').one()
        assert event.user_id == uid and event.changes['reviewed_conflicts'] == ['nome']
        assert '1234567' not in str(event.changes) and 'Ana' not in str(event.changes)


def test_sources_cannot_hide_conflicting_documents_or_contacts_behind_empty_target(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, first, second, *_ = selection(db, uid)
        first.email, second.email = 'first@example.test', 'second@example.test'
        first.documentos = [{'tipo': 'CI', 'pais': 'PY', 'numero': '7654321'}]
        db.flush()
        plan = merge_customer_selection(db, target.id, [first.id, second.id])
        assert set(plan['conflicting_fields']) == {'nome', 'email', 'documentos'}
        with pytest.raises(HTTPException, match='mesma pessoa'):
            merge_customer_selection(db, target.id, [first.id, second.id], apply=True, expected_plan=plan['plan_token'])
        assert first.merged_into_id is None and second.merged_into_id is None


def test_same_number_in_different_document_types_is_not_a_conflict(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, *_ = pair(db, uid)
        target.documentos = [{'tipo': 'CI', 'pais': 'PY', 'numero': '1234567'}]
        source.documentos = [{'tipo': 'RG', 'pais': 'BR', 'numero': '1234567', 'emissor': 'SP'}]
        db.flush()
        assert merge_customer_selection(db, target.id, [source.id])['conflicting_fields'] == []


def test_explicit_document_conflict_review_preserves_both_document_identities(env):
    from app.services.customer_identity import find_customer
    factory, _, uid, _ = env
    with factory() as db:
        target, source, *_ = pair(db, uid)
        target.cpf, source.cpf = '12345678909', '98765432100'
        db.flush()
        plan = merge_customer_selection(db, target.id, [source.id])
        assert plan['conflicting_fields'] == ['cpf']
        merge_customer_selection(db, target.id, [source.id], apply=True,
            expected_plan=plan['plan_token'], reviewed_conflicts=True)
        assert target.cpf == '12345678909' and source.cpf == '98765432100'
        assert find_customer(db, {'nome': 'Ana Correia', 'cpf': '12345678909'})[0].id == target.id
        assert find_customer(db, {'nome': 'Ana Correia', 'cpf': '98765432100'})[0].id == target.id


def test_preview_covers_group_principal_and_each_relationship(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, first, second, order, *_ = selection(db, uid)
        plan = merge_customer_selection(db, target.id, [first.id, second.id])
        assert merge_customer_selection(db, target.id, [second.id, first.id])['plan_token'] == plan['plan_token']
        for main, sources in [(first.id, [target.id, second.id]), (target.id, [first.id])]:
            with pytest.raises(HTTPException, match='nova prévia'):
                merge_customer_selection(db, main, sources, apply=True, expected_plan=plan['plan_token'], reviewed_conflicts=True)
        # Equal counts do not suffice: the relationship itself is part of review.
        order.cliente_id = second.id; db.flush()
        with pytest.raises(HTTPException, match='nova prévia'):
            merge_customer_selection(db, target.id, [first.id, second.id], apply=True,
                                     expected_plan=plan['plan_token'], reviewed_conflicts=True)
        assert first.merged_into_id is None and second.merged_into_id is None


def test_external_link_conflict_never_partially_merges_the_group(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, first, second, order, address, shipment, _ = selection(db, uid)
        outsider = Cliente(nome='Outra Pessoa'); db.add(outsider); db.flush()
        shipment.cliente_id = outsider.id; db.flush()
        with pytest.raises(HTTPException, match='fora da seleção'):
            merge_customer_selection(db, target.id, [first.id, second.id])
        assert first.merged_into_id is None and second.merged_into_id is None
        assert order.cliente_id == address.cliente_id == first.id


def test_confirmation_failure_rolls_back_all_members_and_links(review_app, monkeypatch):
    from app.api.endpoints import directory_duplicates as api
    factory, client, uid = review_app
    with factory() as db:
        target, first, second, order, address, *_ = selection(db, uid)
        body = body_for(target, first, second)
        source_ids = (first.id, second.id); address_id = address.id; order_id = order.id
        db.commit()
    plan = client.post(BASE + '/preview', json=body).json()
    original = api.merge_customer_selection
    def failure(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(409, 'Falha de validação antes de concluir.')
    monkeypatch.setattr(api, 'merge_customer_selection', failure)
    response = client.post(BASE + '/confirm', json={**body, 'confirm': True,
        'plan_token': plan['plan_token'], 'reviewed_conflicts': True})
    assert response.status_code == 409
    with factory() as db:
        assert all(db.get(Cliente, row_id).merged_into_id is None for row_id in source_ids)
        assert db.get(SavedAddress, address_id).cliente_id == source_ids[0]
        assert db.get(Pedido, order_id).cliente_id == source_ids[0]
        assert db.query(AuditEvent).filter_by(action='customers_merged').count() == 0


@pytest.mark.parametrize('invalid', ['none', 'too_many', 'repeat', 'principal', 'confirm_false'])
def test_selection_input_limits_and_identity_confirmation(review_app, invalid):
    _, client, _ = review_app
    target = str(uuid.uuid4()); source = str(uuid.uuid4())
    body = {'target_id': target, 'source_ids': [source]}
    if invalid == 'none': body['source_ids'] = []
    elif invalid == 'too_many': body['source_ids'] = [str(uuid.uuid4()) for _ in range(20)]
    elif invalid == 'repeat': body['source_ids'] = [source, source]
    elif invalid == 'principal': body['source_ids'] = [target]
    else:
        body.update(confirm=False, plan_token='a' * 64)
        assert client.post(BASE + '/confirm', json=body).status_code == 422
        return
    assert client.post(BASE + '/preview', json=body).status_code == 422


def test_selection_routes_require_owner_and_existing_customers(review_app):
    factory, client, uid = review_app
    body = {'target_id': str(uuid.uuid4()), 'source_ids': [str(uuid.uuid4())]}
    assert client.post(BASE + '/preview', json=body).status_code == 404
    with factory() as db:
        db.get(Usuario, uid).role = UsuarioRole.GERENTE; db.commit()
    assert client.post(BASE + '/preview', json=body).status_code == 403
    assert client.post(BASE + '/confirm', json={**body, 'confirm': True, 'plan_token': 'a' * 64}).status_code == 403
