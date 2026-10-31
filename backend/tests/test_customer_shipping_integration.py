"""Synthetic local flow from a linked PDV purchase to address, parcels and queue.

Freight rows are historical fixtures, not provider purchases. No network, payment
or printer dispatch is allowed; only persisted links and pending jobs are checked.
"""
from decimal import Decimal
import uuid

import pytest

from test_assistant import setup, incoming
from test_customer_links import logistics
from test_customer_purchases import account, sale
from app.database import Base
from app.models import Cliente, Pedido, Rastreamento, Usuario
from app.models.access import AuditEvent
from app.models.address_book import FreightOrder, PrintLayout, SavedAddress
from app.models.assistant import AssistantAction
from app.models.pdv import PdvCliente, PdvPayment, PdvSale, PdvSaleItem
from app.models.printing import PrintDevice, PrintJob, PrintSender
from app.models.usuario import UsuarioRole
from app.services import assistant_channels, superfrete
from app.services.address_book import save_or_reuse
from app.services.assistant_printing import AddressArgs, prepare_print
from app.services.assistant_schedule import confirm_action


ADDRESS = {
    'pais': 'BR', 'nome': 'Ana Sintética Silva', 'cpf': '12345678909',
    'documento_tipo': 'CPF', 'telefone': '+5545998765432',
    'endereco': 'Rua Sintética', 'numero': '12', 'bairro': 'Centro',
    'cidade': 'Foz do Iguaçu', 'estado': 'PR', 'cep': '85865-310',
}
DEVICE_ID = uuid.UUID('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')


@pytest.fixture
def shipping_env(logistics, monkeypatch):
    factory, client, user_id = logistics
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[
            SavedAddress.__table__, PrintDevice.__table__, PrintJob.__table__,
            FreightOrder.__table__, PrintLayout.__table__, PrintSender.__table__,
            PdvSaleItem.__table__, PdvPayment.__table__, AuditEvent.__table__,
        ])
        db.get(Usuario, user_id).role = UsuarioRole.ADMIN
        db.add(PrintDevice(id=DEVICE_ID, name='Impressora sintética', token_hash='synthetic-device'))
        db.add(PrintSender(id='synthetic', name='Remetente sintético', lines=['Rua QA, 1']))
        db.commit()

    def no_external_effect(*args, **kwargs):
        raise AssertionError('This integration test must remain entirely local')

    monkeypatch.setattr(superfrete, 'call', no_external_effect)
    monkeypatch.setattr(superfrete, 'label_pdf', no_external_effect)
    monkeypatch.setattr(superfrete.settings, 'SUPERFRETE_SANDBOX', False)
    monkeypatch.setattr(superfrete.requests.sessions.Session, 'request', no_external_effect)
    return factory, client, user_id


def bot_address(db, user_id, data):
    """Use the real preview/confirmation boundary, without model or channel calls."""
    identity = assistant_channels.authorized_identity(db, 'telegram', '123')
    message = incoming(db, user_id, 'Imprima este endereço sintético', channel='telegram')
    before_addresses = db.query(SavedAddress).count()
    before_jobs = db.query(PrintJob).count()
    result = prepare_print(db, message, identity, AddressArgs(**data, remetente='synthetic'))
    assert 'confirmacao' in result
    action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
    assert action.status == 'draft'
    assert db.query(SavedAddress).count() == before_addresses
    assert db.query(PrintJob).count() == before_jobs

    confirmation = incoming(db, user_id, 'Confirmo', channel='telegram')
    assert 'fila de impressão' in confirm_action(db, confirmation, identity, action)
    db.flush()
    job = db.get(PrintJob, action.result_id)
    assert job.status == 'pending'
    assert job.snapshot['endereco']['nome'] == data['nome']
    assert 'Nenhuma alteração foi repetida' in confirm_action(db, confirmation, identity, action)
    assert db.query(PrintJob).count() == before_jobs + 1
    return db.get(SavedAddress, job.address_id), job


def stored_freight(db, recipient, user_id, code):
    row = FreightOrder(
        request_key=uuid.uuid4(), user_id=user_id, address_id=recipient.id,
        environment='production', state='released', price=Decimal('20.00'),
        tracking=code, rates=[], label_pdf=b'%PDF-1.4\nsynthetic-stored-fixture',
        payload={'to': {'name': recipient.data['nome'], 'city': recipient.data['cidade']},
                 'from': {'city': 'Cidade QA'}},
    )
    db.add(row); db.flush()
    return row


def activity_page(client):
    response = client.get('/api/clientes/pagina')
    assert response.status_code == 200, response.text
    return {row['id']: row['activity'] for row in response.json()['items']}


@pytest.mark.parametrize('saved_account_address', [False, True], ids=['new-bot-address', 'reuse-pdv-address'])
def test_linked_purchase_three_parcels_and_confirmed_prints_share_customer_card(shipping_env, saved_account_address):
    factory, client, user_id = shipping_env
    with factory() as db:
        person = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'], telefone=ADDRESS['telefone'])
        homonym = Cliente(nome=ADDRESS['nome'], cpf='52998224725')
        db.add_all([person, homonym]); db.flush()
        buyer = account(db, person, nome=ADDRESS['nome'], doc=ADDRESS['cpf'], doc_tipo='CPF', doc_pais='BR',
                        saldo_fiado_gs=Decimal('75.00'))
        purchase = sale(db, buyer, user_id, cliente_nome='Nome preservado da compra', total='100')
        if saved_account_address:
            selected, _ = save_or_reuse(db, ADDRESS.copy(), user_id, pdv_cliente_id=buyer.id)
            selected_id = selected.id
        recipient, a4_job = bot_address(db, user_id, ADDRESS)
        if saved_account_address:
            assert recipient.id == selected_id and recipient.pdv_cliente_id == buyer.id
        assert db.query(SavedAddress).count() == 1

        freight_ids, job_ids = [], [a4_job.id]
        for index in range(3):
            freight = stored_freight(db, recipient, user_id, f'QA{index + 1:09d}BR')
            request_key = uuid.uuid4()
            superfrete.sync_tracking(db, freight)
            superfrete.sync_tracking(db, freight)
            job = superfrete.print_label(db, freight.id, DEVICE_ID, request_key, user_id)
            repeated = superfrete.print_label(db, freight.id, DEVICE_ID, request_key, user_id)
            assert repeated.id == job.id and job.status == 'pending'
            freight_ids.append(freight.id); job_ids.append(job.id)

        assert db.query(Rastreamento).count() == 3
        assert db.query(PrintJob).count() == 4
        assert db.query(Cliente).count() == 2
        assert db.query(PdvCliente).count() == db.query(PdvSale).count() == 1
        assert buyer.saldo_fiado_gs == Decimal('75.00')
        assert purchase.cliente_nome == 'Nome preservado da compra'
        customer_id, other_id = str(person.id), str(homonym.id)
        db.commit()

    activity = activity_page(client)
    assert activity[customer_id]['purchase_count'] == 1
    assert activity[customer_id]['shipment_count'] == 3
    assert activity[customer_id]['print_count'] == 4
    assert activity[customer_id]['pending_print_count'] == 4
    assert activity[customer_id]['submitted_print_count'] == 0
    assert activity[other_id]['purchase_count'] == activity[other_id]['shipment_count'] == activity[other_id]['print_count'] == 0
    response = client.get(f'/api/clientes/{customer_id}/historico-enderecos')
    assert response.status_code == 200, response.text
    history = response.json()
    assert history['total'] == 7
    assert {row['id'] for row in history['items']} == {str(key) for key in freight_ids + job_ids}
    assert history['summary']['labels'] == 3 and history['summary']['prints'] == 4
    assert history['summary']['completed_prints'] == 0


@pytest.mark.parametrize('conflict', ['homonyms', 'different-document', 'document-other-name'])
def test_bot_shipping_keeps_uncorroborated_identity_out_of_customer_cards(shipping_env, conflict):
    factory, client, user_id = shipping_env
    with factory() as db:
        person = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        db.add(person); db.flush()
        data = ADDRESS.copy()
        if conflict == 'homonyms':
            db.add(Cliente(nome=ADDRESS['nome']))
            data['cpf'] = ''
        elif conflict == 'different-document':
            data['cpf'] = '52998224725'
        else:
            data['nome'] = 'Outra Pessoa Sintética'
        db.flush()
        customer_count = db.query(Cliente).count()
        recipient, _ = bot_address(db, user_id, data)
        assert recipient.cliente_id is None and recipient.customer_link_review
        freight = stored_freight(db, recipient, user_id, 'QA900000001BR')
        superfrete.sync_tracking(db, freight)
        superfrete.sync_tracking(db, freight)
        assert db.query(Rastreamento).one().cliente_id is None
        assert db.query(Cliente).count() == customer_count
        db.commit()
    for activity in activity_page(client).values():
        assert activity['purchase_count'] == activity['shipment_count'] == activity['print_count'] == 0


@pytest.mark.parametrize('existing_link', ['unlinked', 'same-customer', 'other-customer', 'other-order'])
def test_freight_sync_can_fill_an_existing_unowned_parcel_without_overriding_explicit_links(shipping_env, existing_link):
    factory, _, user_id = shipping_env
    with factory() as db:
        person = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        other = Cliente(nome='Outra Pessoa Sintética')
        db.add_all([person, other]); db.flush()
        recipient, _ = save_or_reuse(db, ADDRESS.copy(), user_id, cliente_id=person.id)
        freight = stored_freight(db, recipient, user_id, 'QA800000001BR')
        original_link = person.id if existing_link == 'same-customer' else other.id if existing_link == 'other-customer' else None
        original_recipient = ADDRESS['nome'].upper()
        parcel = Rastreamento(codigo_rastreio=' qa800000001br ', destinatario=original_recipient,
                             destino='Destino histórico', cliente_id=original_link, descricao='Observação preservada')
        if existing_link == 'other-order':
            order = Pedido(numero_pedido='QA-OTHER', descricao='Pedido sintético', valor_total=99,
                           cliente_nome=other.nome, cliente_id=other.id)
            db.add(order); db.flush()
            parcel.pedido_id = order.id
        db.add(parcel); db.flush()
        parcel_id, order_id = parcel.id, parcel.pedido_id

        superfrete.sync_tracking(db, freight)
        superfrete.sync_tracking(db, freight)
        db.flush()
        assert db.query(Rastreamento).count() == 1
        parcel = db.get(Rastreamento, parcel_id)
        expected = person.id if existing_link in ('unlinked', 'same-customer') else original_link
        assert parcel.cliente_id == expected
        assert parcel.pedido_id == order_id
        assert parcel.codigo_rastreio == ' qa800000001br '
        assert parcel.destinatario == original_recipient
        assert parcel.destino == 'Destino histórico' and parcel.descricao == 'Observação preservada'


@pytest.mark.parametrize('captured_customer', ['person', 'unresolved'])
def test_freight_customer_snapshot_is_stable_after_the_address_is_reassigned(shipping_env, captured_customer):
    factory, _, user_id = shipping_env
    with factory() as db:
        person = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        other = Cliente(nome='Outra Pessoa Sintética')
        db.add_all([person, other]); db.flush()
        recipient, _ = save_or_reuse(db, ADDRESS.copy(), user_id, cliente_id=person.id)
        freight = stored_freight(db, recipient, user_id, 'QA700000001BR')
        freight.payload = {**freight.payload, '_customer_id': str(person.id) if captured_customer == 'person' else None}
        recipient.cliente_id = other.id
        db.flush()

        superfrete.sync_tracking(db, freight)
        superfrete.sync_tracking(db, freight)
        parcel = db.query(Rastreamento).one()
        assert parcel.cliente_id == (person.id if captured_customer == 'person' else None)
        assert parcel.destinatario == ADDRESS['nome']
        assert recipient.cliente_id == other.id


@pytest.mark.parametrize('link', ['corroborated', 'pdv', 'unresolved'])
def test_quote_captures_customer_once_and_keeps_private_identity_out_of_provider_payload(shipping_env, monkeypatch, link):
    from app.services import postal_codes
    factory, _, user_id = shipping_env
    monkeypatch.setattr(postal_codes, 'complete_address', lambda data: {'data': data, 'warnings': []})
    calls = []

    def provider(method, path, body):
        calls.append(path)
        assert '_customer_id' not in body and not any(key.startswith('_') for key in body)
        if path == 'calculator':
            return [{'id': 1, 'name': 'PAC', 'price': '20.00'}]
        assert path == 'cart'
        return {'id': 'synthetic-cart', 'price': '20.00'}

    monkeypatch.setattr(superfrete, 'call', provider)
    with factory() as db:
        person = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'])
        db.add(person); db.flush()
        buyer = account(db, person, nome=ADDRESS['nome']) if link == 'pdv' else None
        data = {**ADDRESS, 'cpf': '52998224725'} if link == 'unresolved' else ADDRESS.copy()
        address = SavedAddress(label='Destino sintético', data=data, created_by=user_id,
                               pdv_cliente_id=buyer.id if buyer else None)
        db.add(address); db.flush()
        body = superfrete.QuoteInput(request_key=uuid.uuid4(), address_id=address.id, remetente=ADDRESS,
            package={'weight': 1, 'height': 10, 'width': 15, 'length': 20},
            products=[{'name': 'Camiseta sintética', 'quantity': 1, 'unitary_value': '10.00'}], non_commercial=True)
        freight = superfrete.quote_order(db, body, user_id)
        assert freight.state == 'quoted'
        assert '_customer_id' in freight.payload
        assert freight.payload['_customer_id'] == (None if link == 'unresolved' else str(person.id))
        assert not (address.cliente_id and address.pdv_cliente_id)
        assert db.query(Cliente).count() == 1
        if link == 'unresolved':
            assert address.customer_link_review
        repeated = superfrete.quote_order(db, body, user_id)
        assert repeated.id == freight.id and calls == ['calculator']
        superfrete.cart(db, freight.id, 1)
        assert calls == ['calculator', 'cart']
        assert db.query(PrintJob).count() == db.query(Rastreamento).count() == 0


@pytest.mark.parametrize('link', ['direct-alias', 'pdv-alias', 'conflicting-pdv', 'changed-legacy-recipient'])
def test_legacy_freight_follows_confirmed_aliases_without_accepting_conflicting_identity(shipping_env, link):
    factory, _, user_id = shipping_env
    with factory() as db:
        person = Cliente(nome='Ana Nome Atual')
        db.add(person); db.flush()
        alias = Cliente(nome=ADDRESS['nome'], cpf=ADDRESS['cpf'], merged_into_id=person.id, ativo=False)
        db.add(alias); db.flush()
        buyer = account(db, alias, nome=ADDRESS['nome'], doc=ADDRESS['cpf'], doc_tipo='CPF', doc_pais='BR')
        recipient = SavedAddress(label='Principal sintético', data=ADDRESS.copy(), created_by=user_id,
            cliente_id=alias.id if link == 'direct-alias' else None,
            pdv_cliente_id=buyer.id if link != 'direct-alias' else None)
        db.add(recipient); db.flush()
        old_address = SavedAddress(label='Alias sintético', data={}, created_by=user_id,
                                   merged_into_id=recipient.id, active=False)
        db.add(old_address); db.flush()
        freight = stored_freight(db, recipient, user_id, 'QA600000001BR')
        freight.address_id = old_address.id
        if link == 'conflicting-pdv':
            buyer.doc = '52998224725'
        elif link == 'changed-legacy-recipient':
            freight.payload = {**freight.payload, 'to': {'name': 'Outra Pessoa Sintética', 'city': 'Cidade QA'}}
        db.flush()
        superfrete.sync_tracking(db, freight)
        expected = person.id if link in ('direct-alias', 'pdv-alias') else None
        assert db.query(Rastreamento).one().cliente_id == expected
        assert freight.address_id == old_address.id
        assert buyer.cadastro_cliente_id == alias.id
