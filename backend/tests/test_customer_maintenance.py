"""Explicit consolidation preserves identities and all operational history."""
import uuid
from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi import HTTPException
from test_assistant import setup
from test_address_manager import env
from app.api.endpoints import clientes
from app.dependencies import get_current_active_user, get_current_user
from app.database import Base
from app.models import Cliente, Pedido, Rastreamento, Usuario
from app.models.access import AuditEvent
from app.models.address_book import SavedAddress, FreightOrder
from app.models.printing import PrintJob
from app.models.pdv import PdvCliente
from app.models.assistant import utcnow
from app.models.pedido_tag import TagStatus, pedido_tags_association
from app.models.pedido_anexo import PedidoAnexo
from app.services.customer_maintenance import merge_customers, resolve_customer
from app.services.customer_identity import find_customer
from app.services.address_book import save_or_reuse
from app.services.user_audit import bind_actor


def pair(db, uid):
    target = Cliente(nome='Ana Correia', endereco='Endereço original')
    source = Cliente(nome='ANA CORREIA', endereco='Outro endereço')
    db.add_all([target, source]); db.flush()
    order = Pedido(numero_pedido=str(uuid.uuid4()), descricao='Original', valor_total=150,
                   cliente_id=source.id, cliente_nome='Recebedora original', endereco_entrega='Local da compra')
    address = SavedAddress(label='Casa', data={'pais':'PY','nome':'Ana Correia','cidade':'Asunción'},
                           cliente_id=source.id, created_by=uid)
    db.add_all([order, address]); db.flush()
    shipment = Rastreamento(codigo_rastreio='TEST123456789BR', cliente_id=source.id, pedido_id=order.id,
                           destinatario='Nome original do envio')
    db.add(shipment); db.flush()
    return target, source, order, address, shipment


def apply(db, target, source, **kwargs):
    plan = merge_customers(db, target.id, source.id, **kwargs)
    return merge_customers(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'], **kwargs)


def test_merge_preserves_history_snapshots_documents_and_old_ids(env):
    factory, _, uid, did = env
    with factory() as db:
        target, source, order, address, shipment = pair(db, uid)
        bind_actor(db, db.get(Usuario, uid), source='reconciliation')
        print_job = PrintJob(device_id=uuid.UUID(did), user_id=uid, request_key=uuid.uuid4(),
            address_id=address.id, snapshot={'data':deepcopy(address.data)}, pdf=b'original-pdf', sha256='a'*64,
            source='address', status='submitted', expires_at=utcnow()+timedelta(days=1))
        freight = FreightOrder(request_key=uuid.uuid4(), user_id=uid, address_id=address.id,
            environment='sandbox', state='paid', payload={'to':deepcopy(address.data)}, rates=[], tracking='ORIGINAL')
        db.add_all([print_job, freight]); db.flush()
        plan = merge_customers(db, target.id, source.id)
        assert plan['state'] == 'ready' and source.ativo and not source.merged_into_id
        assert plan['links_to_move'] == {'orders':1, 'tracking':1, 'addresses':1}
        assert merge_customers(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])['state'] == 'merged'
        assert order.cliente_id == shipment.cliente_id == address.cliente_id == target.id
        assert source.endereco == 'Outro endereço' and target.endereco == 'Endereço original'
        assert order.cliente_nome == 'Recebedora original' and order.endereco_entrega == 'Local da compra'
        assert order.valor_total == 150 and shipment.destinatario == 'Nome original do envio'
        assert address.version == 2 and address.data == print_job.snapshot['data'] == freight.payload['to']
        assert print_job.pdf == b'original-pdf' and print_job.status == 'submitted' and freight.tracking == 'ORIGINAL'
        assert not source.ativo and resolve_customer(db, source.id).id == target.id
        assert merge_customers(db, target.id, source.id, apply=True)['state'] == 'already_merged'
        assert db.query(Cliente).count() == 2
        event = db.query(AuditEvent).filter_by(action='customer_merged').one()
        assert event.user_id == uid and event.changes['links_moved'] == plan['links_to_move']
        assert 'Ana' not in str(event.changes)


def test_changed_plan_and_external_order_conflict_are_rejected(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, order, address, shipment = pair(db, uid)
        plan = merge_customers(db, target.id, source.id)
        address.version += 1; db.flush()
        with pytest.raises(HTTPException, match='nova simulação'):
            merge_customers(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])
        third = Cliente(nome='Outra Pessoa'); db.add(third); db.flush()
        shipment.cliente_id = third.id; db.flush()
        with pytest.raises(HTTPException, match='fora do par'):
            merge_customers(db, target.id, source.id)
        assert not source.merged_into_id and source.ativo


def test_merge_moves_pdv_links_without_merging_financial_accounts(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, *_ = pair(db, uid)
        first = PdvCliente(nome=target.nome, cadastro_cliente_id=target.id, saldo_fiado_gs=100)
        second = PdvCliente(nome=source.nome, cadastro_cliente_id=source.id, saldo_fiado_gs=200)
        db.add_all([first,second]); db.flush()
        result = apply(db, target, source)
        assert result['links_to_move']['pdv_customers'] == 1
        assert first.cadastro_cliente_id == second.cadastro_cliente_id == target.id
        assert first.saldo_fiado_gs == 100 and second.saldo_fiado_gs == 200
        assert first.id != second.id


def test_documents_require_explicit_review_and_keep_chosen_principal(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, *_ = pair(db, uid)
        target.cpf, source.cpf = '12345678909', '98765432100'
        target.telefone, source.telefone = '+595972111123', '+595972222124'
        db.flush()
        plan = merge_customers(db, target.id, source.id)
        assert plan['state'] == 'review_conflicts' and set(plan['conflicting_fields']) == {'cpf','telefone'}
        with pytest.raises(HTTPException, match='divergem'):
            merge_customers(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])
        assert apply(db, target, source, reviewed_conflicts=True)['state'] == 'merged'
        assert target.cpf == '12345678909' and source.cpf == '98765432100'
        assert target.telefone == '+595972111123'


def test_new_addresses_reuse_principal_and_known_alias_without_hiding_conflicts(env):
    factory, _, uid, _ = env
    with factory() as db:
        target, source, *_ = pair(db, uid)
        target.nome = 'Ana Correia Silva'; db.flush()
        apply(db, target, source)
        new, _ = save_or_reuse(db, {'pais':'PY','nome':'ANA CORREIA','cidade':'Encarnación'}, uid)
        assert new.cliente_id == target.id and not new.customer_link_review
        assert db.query(Cliente).count() == 2
        assert find_customer(db, {'nome':'Ana Correia'}, customers=db.query(Cliente).all())[0].id == target.id
        target.cpf = '12345678909'; db.flush()
        assert find_customer(db, {'nome':'Ana Correia','cpf':'98765432100'})[0] is None
        db.add(Cliente(nome='Ana Correia')); db.flush()
        assert find_customer(db, {'nome':'Ana Correia'})[0] is None


def test_customer_api_hides_aliases_redirects_history_and_rejects_stale_edits(env):
    factory, client, uid, _ = env
    client.app.include_router(clientes.router, prefix='/clientes')
    def user():
        with factory() as db: return db.get(Usuario, uid)
    client.app.dependency_overrides[get_current_active_user] = user
    client.app.dependency_overrides[get_current_user] = user
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[TagStatus.__table__, pedido_tags_association, PedidoAnexo.__table__])
        target, source, *_ = pair(db, uid)
        apply(db, target, source)
        tid, sid = str(target.id), str(source.id); db.commit()
    for url in ['/clientes/', '/clientes/?include_inactive=true', '/clientes/search?q=Ana']:
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert [row['id'] for row in response.json()] == [tid]
    assert client.get(f'/clientes/{sid}').json()['id'] == tid
    assert client.get(f'/clientes/{sid}/pedidos').json()[0]['cliente_id'] == tid
    assert client.get(f'/clientes/{sid}/logistica').json()['shipment_total'] == 1
    assert len(client.get(f'/clientes/{sid}/historico-enderecos').json()['addresses']) == 1
    assert client.put(f'/clientes/{sid}', json={'ativo':True}).status_code == 409
    assert client.delete(f'/clientes/{sid}').status_code == 409
    assert client.post('/clientes/', json={'nome':'ANA CORREIA'}).status_code == 409
    # A documented/contact conflict remains a separate identity, never auto-merged.
    assert client.post('/clientes/', json={'nome':'Outra Pessoa'}).status_code == 201
