"""The address shortcut resolves directory owners and preserves exact PDV filters."""
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event

from test_assistant import setup
from test_address_manager import env
from test_customer_links import customer
from test_customer_purchases import account
from app.api.endpoints import address_manager
from app.dependencies import get_current_active_user
from app.models.address_book import SavedAddress
from app.models.usuario import Usuario, UsuarioRole


def address(db, user_id, *, person=None, buyer=None, parent=None, active=True, country='PY', label='Destino QA'):
    row = SavedAddress(label=label, created_by=user_id, data={'pais': country, 'nome': 'Snapshot QA'},
        cliente_id=person.id if person else None, pdv_cliente_id=buyer.id if buyer else None,
        merged_into_id=parent.id if parent else None, active=active)
    db.add(row); db.flush()
    return row


def results(client, customer_id, **params):
    response = client.get('/manager/addresses', params={'customer_id': str(customer_id), **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_directory_filter_includes_pdv_customer_aliases_and_preserves_other_filters(env):
    factory, client, user_id, _ = env
    with factory() as db:
        principal = customer(db, 'Pessoa QA'); other = customer(db, principal.nome)
        alias = customer(db, 'Nome anterior QA'); alias.merged_into_id = principal.id; alias.ativo = False
        buyer = account(db, alias, ativo=False)
        direct = address(db, user_id, person=alias, label='Casa principal')
        via_pdv = address(db, user_id, buyer=buyer, country='BR', label='Casa secundária')
        inactive = address(db, user_id, buyer=buyer, active=False)
        address(db, user_id, parent=via_pdv)
        address(db, user_id, person=other)
        address(db, user_id, person=other, buyer=buyer)  # Conflicting owners are not attributed.
        ids = principal.id, alias.id, direct.id, via_pdv.id, inactive.id
        db.commit()
    first = results(client, ids[0])
    assert first['total'] == 2
    assert {item['id'] for item in first['items']} == {str(ids[2]), str(ids[3])}
    assert results(client, ids[1]) == first
    assert results(client, ids[0], country='BR')['items'][0]['id'] == str(ids[3])
    assert results(client, ids[0], q='principal')['items'][0]['id'] == str(ids[2])
    assert results(client, ids[0], active='false')['items'][0]['id'] == str(ids[4])
    paginated = results(client, ids[0], offset=1, limit=1)
    assert paginated['total'] == 2 and len(paginated['items']) == 1
    assert paginated['items'][0] == first['items'][1]


def test_pdv_filter_remains_exact_including_accounts_without_directory_link_and_is_read_only(env):
    factory, client, user_id, _ = env
    with factory() as db:
        principal = customer(db, 'Pessoa QA')
        first, second, unlinked = account(db, principal), account(db, principal), account(db)
        one = address(db, user_id, buyer=first)
        address(db, user_id, buyer=second)
        orphan = address(db, user_id, buyer=unlinked)
        ids = first.id, unlinked.id, one.id, orphan.id
        db.commit(); engine = db.bind
    statements = []
    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, 'before_cursor_execute', record)
    try:
        linked = results(client, ids[0]); unknown = results(client, ids[1])
        missing = results(client, uuid.uuid4())
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert linked['total'] == 1 and linked['items'][0]['id'] == str(ids[2])
    assert unknown['total'] == 1 and unknown['items'][0]['id'] == str(ids[3])
    assert missing == {'total': 0, 'items': []}
    assert set(statements) <= {'SELECT', 'WITH'}
    assert linked['items'][0]['cliente_id'] is None
    assert linked['items'][0]['pdv_cliente_id'] == str(ids[0])


def test_customer_filter_keeps_manager_authorization():
    app = FastAPI(); app.include_router(address_manager.router, prefix='/manager')
    with TestClient(app) as client:
        assert client.get('/manager/addresses', params={'customer_id': str(uuid.uuid4())}).status_code in {401, 403}
        app.dependency_overrides[get_current_active_user] = lambda: Usuario(
            nome='Vendedor QA', email='filter-qa@example.test', senha_hash='unused', role=UsuarioRole.VENDEDOR)
        assert client.get('/manager/addresses', params={'customer_id': str(uuid.uuid4())}).status_code == 403
