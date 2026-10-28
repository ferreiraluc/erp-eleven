"""Customer purchase history uses explicit links and scoped, read-only queries."""
from datetime import datetime
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import event

from test_assistant import setup
from test_customer_links import logistics, customer
from app.database import Base
from app.models import Usuario
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem, PdvPayment


@pytest.fixture
def purchases(logistics):
    factory, client, user_id = logistics
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[PdvSaleItem.__table__, PdvPayment.__table__])
    return factory, client, user_id


def account(db, linked=None, **fields):
    row = PdvCliente(nome=fields.pop('nome', 'Ana sintética'),
                     cadastro_cliente_id=linked.id if linked else None, **fields)
    db.add(row); db.flush()
    return row


def sale(db, buyer, seller, *, total='100', refunded='0', day=1, **fields):
    row = PdvSale(cliente_id=buyer.id if buyer else None, vendedor_id=seller,
                  cliente_nome=fields.pop('cliente_nome', 'Nome histórico da venda'),
                  total_gs=Decimal(total), refunded_gs=Decimal(refunded),
                  created_at=datetime(2026, 10, day, 14), **fields)
    db.add(row); db.flush()
    return row


def history(client, customer_id, **params):
    response = client.get(f'/api/clientes/{customer_id}/compras-pdv', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_only_explicit_accounts_match_including_inactive_accounts_and_original_items(purchases):
    factory, client, user_id = purchases
    with factory() as db:
        ana = customer(db, 'Ana sintética')
        homonym = customer(db, 'Ana sintética')
        first = account(db, ana, nome='Conta principal', saldo_fiado_gs=999)
        inactive = account(db, ana, nome='Outra conta', ativo=False, saldo_fiado_gs=-40)
        one = sale(db, first, user_id, cliente_nome='Nome antigo', day=2)
        two = sale(db, inactive, user_id)
        db.add(PdvSaleItem(sale_id=one.id, item_name='Camisa histórica', quantity=2,
                          returned_quantity=1, unit_price_gs=50, total_gs=100, is_avulso=True))
        sale(db, account(db, homonym), user_id, total='700')
        sale(db, account(db), user_id, total='800')
        sale(db, None, user_id, total='900', cliente_nome='Ana sintética')
        customer_id, sale_ids = ana.id, {str(one.id), str(two.id)}
        first_id, inactive_id = first.id, inactive.id
        db.commit()
    result = history(client, customer_id)
    assert result['total'] == 2 and {row['id'] for row in result['items']} == sale_ids
    assert Decimal(result['summary']['net_gs']) == 200
    one = result['items'][0]
    assert one['customer_name'] == 'Nome antigo' and one['account_name'] == 'Conta principal'
    assert one['created_at'] == '2026-10-02T14:00:00-03:00'
    assert one['lines'][0]['name'] == 'Camisa histórica'
    assert Decimal(one['lines'][0]['quantity']) == 2
    assert Decimal(one['lines'][0]['returned_quantity']) == 1
    assert 'saldo_fiado_gs' not in str(result) and 'limite_fiado_gs' not in str(result)
    with factory() as db:
        assert db.get(PdvCliente, first_id).saldo_fiado_gs == 999
        assert db.get(PdvCliente, inactive_id).saldo_fiado_gs == -40
        assert db.get(PdvSale, uuid.UUID(one['id'])).cliente_nome == 'Nome antigo'


def test_personal_scope_precedes_counts_summary_and_pagination(purchases):
    factory, client, user_id = purchases
    with factory() as db:
        db.get(Usuario, user_id).sales_scope = 'own'
        other = Usuario(nome='Colega', email='other@example.test', senha_hash='unused')
        db.add(other); db.flush()
        ana = customer(db); buyer = account(db, ana)
        own = sale(db, buyer, user_id, total='120', refunded='20', status='partially_refunded', day=2)
        cancelled = sale(db, buyer, user_id, total='999', status='cancelled', day=1)
        sale(db, buyer, other.id, total='9000', refunded='300', day=5)
        sale(db, buyer, None, total='8000', day=4)
        sale(db, buyer, user_id, total='7000', day=3, deleted_at=datetime(2026, 10, 4))
        customer_id, own_ids = ana.id, [str(own.id), str(cancelled.id)]
        db.commit()
    for page, expected_ids in [(1, own_ids[:1]), (2, own_ids[1:]), (3, [])]:
        result = history(client, customer_id, page=page, page_size=1)
        assert result['own_sales_only'] and result['total'] == 2
        assert [row['id'] for row in result['items']] == expected_ids
        assert Decimal(result['summary']['net_gs']) == 100
        assert Decimal(result['summary']['refunded_gs']) == 20
        assert result['summary']['cancelled'] == 1
        if page == 2:
            assert Decimal(result['items'][0]['net_gs']) == 0
    with factory() as db:
        db.get(Usuario, user_id).sales_scope = 'all'; db.commit()
    result = history(client, customer_id, page_size=1)
    assert not result['own_sales_only'] and result['total'] == 4
    assert Decimal(result['summary']['net_gs']) == 16800


def test_refunds_and_legacy_cancellations_match_effective_pdv_amounts(purchases):
    factory, client, user_id = purchases
    with factory() as db:
        ana = customer(db); buyer = account(db, ana)
        sale(db, buyer, user_id, total='100', refunded='25', status='partially_refunded')
        sale(db, buyer, user_id, total='80', refunded='80', status='refunded')
        sale(db, buyer, user_id, total='200', refunded='200', status='cancelled')
        sale(db, buyer, user_id, total='300', refunded='0', status='cancelled')
        customer_id = ana.id; db.commit()
    result = history(client, customer_id, page_size=1)
    assert result['total'] == 4 and result['summary']['cancelled'] == 2
    assert Decimal(result['summary']['net_gs']) == 75
    assert Decimal(result['summary']['refunded_gs']) == 305


def test_alias_resolves_to_main_customer_and_read_has_no_writes(purchases):
    factory, client, user_id = purchases
    with factory() as db:
        main = customer(db); main.ativo = False
        alias = customer(db); alias.merged_into_id = main.id; alias.ativo = False
        buyer = account(db, main, saldo_fiado_gs=42)
        sale(db, buyer, user_id)
        main_id, alias_id = main.id, alias.id
        db.commit(); engine = db.bind
    statements = []
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.strip().split()[0].upper())
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        first = history(client, main_id)
        assert history(client, alias_id) == first
        assert first['total'] == 1
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert statements and set(statements) == {'SELECT'}


@pytest.mark.parametrize('params', [{'page': 0}, {'page': -1}, {'page_size': 0}, {'page_size': 101}])
def test_pagination_bounds_are_validated(purchases, params):
    _, client, _ = purchases
    response = client.get(f'/api/clientes/{uuid.uuid4()}/compras-pdv', params=params)
    assert response.status_code == 422


def test_missing_customer_and_unlinked_history(purchases):
    factory, client, _ = purchases
    assert client.get(f'/api/clientes/{uuid.uuid4()}/compras-pdv').status_code == 404
    with factory() as db:
        customer_id = customer(db).id; db.commit()
    result = history(client, customer_id)
    assert result['total'] == 0 and result['items'] == []
    assert Decimal(result['summary']['net_gs']) == 0
    assert Decimal(result['summary']['refunded_gs']) == 0
    assert result['summary']['cancelled'] == 0
