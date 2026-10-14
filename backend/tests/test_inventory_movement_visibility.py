"""Legacy movement reads keep stock facts without leaking inaccessible PDV data."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.orm import joinedload

from test_assistant import setup
from test_inventory_ocr import stock_app, item
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import StockMovement
from app.models.pdv import PdvSale
from app.services.inventory_movement_visibility import movement_read_responses


@pytest.fixture
def movements_app(stock_app):
    factory, client, uid = stock_app
    with factory() as db:
        product = item(db)
        other = Usuario(nome='Colega sintético', email='other@example.test', senha_hash='unused')
        db.add(other); db.flush()
        sales = {}
        for kind, seller, deleted in (
            ('own', uid, False), ('other', other.id, False),
            ('own_deleted', uid, True), ('other_deleted', other.id, True),
        ):
            row = PdvSale(vendedor_id=seller, total_gs=456,
                          deleted_at=datetime(2026, 10, 14, tzinfo=timezone.utc) if deleted else None)
            db.add(row); db.flush(); sales[kind] = row.id
        references = [
            ('own', str(sales['own'])), ('own', sales['own'].hex), ('own', str(sales['own']).upper()),
            ('other', str(sales['other'])), ('other', sales['other'].hex),
            ('own_deleted', str(sales['own_deleted'])), ('other_deleted', str(sales['other_deleted']).upper()),
            ('missing', uuid.uuid4().hex), ('invalid', 'invalid-reference'), ('invalid', None),
            ('manual', 'manual-stock-reference'),
        ]
        expected = {}
        for index, (kind, reference) in enumerate(references):
            row = StockMovement(item_id=product.id, movement_type='entry', quantity=1,
                                quantity_before=100 + index, quantity_after=101 + index,
                                reference_type='manual' if kind == 'manual' else 'pdv_sale',
                                reference_id=reference, created_by=other.id,
                                reason=f'Motivo sintético {index}', notes=f'Nota sintética {index}',
                                unit_cost=Decimal('456.78'), location_from='loja', location_to='deposito',
                                created_at=datetime(2026, 10, 14, 12) + timedelta(minutes=index))
            db.add(row); db.flush()
            expected[str(row.id)] = {
                'kind': kind, 'reference_id': reference, 'created_by': str(other.id),
                'reason': row.reason, 'notes': row.notes, 'unit_cost': '456.78',
                'quantity_before': row.quantity_before, 'quantity_after': row.quantity_after,
            }
        rid = product.id; db.commit()
    return factory, client, uid, rid, expected


def set_profile(factory, uid, identity, scope):
    with factory() as db:
        user = db.get(Usuario, uid)
        user.email = f'{identity}@eleven.com'; user.sales_scope = scope
        user.role = UsuarioRole.ADMIN if identity == 'lucas' else UsuarioRole.GERENTE
        db.commit()


def path(route, rid):
    return '/api/inventory/movements' if route == 'all' else f'/api/inventory/movements/item/{rid}'


@pytest.mark.parametrize('route', ['all', 'item'])
@pytest.mark.parametrize(('identity', 'scope'), [('denis', 'own'), ('wissam', 'all'), ('lucas', 'all'), ('lucas', 'own')])
def test_movement_reads_obey_sale_access_without_hiding_stock_or_manual_entries(movements_app, route, identity, scope):
    factory, client, uid, rid, expected = movements_app
    set_profile(factory, uid, identity, scope)
    response = client.get(path(route, rid), params={'limit': 50})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row['id'] for row in rows] == list(reversed(expected))
    for row in rows:
        original = expected[row['id']]
        kind = original['kind']
        restricted = kind != 'manual' and (
            scope == 'own' and kind not in ('own', 'own_deleted') or
            identity != 'lucas' and kind in ('own_deleted', 'other_deleted', 'invalid', 'missing')
        )
        assert row['quantity'] == 1 and row['item_id'] == str(rid) and row['item_name'] == 'Camiseta'
        assert row['location_from'] == 'loja' and row['location_to'] == 'deposito'
        assert row['quantity_before'] == original['quantity_before']
        assert row['quantity_after'] == original['quantity_after']
        for field in ('reference_id', 'created_by', 'reason', 'notes', 'unit_cost'):
            assert row[field] == (None if restricted else original[field]), (identity, scope, kind, field)


@pytest.mark.parametrize('route', ['all', 'item'])
def test_movement_authorization_queries_only_the_page_without_n_plus_one_or_writes(movements_app, route):
    factory, client, uid, rid, expected = movements_app
    set_profile(factory, uid, 'denis', 'own')
    statements = []
    with factory() as db: engine = db.bind
    def capture(_connection, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = client.get(path(route, rid), params={'skip': 4, 'limit': 3})
        assert response.status_code == 200, response.text
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    rows = response.json()
    assert [row['id'] for row in rows] == list(reversed(expected))[4:7]
    assert all(statement.lstrip().startswith('SELECT') for statement, _ in statements)
    sale_queries = [(statement, parameters) for statement, parameters in statements if 'FROM pdv_sales' in statement]
    assert len(sale_queries) == 1
    assert len(statements) == 3  # authenticated actor, joined movement page, sale authorization
    parameters = str(sale_queries[0][1]).lower()
    page_refs = {str(uuid.UUID(expected[row['id']]['reference_id'])).replace('-', '') for row in rows}
    for reference in page_refs:
        assert reference in parameters
    outside = {str(uuid.UUID(data['reference_id'])).replace('-', '') for data in expected.values() if data['kind'] == 'own'}
    for reference in outside - page_refs:
        assert reference not in parameters
    with factory() as db:
        for row in db.query(StockMovement):
            original = expected[str(row.id)]
            assert row.reference_id == original['reference_id']
            assert row.notes == original['notes'] and row.reason == original['reason']
            assert str(row.created_by) == original['created_by'] and row.unit_cost == Decimal('456.78')


def test_redaction_does_not_dirty_or_change_orm_rows_in_the_same_session(movements_app):
    factory, _, uid, _, expected = movements_app
    set_profile(factory, uid, 'denis', 'own')
    with factory() as db:
        user = db.get(Usuario, uid)
        rows = db.query(StockMovement).options(joinedload(StockMovement.item)).all()
        responses = movement_read_responses(db, rows, user)
        assert any(response.reason is None for response in responses)
        assert not db.dirty
        for row in rows:
            original = expected[str(row.id)]
            assert row.reason == original['reason'] and row.notes == original['notes']
            assert row.reference_id == original['reference_id']
            assert row.unit_cost == Decimal('456.78') and str(row.created_by) == original['created_by']
