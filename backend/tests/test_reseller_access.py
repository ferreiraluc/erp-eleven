"""Restricted profiles are enforced with real JWT sessions, before handlers run."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import Depends, HTTPException

from app.dependencies import get_current_user
from app.models.usuario import Usuario, UsuarioRole
from app.api.endpoints import inventory, exchange_rates, rastreamento, clientes
from app.services.access_policy import RESELLER_READ_ROUTES, RESELLER_ACCOUNT_ACTIONS, require_profile_route
from test_access import setup, login


def restrict(factory, ids):
    with factory() as db:
        user = db.get(Usuario, ids['Junior'][0])
        user.access_profile = 'reseller'
        user.role = UsuarioRole.VENDEDOR
        user.sales_scope = 'own'
        db.commit()


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/access/users'), ('GET', '/api/access/audit'),
    ('GET', '/api/pdv/sales'), ('POST', '/api/pdv/sales'),
    ('GET', '/api/dashboard/stats'), ('GET', '/api/clientes/'),
    ('POST', '/api/clientes/'), ('GET', '/api/rastreamento/'),
    ('POST', '/api/rastreamento/'), ('GET', '/api/inventory/diagnostics'),
    ('GET', '/api/inventory/movements'), ('GET', '/api/inventory/sessions'),
    ('GET', '/api/inventory/items/00000000-0000-0000-0000-000000000001/history'),
    ('POST', '/api/inventory/items'), ('PATCH', '/api/inventory/items/batch'),
    ('POST', '/api/inventory/items/transfer-bulk'), ('POST', '/api/inventory/movements'),
    ('POST', '/api/inventory/items/00000000-0000-0000-0000-000000000001/quick-exit'),
    ('POST', '/api/exchange-rates/quick-update'),
])
def test_restricted_profile_blocks_real_routes_before_data_or_writes(setup, method, path):
    client, factory, ids = setup
    for prefix, module in [('inventory', inventory), ('exchange-rates', exchange_rates), ('rastreamento', rastreamento), ('clientes', clientes)]:
        client.app.include_router(module.router, prefix='/api/' + prefix)
    restrict(factory, ids)
    response = client.request(method, path, headers=login(client, 'Junior'), json={} if method != 'GET' else None)
    assert response.status_code == 403, response.text
    assert 'somente consultar' in response.text


def test_every_allowed_route_passes_the_central_dependency_and_unknown_routes_fail_closed(setup):
    client, factory, ids = setup
    restrict(factory, ids)
    headers = login(client, 'Junior')
    response = client.get('/api/auth/me', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['access_profile'] == 'reseller'
    # Probe exactly the registered templates: authorization is independent of
    # whether the individual catalog endpoint needs a specific fixture record.
    async def allowed(user=Depends(get_current_user)):
        return {'profile': user.access_profile}
    for route in sorted(RESELLER_READ_ROUTES - {'/api/auth/me'}, key=len, reverse=True):
        client.app.add_api_route(route, allowed, methods=['GET'])
        path = route.replace('{item_id}', str(uuid.uuid4())).replace('{lot_id}', str(uuid.uuid4())).replace('{currency_pair}', 'USD_TO_PYG').replace('{code}', 'INV-TEST')
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (route, response.text)
    client.app.add_api_route('/api/new-private-module', allowed, methods=['GET'])
    assert client.get('/api/new-private-module', headers=headers).status_code == 403
    for method, route in RESELLER_ACCOUNT_ACTIONS:
        require_profile_route(SimpleNamespace(access_profile='reseller'), method, route)
    with pytest.raises(HTTPException):
        require_profile_route(SimpleNamespace(access_profile='reseller'), 'POST', '/api/notifications/admin')
    require_profile_route(SimpleNamespace(access_profile='standard'), 'POST', '/api/new-private-module')


def test_catalog_details_are_readable_but_never_writable(setup):
    from app.database import Base
    from app.models.inventory import Item, Supplier
    client, factory, ids = setup
    client.app.include_router(inventory.router, prefix='/api/inventory')
    restrict(factory, ids)
    item_id = uuid.uuid4()
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[Supplier.__table__, Item.__table__])
        db.add(Item(id=item_id, name='Peça de teste', sku_internal='FIXTURE-1', stock_loja=2,
                    stock_deposito=7, current_stock=9, cost_price=12, sale_price=25))
        db.commit()
    headers = login(client, 'Junior')
    response = client.get('/api/inventory/items/' + str(item_id), headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['stock_loja'] == 2 and response.json()['stock_deposito'] == 7
    assert float(response.json()['cost_price']) == 12
    assert client.put('/api/inventory/items/' + str(item_id), headers=headers, json={'name': 'Changed'}).status_code == 403
    assert client.delete('/api/inventory/items/' + str(item_id), headers=headers).status_code == 403
    with factory() as db:
        assert db.get(Item, item_id).name == 'Peça de teste'


def test_allowlist_contains_only_registered_read_routes_and_account_actions():
    from fastapi import FastAPI
    from app.api.endpoints import auth, notifications, notification_push
    app = FastAPI()
    for prefix, module in [('auth', auth), ('inventory', inventory), ('exchange-rates', exchange_rates), ('notifications', notifications)]:
        app.include_router(module.router, prefix='/api/' + prefix)
    app.include_router(notification_push.router)
    paths = app.openapi()['paths']
    for route in RESELLER_READ_ROUTES:
        assert 'get' in paths[route], route
    for method, route in RESELLER_ACCOUNT_ACTIONS:
        assert method.lower() in paths[route], route


def test_owner_creates_reseller_without_seller_binding_and_legacy_update_preserves_restriction(setup):
    client, factory, ids = setup
    owner = login(client)
    body = {'nome': 'Revendedor QA', 'email': 'reseller@example.com', 'password': 'temporary-test',
            'ativo': True, 'sales_scope': 'all', 'access_profile': 'reseller'}
    response = client.post('/api/access/users', headers=owner, json=body)
    assert response.status_code == 201, response.text
    created = response.json()
    assert (created['access_profile'], created['role'], created['sales_scope']) == ('reseller', 'VENDEDOR', 'own')
    update = {'nome': 'Revendedor atualizado', 'ativo': True, 'sales_scope': 'all'}
    edited = client.put('/api/access/users/' + created['id'], headers=owner, json=update)
    assert edited.status_code == 200, edited.text
    assert (edited.json()['access_profile'], edited.json()['role'], edited.json()['sales_scope']) == ('reseller', 'VENDEDOR', 'own')
    # Promotion is explicit and retains the existing requirements for own sales.
    denied = client.put('/api/access/users/' + created['id'], headers=owner,
                        json={**update, 'access_profile': 'standard', 'sales_scope': 'own'})
    assert denied.status_code == 400
    assert client.put('/api/access/users/' + str(ids['Lucas'][0]), headers=owner,
                      json={**update, 'access_profile': 'reseller'}).status_code == 400


def test_profile_change_revokes_old_sessions_and_blocks_existing_bot_identity(setup):
    from app.database import Base
    from app.models.assistant import AssistantIdentity
    from app.services.assistant_channels import authorized_identity
    client, factory, ids = setup
    previous = login(client, 'Junior')
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[AssistantIdentity.__table__])
        identity = AssistantIdentity(channel='whatsapp_web', external_id='whatsapp:+5511999999999', user_id=ids['Junior'][0], active=True)
        db.add(identity); db.commit()
        assert authorized_identity(db, identity.channel, identity.external_id)
    result = client.put('/api/access/users/' + str(ids['Junior'][0]), headers=login(client),
                        json={'nome': 'Junior', 'ativo': True, 'sales_scope': 'own', 'access_profile': 'reseller'})
    assert result.status_code == 200, result.text
    assert client.get('/api/auth/me', headers=previous).status_code == 401
    with factory() as db:
        assert authorized_identity(db, 'whatsapp_web', 'whatsapp:+5511999999999') is None
        from app.services.assistant_tools import execute_tool, draft_note, confirm_note
        message = SimpleNamespace(user_id=ids['Junior'][0])
        identity = SimpleNamespace(can_register=True)
        assert 'erro' in execute_tool(db, message, identity, 'preparar_entrada_estoque', {})
        assert 'erro' in draft_note(db, message, identity, 'geral', 'Não deve gravar')
        assert 'permissão' in confirm_note(db, message, identity, str(uuid.uuid4()))
