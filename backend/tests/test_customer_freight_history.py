"""Reviewed freight snapshots can prove old parcels without rewriting history."""
from copy import deepcopy
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from test_assistant import setup
from test_address_manager import env
from app.models import Cliente, Rastreamento, Usuario
from app.models.access import AuditEvent
from app.models.address_book import FreightOrder, SavedAddress
from app.models.pdv import PdvCliente, PdvSale
from app.services.customer_reconciliation import preview_customer_links, apply_customer_links


ADDRESS = {'pais': 'BR', 'nome': 'Davi Sintético Ribeiro', 'endereco': 'Rua Central',
           'numero': '40', 'bairro': 'Centro', 'cidade': 'São Paulo', 'estado': 'SP', 'cep': '01001000'}
RECIPIENT = {'name': ADDRESS['nome'], 'address': ADDRESS['endereco'], 'number': ADDRESS['numero'],
             'district': ADDRESS['bairro'], 'city': ADDRESS['cidade'], 'state_abbr': ADDRESS['estado'],
             'postal_code': ADDRESS['cep']}


def seed(db, user_id, count=3, captured_null=False):
    customer = Cliente(nome=ADDRESS['nome'], cpf='12345678909',
                       endereco='Rua Central, 40, Centro, São Paulo, SP, 01001000, BR')
    db.add(customer); db.flush()
    address = SavedAddress(label='Casa sintética', created_by=user_id, data=ADDRESS.copy())
    db.add(address); db.flush()
    freights, parcels = [], []
    for index in range(count):
        code = f'QA{index + 1:09d}BR'
        payload = {'to': RECIPIENT.copy(), 'from': {'city': 'Origem sintética'}}
        if captured_null:
            payload['_customer_id'] = None
        freight = FreightOrder(request_key=uuid.uuid4(), user_id=user_id, address_id=address.id,
            environment='production', state='released', tracking=code, payload=payload, rates=[],
            price=Decimal('20.00'), label_pdf=b'%PDF-historical-unchanged')
        parcel = Rastreamento(codigo_rastreio=code, destinatario=ADDRESS['nome'], destino=ADDRESS['cidade'],
                             descricao='Detalhes históricos preservados')
        db.add_all([freight, parcel]); freights.append(freight); parcels.append(parcel)
    db.flush()
    return customer, address, freights, parcels


@pytest.mark.parametrize('captured_null', [False, True])
def test_read_only_preview_proposes_one_address_three_exact_parcels_and_apply_is_idempotent(env, captured_null):
    factory, _, user_id, _ = env
    with factory() as db:
        customer, address, freights, parcels = seed(db, user_id, captured_null=captured_null)
        account = PdvCliente(nome=customer.nome, cadastro_cliente_id=customer.id, saldo_fiado_gs=75)
        db.add(account); db.flush()
        purchase = PdvSale(cliente_id=account.id, cliente_nome='Nome da compra preservado', total_gs=100)
        db.add(purchase); db.flush()
        before = [(row.id, deepcopy(row.payload), row.label_pdf, row.price, row.address_id) for row in freights]
        statements = []
        def capture(_connection, _cursor, sql, _parameters, _context, _many):
            statements.append(sql)
        event.listen(db.bind, 'before_cursor_execute', capture)
        try:
            plan = preview_customer_links(db, customer)
        finally:
            event.remove(db.bind, 'before_cursor_execute', capture)
        assert all(sql.lstrip().upper().startswith(('SELECT', 'WITH')) for sql in statements)
        assert not any('freight_orders.label_pdf' in sql for sql in statements)
        assert plan['counts'] == {'addresses': 1, 'orders': 0, 'tracking': 3, 'pdv_accounts': 0}
        assert {row['reason'] for row in plan['items'] if row['kind'] == 'tracking'} == {'freight_name_address'}
        assert address.cliente_id is None and all(row.cliente_id is None for row in parcels)
        result = apply_customer_links(db, customer, plan['token'], db.get(Usuario, user_id))
        assert result['linked'] == plan['counts'] and not result['already_applied']
        assert address.cliente_id == customer.id and all(row.cliente_id == customer.id for row in parcels)
        assert before == [(row.id, row.payload, row.label_pdf, row.price, row.address_id) for row in freights]
        assert all(row.destino == ADDRESS['cidade'] and row.descricao == 'Detalhes históricos preservados' for row in parcels)
        assert account.saldo_fiado_gs == 75 and purchase.cliente_nome == 'Nome da compra preservado'
        assert db.query(PdvSale).count() == 1
        assert apply_customer_links(db, customer, plan['token'], db.get(Usuario, user_id))['already_applied']
        assert db.query(AuditEvent).filter_by(action='customer_history_reconciled').count() == 1


@pytest.mark.parametrize('conflict', ['address-owner', 'captured-owner', 'document', 'location',
    'recipient', 'tracking-recipient', 'sandbox', 'unpaid', 'different-code', 'duplicate-conflict'])
def test_freight_evidence_rejects_conflicting_identity_location_or_operation(env, conflict):
    factory, _, user_id, _ = env
    with factory() as db:
        customer, address, freights, parcels = seed(db, user_id, count=1)
        freight = freights[0]
        other = Cliente(nome='Outra Pessoa Sintética')
        db.add(other); db.flush()
        if conflict == 'address-owner':
            address.cliente_id = other.id
        elif conflict == 'captured-owner':
            freight.payload = {**freight.payload, '_customer_id': str(other.id)}
        elif conflict in ('document', 'location', 'recipient'):
            field, value = {'document': ('document', '52998224725'), 'location': ('number', '99'),
                            'recipient': ('name', other.nome)}[conflict]
            freight.payload = {**freight.payload, 'to': {**freight.payload['to'], field: value}}
        elif conflict == 'tracking-recipient':
            parcels[0].destinatario = other.nome
        elif conflict == 'sandbox':
            freight.environment = 'sandbox'
        elif conflict == 'unpaid':
            freight.state = 'pending'
        elif conflict == 'different-code':
            freight.tracking = 'QA999999999BR'
        else:
            db.add(FreightOrder(request_key=uuid.uuid4(), user_id=user_id, address_id=address.id,
                environment='production', state='released', tracking=freight.tracking, rates=[],
                payload={**freight.payload, '_customer_id': str(other.id)}))
        db.flush()
        assert preview_customer_links(db, customer)['counts']['tracking'] == 0
        assert parcels[0].cliente_id is None


@pytest.mark.parametrize('change', ['payload', 'address', 'account', 'captured', 'duplicate'])
def test_any_changed_freight_dependency_invalidates_the_preview_before_writes(env, change):
    factory, _, user_id, _ = env
    with factory() as db:
        customer, address, freights, parcels = seed(db, user_id, count=1)
        freight = freights[0]
        account = PdvCliente(nome=customer.nome, cadastro_cliente_id=customer.id)
        db.add(account); db.flush()
        address.pdv_cliente_id = account.id
        other = Cliente(nome='Outra Pessoa Sintética')
        db.add(other); db.flush()
        plan = preview_customer_links(db, customer)
        assert plan['counts']['tracking'] == 1
        if change == 'payload':
            freight.payload = {**freight.payload, 'to': {**freight.payload['to'], 'number': '99'}}
        elif change == 'address':
            address.data = {**address.data, 'numero': '99'}
        elif change == 'account':
            account.cadastro_cliente_id = other.id
        elif change == 'captured':
            freight.payload = {**freight.payload, '_customer_id': str(other.id)}
        else:
            db.add(FreightOrder(request_key=uuid.uuid4(), user_id=user_id, address_id=address.id,
                environment='production', state='released', tracking=freight.tracking, rates=[],
                payload={**freight.payload, '_customer_id': str(other.id)}))
        db.flush()
        with pytest.raises(HTTPException) as error:
            apply_customer_links(db, customer, plan['token'], db.get(Usuario, user_id))
        assert error.value.status_code == 409
        assert parcels[0].cliente_id is None and address.cliente_id is None
        assert db.query(AuditEvent).filter_by(action='customer_history_reconciled').count() == 0


def test_partial_freight_scan_never_uses_a_positive_match_to_hide_unread_conflicts(env):
    factory, _, user_id, _ = env
    with factory() as db:
        customer, address, freights, _ = seed(db, user_id, count=1)
        db.add(FreightOrder(request_key=uuid.uuid4(), user_id=user_id, address_id=address.id,
            environment='production', state='released', tracking=freights[0].tracking, rates=[],
            payload=deepcopy(freights[0].payload)))
        db.flush()
        plan = preview_customer_links(db, customer, limit=1)
        assert plan['limited'] and plan['counts']['tracking'] == 0


def test_captured_null_and_city_only_do_not_become_proof_after_an_address_is_linked(env):
    factory, _, user_id, _ = env
    with factory() as db:
        customer, address, freights, parcels = seed(db, user_id, count=1, captured_null=True)
        address.cliente_id = customer.id
        freights[0].payload = {'to': {'name': customer.nome, 'city': ADDRESS['cidade']}, '_customer_id': None}
        db.flush()
        assert preview_customer_links(db, customer)['counts']['tracking'] == 0
        assert parcels[0].cliente_id is None
