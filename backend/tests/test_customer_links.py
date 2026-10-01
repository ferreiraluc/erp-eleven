"""Customer/parcel identities and partial fulfillment, with isolated database only."""
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_assistant import setup
from app.api.endpoints import clientes, pedidos, rastreamento
from app.database import Base, get_db
from app.dependencies import get_current_active_user, get_current_user
from app.models import Cliente, Pedido, Rastreamento, Usuario
from app.models.pedido import PedidoStatus
from app.models.pedido_anexo import PedidoAnexo
from app.models.pedido_tag import TagStatus, pedido_tags_association
from app.models.rastreamento import RastreamentoStatus
from app.services.customer_links import validate_tracking_links, customer_shipments
from app.services.rastreamento_sync import RastreamentoSyncService as Sync
from app.services.assistant_queries import query_shipments, ShipmentArgs


@pytest.fixture
def logistics(setup):
    factory, _, user_id = setup
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[TagStatus.__table__, pedido_tags_association, PedidoAnexo.__table__])
    app = FastAPI()
    app.include_router(clientes.router, prefix='/api/clientes')
    app.include_router(pedidos.router, prefix='/api/pedidos')
    app.include_router(rastreamento.router, prefix='/api/rastreamento')
    def session():
        with factory() as db:
            yield db
    def user():
        with factory() as db:
            return db.get(Usuario, user_id)
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = user
    app.dependency_overrides[get_current_user] = user
    return factory, TestClient(app), user_id


def customer(db, name='Ana'):
    row = Cliente(nome=name, ativo=True)
    db.add(row); db.flush()
    return row


def order(db, client=None, number=None, status=PedidoStatus.PROCESSANDO, **kwargs):
    row = Pedido(numero_pedido=number or str(uuid.uuid4()), descricao='Pacotes independentes', valor_total=1,
                 cliente_id=client.id if client else None, status=status, **kwargs)
    db.add(row); db.flush()
    return row


def parcel(db, code='AA123456789BR', client=None, pedido=None, status=RastreamentoStatus.PENDENTE, **kwargs):
    row = Rastreamento(codigo_rastreio=code, cliente_id=client.id if client else None,
                      pedido_id=pedido.id if pedido else None, status=status, **kwargs)
    db.add(row); db.flush()
    return row


def test_direct_link_and_legacy_order_link_never_match_names(logistics):
    factory, client, _ = logistics
    with factory() as db:
        ana = customer(db); homonym = customer(db)
        p = order(db, ana)
        parcel(db, 'DIRECT', client=ana, destinatario='Nome do recebedor')
        parcel(db, 'VIA-ORDER', pedido=p)
        parcel(db, 'SAME-NAME', client=homonym, destinatario='Ana')
        parcel(db, 'UNLINKED', destinatario='Ana')
        assert customer_shipments(db, ana.id).count() == 2
        customer_id = str(ana.id); db.commit()
    result = client.get(f'/api/clientes/{customer_id}/logistica').json()
    assert result['order_total'] == 1 and result['shipment_total'] == 2
    assert {row['codigo_rastreio'] for row in result['shipments']} == {'DIRECT', 'VIA-ORDER'}


def test_archiving_primary_tracking_selects_an_active_parcel_and_clears_last(logistics):
    factory,client,_=logistics
    with factory() as db:
        p=order(db,codigo_rastreio='FIRST')
        one=parcel(db,'FIRST',pedido=p);two=parcel(db,'SECOND',pedido=p)
        order_id,first_id,second_id=p.id,one.id,two.id;db.commit()
    assert client.delete(f'/api/rastreamento/{first_id}').status_code==200
    with factory() as db:assert db.get(Pedido,order_id).codigo_rastreio=='SECOND'
    assert client.delete(f'/api/rastreamento/{second_id}').status_code==200
    with factory() as db:assert db.get(Pedido,order_id).codigo_rastreio is None


def test_explicit_link_is_idempotent_preserves_snapshots_and_inherits_to_all_parcels(logistics):
    factory, client, _ = logistics
    with factory() as db:
        ana = customer(db); ana.endereco = 'Endereço atual do cadastro'
        p = order(db, cliente_nome='Recebedor original', endereco_entrega='Endereço da compra')
        parcel(db, 'ONE', pedido=p, destinatario='Histórico 1')
        parcel(db, 'TWO', pedido=p, destinatario='Histórico 2')
        ids = str(ana.id), str(p.id); db.commit()
    for _ in range(2):
        response = client.post(f'/api/clientes/{ids[0]}/vinculos', json={'kind': 'pedido', 'target_id': ids[1]})
        assert response.status_code == 200
    with factory() as db:
        p = db.get(Pedido, uuid.UUID(ids[1]))
        assert p.cliente_nome == 'Recebedor original' and p.endereco_entrega == 'Endereço da compra'
        assert all(str(row.cliente_id) == ids[0] for row in db.query(Rastreamento))
        assert {row.destinatario for row in db.query(Rastreamento)} == {'Histórico 1', 'Histórico 2'}
    assert len(client.get(f'/api/pedidos/{ids[1]}/rastreamentos').json()) == 2


def test_create_tracking_inherits_customer_and_rejects_conflicts_missing_ids(logistics):
    factory, client, _ = logistics
    with factory() as db:
        ana, other = customer(db), customer(db, 'Bia')
        p = order(db, ana); ids = str(ana.id), str(other.id), str(p.id); db.commit()
    response = client.post('/api/rastreamento/', json={'codigo_rastreio': ' aa123456789br ', 'pedido_id': ids[2]})
    assert response.status_code == 200
    assert response.json()['cliente_id'] == ids[0] and response.json()['codigo_rastreio'] == 'AA123456789BR'
    response = client.post('/api/rastreamento/', json={'codigo_rastreio': 'OTHER', 'pedido_id': ids[2], 'cliente_id': ids[1]})
    assert response.status_code == 409
    assert client.post('/api/rastreamento/', json={'codigo_rastreio': 'MISSING', 'pedido_id': str(uuid.uuid4())}).status_code == 404
    with factory() as db:
        assert db.query(Rastreamento).count() == 1


def test_existing_code_cannot_be_stolen_by_another_order(logistics):
    factory, _, user_id = logistics
    with factory() as db:
        first = order(db); second = order(db)
        row = parcel(db, pedido=first, status=RastreamentoStatus.EM_TRANSITO)
        with pytest.raises(HTTPException) as error:
            Sync.buscar_ou_criar_rastreamento(db, row.codigo_rastreio, second, user_id)
        assert error.value.status_code == 409
        assert row.pedido_id == first.id and row.status == RastreamentoStatus.EM_TRANSITO


@pytest.mark.parametrize(('states', 'expected'), [
    (['ENTREGUE', 'EM_TRANSITO'], PedidoStatus.ENVIADO),
    (['ENTREGUE', 'PENDENTE'], PedidoStatus.ENVIADO),
    (['ENTREGUE', 'ERRO'], PedidoStatus.ENVIADO),
    (['ENTREGUE', 'ENTREGUE'], PedidoStatus.ENTREGUE),
    (['ERRO', 'NAO_ENCONTRADO'], PedidoStatus.PROCESSANDO),
])
def test_order_status_considers_every_active_package(logistics, states, expected):
    factory, _, _ = logistics
    with factory() as db:
        p = order(db)
        rows = [parcel(db, str(i), pedido=p, status=RastreamentoStatus(status)) for i, status in enumerate(states)]
        Sync.sincronizar_rastreamento_com_pedido(db, rows[0])
        assert p.status == expected


def test_cancelled_orders_and_orders_without_parcels_keep_explicit_status(logistics):
    factory, _, _ = logistics
    with factory() as db:
        cancelled = order(db, status=PedidoStatus.CANCELADO)
        row = parcel(db, pedido=cancelled, status=RastreamentoStatus.ENTREGUE)
        Sync.sincronizar_rastreamento_com_pedido(db, row)
        assert cancelled.status == PedidoStatus.CANCELADO
        empty = order(db, status=PedidoStatus.PENDENTE)
        Sync.atualizar_status_por_pacotes(db, empty)
        assert empty.status == PedidoStatus.PENDENTE
        p = order(db)
        delivered = parcel(db, 'DELIVERED', pedido=p, status=RastreamentoStatus.ENTREGUE)
        parcel(db, 'ARCHIVED', pedido=p, ativo=False)
        Sync.sincronizar_rastreamento_com_pedido(db, delivered)
        assert p.status == PedidoStatus.ENTREGUE


def test_customer_change_rejected_if_parcels_belong_to_another_customer(logistics):
    factory, client, _ = logistics
    with factory() as db:
        first, other = customer(db), customer(db, 'Bia')
        p = order(db, first); parcel(db, client=first, pedido=p)
        ids = str(p.id), str(first.id), str(other.id); db.commit()
    response = client.put(f'/api/pedidos/{ids[0]}', json={'cliente_id': ids[2]})
    assert response.status_code == 409
    with factory() as db:
        assert str(db.get(Pedido, uuid.UUID(ids[0])).cliente_id) == ids[1]


def test_unlink_order_preserves_customer_and_package_history(logistics):
    factory, client, _ = logistics
    with factory() as db:
        ana = customer(db); p = order(db, ana, codigo_rastreio='FIRST')
        first = parcel(db, 'FIRST', client=ana, pedido=p)
        parcel(db, 'SECOND', client=ana, pedido=p)
        ids = str(first.id), str(p.id), str(ana.id); db.commit()
    response = client.put(f'/api/rastreamento/{ids[0]}', json={'pedido_id': None})
    assert response.status_code == 200 and response.json()['pedido_id'] is None
    assert response.json()['cliente_id'] == ids[2]
    with factory() as db:
        assert db.get(Pedido, uuid.UUID(ids[1])).codigo_rastreio == 'SECOND'
        assert db.query(Rastreamento).count() == 2


def test_bot_finds_direct_customer_link_and_retains_recipient_search(logistics):
    factory, _, _ = logistics
    with factory() as db:
        ana = customer(db, 'Cliente cadastrado')
        parcel(db, client=ana, destinatario='Recebedor diferente', status=RastreamentoStatus.EM_TRANSITO)
        for term in ('Cliente cadastrado', 'Recebedor diferente'):
            result = query_shipments(db, ShipmentArgs(termo=term))
            assert result['total'] == 1 and result['recomendado']['codigo'] == 'AA123456789BR'


def test_archived_duplicate_code_is_conflict_and_customer_link_cannot_move_it(logistics):
    factory, client, _ = logistics
    with factory() as db:
        ana = customer(db)
        row = parcel(db, ativo=False)
        ids = str(ana.id), str(row.id); db.commit()
    assert client.post('/api/rastreamento/', json={'codigo_rastreio': 'AA123456789BR'}).status_code == 409
    assert client.post(f'/api/clientes/{ids[0]}/vinculos', json={'kind': 'rastreamento', 'target_id': ids[1]}).status_code == 404


def test_legacy_code_whitespace_and_case_do_not_duplicate_across_inputs(logistics):
    factory, client, user_id = logistics
    with factory() as db:
        p = order(db, codigo_rastreio='AA123456789BR')
        row = parcel(db, ' aa 123\t456789br ', destinatario='Ana')
        original_id = row.id
        found, created = Sync.buscar_ou_criar_rastreamento(db, 'AA 123456789 BR', p, user_id)
        assert not created and found.id == original_id
        assert query_shipments(db, ShipmentArgs())['total'] == 1
        db.commit()
    assert client.post('/api/rastreamento/', json={'codigo_rastreio': 'AA123456789BR'}).status_code == 409
    assert client.get('/api/rastreamento/codigo/AA123456789BR').status_code == 200


def test_provider_delivery_refresh_updates_order_using_all_packages(logistics, monkeypatch):
    factory, client, _ = logistics
    with factory() as db:
        p = order(db)
        first = parcel(db, 'ONE', pedido=p, status=RastreamentoStatus.EM_TRANSITO)
        second = parcel(db, 'TWO', pedido=p, status=RastreamentoStatus.EM_TRANSITO)
        ids = str(first.id), str(second.id), str(p.id); db.commit()
    monkeypatch.setattr('app.services.wonca_service.parse_tracking', lambda _: ([], {}, RastreamentoStatus.ENTREGUE))
    assert client.post(f'/api/rastreamento/{ids[0]}/atualizar').status_code == 200
    with factory() as db:
        assert db.get(Pedido, uuid.UUID(ids[2])).status == PedidoStatus.ENVIADO
    assert client.post(f'/api/rastreamento/{ids[1]}/atualizar').status_code == 200
    with factory() as db:
        assert db.get(Pedido, uuid.UUID(ids[2])).status == PedidoStatus.ENTREGUE
