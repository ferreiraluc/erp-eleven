"""Commercial order scope cannot be bypassed through shared customer logistics."""
import uuid
from types import SimpleNamespace

from app.models import Usuario
from app.models.pedido import Pedido
from app.models.usuario import UsuarioRole
from app.services.assistant_queries import OrderArgs, StockArgs, query_orders, query_stock
from app.services.assistant_tools import execute_tool
from app.services.customer_reconciliation import preview_customer_links, reconcile
from app.database import Base
from test_assistant import setup
from test_customer_links import logistics, customer, order, parcel
from test_customer_activity import activity_env
from test_inventory_ocr import item


def seed(factory, uid, *, role=UsuarioRole.VENDEDOR):
    with factory() as db:
        user = db.get(Usuario, uid)
        user.role, user.sales_scope = role, 'own'
        other = Usuario(nome='Outro vendedor sintético', email='seller-scope@example.test', role=UsuarioRole.VENDEDOR,
                        senha_hash='not-used', sales_scope='own')
        db.add(other)
        db.flush()
        person = customer(db, 'Cliente Escopo QA')
        own = order(db, person, number='OWN-COMMERCE', commerce_status='reserved', vendedor_id=uid,
                    cliente_nome=person.nome, usd_rate_gs=6000, subtotal_gs=10, total_gs=10, paid_gs=0)
        hidden = order(db, person, number='OTHER-COMMERCE', commerce_status='reserved', vendedor_id=other.id,
                       cliente_nome=person.nome, usd_rate_gs=6000, subtotal_gs=20, total_gs=20, paid_gs=0)
        legacy = order(db, person, number='LEGACY-SHARED')
        parcel(db, 'SHARED-LOGISTICS', person, hidden)
        ids = person.id, own.id, hidden.id, legacy.id
        db.commit()
        return ids


def test_customer_order_lists_and_counts_scope_only_commerce_preserving_shipping(activity_env):
    factory, client, uid = activity_env
    person, own, hidden, legacy = seed(factory, uid)
    response = client.get(f'/api/clientes/{person}/pedidos')
    assert response.status_code == 200, response.text
    assert {row['id'] for row in response.json()} == {str(own), str(legacy)}
    response = client.get(f'/api/clientes/{person}/logistica')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['order_total'] == 2 and {row['id'] for row in data['orders']} == {str(own), str(legacy)}
    assert data['shipment_total'] == 1 and data['shipments'][0]['codigo_rastreio'] == 'SHARED-LOGISTICS'
    data = client.get('/api/clientes/pagina').json()
    assert data['items'][0]['activity']['order_count'] == 2
    assert data['items'][0]['activity']['shipment_count'] == 1


def test_non_commerce_role_keeps_legacy_logistics_without_financial_orders(activity_env):
    factory, client, uid = activity_env
    person, _, _, legacy = seed(factory, uid, role=UsuarioRole.LIMPEZA)
    data = client.get(f'/api/clientes/{person}/pedidos').json()
    assert [row['id'] for row in data] == [str(legacy)]


def test_customer_link_endpoint_cannot_change_commercial_customer_or_bypass_scope(activity_env):
    factory, client, uid = activity_env
    person, own, hidden, _ = seed(factory, uid)
    assert client.post(f'/api/clientes/{person}/vinculos', json={'kind': 'pedido', 'target_id': str(own)}).status_code == 409
    assert client.post(f'/api/clientes/{person}/vinculos', json={'kind': 'pedido', 'target_id': str(hidden)}).status_code == 404
    with factory() as db:
        assert db.get(Pedido, own).cliente_id == db.get(Pedido, hidden).cliente_id == person


def test_bot_order_lookup_has_same_personal_scope_and_no_implicit_financial_access(activity_env):
    factory, _, uid = activity_env
    seed(factory, uid)
    with factory() as db:
        user = db.get(Usuario, uid)
        scoped = query_orders(db, OrderArgs(), user=user)
        assert {row['pedido'] for row in scoped['resultados']} == {'OWN-COMMERCE', 'LEGACY-SHARED'}
        assert scoped['total'] == 2
        assert query_orders(db, OrderArgs())['total'] == 1
        via_bot = execute_tool(db, SimpleNamespace(user_id=uid), None, 'consultar_pedidos', {})
        assert {row['pedido'] for row in via_bot['resultados']} == {'OWN-COMMERCE', 'LEGACY-SHARED'}


def test_legacy_reconciliation_cannot_reassign_a_commercial_order_behind_its_pdv_account(activity_env):
    factory, _, uid = activity_env
    with factory() as db:
        Base.metadata.create_all(db.bind)
        person = customer(db, 'Cliente Evidência QA')
        person.telefone = '+5511999998888'
        held = order(db, number='UNLINKED-COMMERCE', commerce_status='reserved', vendedor_id=uid,
                     cliente_nome=person.nome, cliente_telefone=person.telefone)
        db.flush()
        preview = preview_customer_links(db, person)
        assert not any(row['kind'] == 'order' and row['id'] == str(held.id) for row in preview['items'])
        result = reconcile(db)
        assert result['orders_linked'] == 0
        assert held.cliente_id is None


def test_bot_stock_totals_and_filters_exclude_held_units(setup):
    factory, _, _ = setup
    with factory() as db:
        row = item(db, loja=1, deposito=2, reserved_loja=1, reserved_deposito=1)
        db.commit()
        data = query_stock(db, StockArgs(local='total'))
        assert data['unidades'] == 1 and data['saldos_por_local'] == {'total': 1, 'loja': 0, 'deposito': 1}
        line = data['resultados'][0]
        assert line['total'] == 1 and line['estoque_fisico']['total'] == 3
        assert line['reservado'] == {'loja': 1, 'deposito': 1}
        assert query_stock(db, StockArgs(local='loja', situacao='disponivel'))['total'] == 0
