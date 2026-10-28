"""Customer cards read linked activity in batches, without financial inference."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import event

from test_assistant import setup
from test_customer_links import logistics, customer, order, parcel
from test_customer_purchases import account, sale
from app.database import Base
from app.models import Usuario
from app.models.address_book import SavedAddress
from app.models.pdv import PdvPayment, PdvSaleItem
from app.models.printing import PrintDevice, PrintJob
from app.services.customer_activity import customer_activity, order_customer_directory
from app.models.cliente import Cliente
from app.models.access import AuditEvent
from app.models.usuario import UsuarioRole


@pytest.fixture
def activity_env(logistics):
    factory, client, user_id = logistics
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[
            SavedAddress.__table__, PrintDevice.__table__, PrintJob.__table__,
            PdvSaleItem.__table__, PdvPayment.__table__,
            AuditEvent.__table__,
        ])
        db.add(PrintDevice(id=uuid.UUID(int=1), name='Impressora QA', token_hash='synthetic-device'))
        db.commit()
    return factory, client, user_id


def address(db, person, user_id, *, parent=None):
    row = SavedAddress(label='Destino QA', data={'nome': 'Pessoa sintética', 'cidade': 'Cidade QA',
                                               'endereco': f'Rua QA {uuid.uuid4()}'},
                       cliente_id=person.id if person else None, created_by=user_id,
                       merged_into_id=parent.id if parent else None)
    db.add(row); db.flush()
    return row


def print_job(db, recipient, user_id, *, status='submitted', day=1, source='erp'):
    created = datetime(2026, 10, day, 13, tzinfo=timezone.utc)
    row = PrintJob(device_id=uuid.UUID(int=1), user_id=user_id, request_key=uuid.uuid4(),
                   address_id=recipient.id if recipient else None, source=source,
                   pdf=b'synthetic-only', sha256='0' * 64, status=status, created_at=created,
                   finished_at=created + timedelta(hours=1) if status == 'submitted' else None,
                   expires_at=created + timedelta(days=1))
    db.add(row); db.flush()
    return row


def page(client, **params):
    response = client.get('/api/clientes/pagina', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_activity_counts_only_real_links_and_address_alias_jobs_once(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        ana = customer(db, 'Ana QA')
        same_name = customer(db, 'Ana QA')
        buyer = account(db, ana, ativo=False)
        sale(db, buyer, user_id, day=2)
        sale(db, buyer, user_id, day=3, status='partially_refunded', refunded='30')
        sale(db, buyer, user_id, day=7, status='cancelled')
        sale(db, buyer, user_id, day=8, deleted_at=datetime(2026, 10, 8))
        sale(db, account(db, same_name), user_id, day=9)
        sale(db, None, user_id, day=10, cliente_nome='Ana QA')
        pedido = order(db, ana)
        parcel(db, 'LINKED-BOTH', client=ana, pedido=pedido)
        parcel(db, 'ORDER-INHERITED', pedido=pedido, ativo=False)
        parcel(db, 'OTHER-CUSTOMER', client=same_name, pedido=pedido)
        parcel(db, 'SAME-NAME-UNLINKED', destinatario='Ana QA')
        root = address(db, ana, user_id)
        middle = address(db, same_name, user_id, parent=root)
        old = address(db, None, user_id, parent=middle)
        print_job(db, root, user_id, day=1)
        print_job(db, middle, user_id, status='uncertain', day=3)
        print_job(db, old, user_id, status='pending', day=4)
        print_job(db, old, user_id, status='claimed', day=5)
        print_job(db, old, user_id, status='failed', day=6)
        print_job(db, old, user_id, source='bot_pdf_ephemeral', day=10)
        print_job(db, None, user_id, day=11)
        customer_id, other_id = str(ana.id), str(same_name.id)
        db.commit()
    result = {row['id']: row['activity'] for row in page(client)['items']}
    activity = result[customer_id]
    assert activity == {
        'purchase_count': 2, 'order_count': 1, 'shipment_count': 2,
        'print_count': 5, 'submitted_print_count': 1, 'pending_print_count': 2,
        'uncertain_print_count': 1, 'last_purchase_at': '2026-10-03T14:00:00-03:00',
        'last_print_at': '2026-10-06T13:00:00Z', 'own_sales_only': False,
    }
    assert result[other_id]['shipment_count'] == 1
    assert result[other_id]['print_count'] == 0


def test_personal_financial_scope_precedes_ordering_pagination_and_counts(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        db.get(Usuario, user_id).sales_scope = 'own'
        colleague = Usuario(nome='Outra pessoa QA', email='other-qa@example.test', senha_hash='unused')
        db.add(colleague); db.flush()
        ana = customer(db, 'Ana QA')
        bia = customer(db, 'Bia QA')
        clara = customer(db, 'Clara QA')
        sale(db, account(db, ana), colleague.id, day=20, total='999999')
        sale(db, account(db, bia), user_id, day=3, total='150')
        sale(db, account(db, clara), user_id, day=2, total='70')
        sale(db, account(db, bia), user_id, day=27, status='cancelled')
        db.commit()
    result = page(client, sort='ultima_compra', page_size=1)
    assert result['total'] == 3
    assert result['items'][0]['nome'] == 'Bia QA'
    assert result['items'][0]['activity']['purchase_count'] == 1
    assert result['items'][0]['activity']['own_sales_only'] is True
    assert page(client, sort='ultima_compra', page=2, page_size=1)['items'][0]['nome'] == 'Clara QA'
    hidden = page(client, sort='ultima_compra', page=3, page_size=1)['items'][0]
    assert hidden['nome'] == 'Ana QA'
    assert hidden['activity']['purchase_count'] == 0
    assert hidden['activity']['last_purchase_at'] is None
    with factory() as db:
        db.get(Usuario, user_id).sales_scope = 'all'; db.commit()
    assert page(client, sort='ultima_compra', page_size=1)['items'][0]['nome'] == 'Ana QA'


def test_sort_filters_before_page_keeps_nulls_last_and_name_id_ties(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        ana = customer(db, 'Ana lote QA')
        bia = customer(db, 'Bia lote QA')
        clara = customer(db, 'Clara lote QA'); clara.ativo = False
        dora = customer(db, 'Dora fora QA')
        for person, day in ((ana, 2), (bia, 3), (clara, 4), (dora, 5)):
            print_job(db, address(db, person, user_id), user_id, day=day)
        db.commit()
    result = page(client, search='lote', sort='ultima_impressao', page_size=1)
    assert result['total'] == 2 and result['items'][0]['nome'] == 'Bia lote QA'
    assert page(client, search='lote', sort='ultima_impressao', page=2, page_size=1)['items'][0]['nome'] == 'Ana lote QA'
    assert page(client, search='lote', sort='ultima_impressao', include_inactive=True)['items'][0]['nome'] == 'Clara lote QA'
    assert page(client, search='lote', sort='ultima_impressao', ativo=False)['total'] == 1
    assert client.get('/api/clientes/pagina', params={'sort': 'unsupported'}).status_code == 422


@pytest.mark.parametrize('sort', ['nome', 'ultima_compra', 'ultima_impressao'])
def test_directory_batch_query_count_is_constant_and_reads_no_print_pdf(activity_env, sort):
    factory, _, user_id = activity_env
    with factory() as db:
        for i in range(25):
            person = customer(db, f'Cliente QA {i:02}')
            sale(db, account(db, person), user_id)
            print_job(db, address(db, person, user_id), user_id)
        db.commit()
        user = db.get(Usuario, user_id)
        engine = db.bind
        statements = []
        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            counts = []
            for size in (1, 20):
                statements.clear()
                query = db.query(Cliente).filter(Cliente.merged_into_id.is_(None))
                assert query.count() == 25
                people = order_customer_directory(query, db, user, sort).limit(size).all()
                summaries = customer_activity(db, [person.id for person in people], user)
                assert len(summaries) == size
                counts.append(len(statements))
                assert all(sql.lstrip().upper().startswith(('SELECT', 'WITH')) for sql in statements)
                assert not any('print_jobs.pdf' in sql or 'print_jobs.snapshot' in sql for sql in statements)
            assert counts == [3, 3]
        finally:
            event.remove(engine, 'before_cursor_execute', capture)


def test_purchase_payments_are_original_separate_from_net_and_scope(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        person = customer(db, 'Ana QA')
        buyer = account(db, person)
        completed = sale(db, buyer, user_id, total='100', day=3)
        cancelled = sale(db, buyer, user_id, total='200', day=2, status='cancelled')
        refunded = sale(db, buyer, user_id, total='300', refunded='50', day=1, status='partially_refunded')
        for entry, method, amount, original, currency, rate in (
            (completed, 'cash_usd', 120, 20, 'USD', 6),
            (cancelled, 'card', 200, 200, 'GS', 1),
            (refunded, 'fiado', 300, 300, 'GS', 1),
        ):
            db.add(PdvPayment(sale_id=entry.id, method=method, amount_gs=amount,
                              amount_original=original, currency=currency, exchange_rate=rate,
                              reference='private-payment-reference'))
        person_id = person.id
        db.commit()
    response = client.get(f'/api/clientes/{person_id}/compras-pdv')
    assert response.status_code == 200, response.text
    data = response.json()
    assert Decimal(data['summary']['net_gs']) == 350
    assert Decimal(data['items'][0]['change_gs']) == 20
    assert data['items'][1]['change_gs'] is None
    assert data['items'][2]['change_gs'] is None
    assert data['items'][0]['payments'][0]['method'] == 'cash_usd'
    assert data['items'][2]['payments'][0]['method'] == 'fiado'
    assert Decimal(data['items'][0]['payments'][0]['amount_original']) == 20
    assert Decimal(data['items'][0]['payments'][0]['exchange_rate']) == 6
    assert Decimal(data['items'][0]['payment_difference_gs']) == 20
    assert 'private-payment-reference' not in response.text
    assert 'payment_total_gs' not in data['summary']


def test_legacy_non_cash_overpayment_is_a_difference_not_cash_change(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        person = customer(db, 'Ana Pagamento QA')
        entry = sale(db, account(db, person), user_id, total='100')
        db.add(PdvPayment(sale_id=entry.id, method='card', amount_gs=140,
                          amount_original=140, currency='GS', exchange_rate=1))
        person_id = person.id
        db.commit()
    response = client.get(f'/api/clientes/{person_id}/compras-pdv')
    assert response.status_code == 200, response.text
    purchase = response.json()['items'][0]
    assert Decimal(purchase['payment_difference_gs']) == 40
    assert purchase['change_gs'] is None


def test_reconcile_endpoints_require_owner_preview_and_explicit_confirmation(activity_env):
    factory, client, user_id = activity_env
    with factory() as db:
        person = customer(db, 'Ana Correia QA')
        person.telefone = '+5511987654321'
        pending = order(db, cliente_nome=person.nome, cliente_telefone=person.telefone)
        person_id, order_id = person.id, pending.id
        db.commit()
    base = f'/api/clientes/{person_id}/conciliacao'
    assert client.post(base + '/previa').status_code == 403
    assert client.post(base, json={'expected_token': '0' * 64, 'confirm': True}).status_code == 403
    with factory() as db:
        user = db.get(Usuario, user_id)
        user.email = 'lucas@eleven.com'; user.role = UsuarioRole.ADMIN
        db.commit()
    statements = []
    engine = factory.kw['bind']
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        preview = client.post(base + '/previa')
        assert preview.status_code == 200, preview.text
        assert preview.json()['counts']['orders'] == 1
        assert set(statements) == {'SELECT'}
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    token = preview.json()['token']
    for body in ({'expected_token': token}, {'expected_token': token, 'confirm': False},
                 {'expected_token': token, 'confirm': True, 'limit': 10000},
                 {'expected_token': 'invalid', 'confirm': True}):
        assert client.post(base, json=body).status_code == 422
    assert client.post(base, json={'expected_token': '0' * 64, 'confirm': True}).status_code == 409
    first = client.post(base, json={'expected_token': token, 'confirm': True})
    assert first.status_code == 200, first.text
    assert first.json()['linked']['orders'] == 1
    assert first.json()['already_applied'] is False
    retry = client.post(base, json={'expected_token': token, 'confirm': True})
    assert retry.status_code == 200 and retry.json()['already_applied'] is True
    with factory() as db:
        assert db.get(type(pending), order_id).cliente_id == person_id
        assert db.query(AuditEvent).filter_by(action='customer_history_reconciled').count() == 1
        person = db.get(Cliente, person_id); person.ativo = False
        db.commit()
    assert client.post(base + '/previa').status_code == 409
