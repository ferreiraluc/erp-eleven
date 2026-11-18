"""Exceptional checkout is explicit, local, auditable and reversible."""
from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException

from test_pdv_unknown_stock import pdv_app, make_item, sale_payload, balances
from test_pdv_management import apply, command, edit_body
from app.api.endpoints.pdv import create_sale_record
from app.models import Usuario
from app.models.inventory import Item, StockMovement
from app.models.pdv import PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement, PdvCliente
from app.schemas.pdv import PdvSaleCreate
from app.services.inventory_service import create_movement, StockMovementError


def confirmed_payload(ids, cid, location='loja'):
    return {**sale_payload(ids, cid, location), 'allow_negative_stock': True}


def zero_item(db, **changes):
    return make_item(db, current_stock=0, stock_loja=0, stock_deposito=0, **changes)


def assert_no_sale(factory, cid, ids, before):
    with factory() as db:
        assert [balances(db, uid) for uid in ids] == before
        assert db.get(PdvCliente, cid).saldo_fiado_gs == Decimal('20')
        assert all(db.query(model).count() == 0 for model in (
            PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement, StockMovement))


@pytest.mark.parametrize('flag', [None, False, 'true', 1])
def test_checkout_needs_literal_true_confirmation(pdv_app, flag):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = zero_item(db).id
        db.commit()
    body = sale_payload([uid], cid)
    if flag is not None:
        body['allow_negative_stock'] = flag
    response = client.post('/api/pdv/sales', json=body)
    assert response.status_code == (409 if flag in (None, False) else 422), response.text
    assert_no_sale(factory, cid, [uid], [(0, 0, 0)])


@pytest.mark.parametrize('location', ['loja', 'deposito'])
def test_confirmed_sale_can_reach_negative_and_audits_original_location(pdv_app, location):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = zero_item(db).id
        db.commit()
    response = client.post('/api/pdv/sales', json=confirmed_payload([uid], cid, location))
    assert response.status_code == 201, response.text
    sid = response.json()['id']
    with factory() as db:
        assert balances(db, uid) == ((-1, -1, 0) if location == 'loja' else (-1, 0, -1))
        sale = db.get(PdvSale, uuid.UUID(sid))
        assert sale.total_gs == 100 and sale.stock_applied
        assert db.query(PdvPayment).one().amount_gs == 100
        movement = db.query(StockMovement).one()
        assert (movement.quantity_before, movement.quantity_after) == (0, -1)
        assert movement.reason == 'pdv_sale_negative_stock'
        assert movement.reference_id == sid and movement.reference_type == 'pdv_sale'
        assert movement.location_from == location
        assert f'Saldo em {location}: 0 → -1' in movement.notes
    cancelled = client.post(f'/api/pdv/sales/{sid}/cancel')
    assert cancelled.status_code == 200, cancelled.text
    with factory() as db:
        assert balances(db, uid) == (0, 0, 0)
        assert db.get(PdvCliente, cid).saldo_fiado_gs == 20
        assert db.query(StockMovement).count() == 2


def test_repeated_lines_and_later_sales_accumulate_without_borrowing_other_location(pdv_app):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = make_item(db, current_stock=5, stock_loja=0, stock_deposito=5).id
        db.commit()
    for ids in ([uid, uid], [uid]):
        response = client.post('/api/pdv/sales', json=confirmed_payload(ids, cid))
        assert response.status_code == 201, response.text
    with factory() as db:
        assert balances(db, uid) == (2, -3, 5)
        assert db.query(StockMovement).count() == 3
        assert db.query(PdvSale).count() == 2
    # Confirmation applies to a checkout, not to all subsequent requests.
    assert client.post('/api/pdv/sales', json=sale_payload([uid], cid)).status_code == 409


@pytest.mark.parametrize('changes', [
    {'stock_loja': None}, {'stock_deposito': None}, {'current_stock': None},
    {'current_stock': 99}, {'is_active': False}, {'deleted_at': datetime.now(timezone.utc)},
])
def test_confirmation_never_bypasses_unknown_invalid_or_unavailable_catalog(pdv_app, changes):
    factory, client, cid = pdv_app
    with factory() as db:
        first, second = zero_item(db), make_item(db, **changes)
        ids = [first.id, second.id]
        before = [balances(db, uid) for uid in ids]
        db.commit()
    response = client.post('/api/pdv/sales', json=confirmed_payload(ids, cid))
    assert response.status_code == 409, response.text
    assert_no_sale(factory, cid, ids, before)


@pytest.mark.parametrize('stock,reserved,quantity', [(0, 1, 1), (2, 1, 2), (2, 1, 3)])
def test_confirmation_cannot_consume_reserved_units(pdv_app, stock, reserved, quantity):
    factory, client, cid = pdv_app
    with factory() as db:
        first = zero_item(db)
        second = make_item(db, current_stock=stock, stock_loja=stock, stock_deposito=0, reserved_loja=reserved)
        ids = [first.id, second.id]
        before = [balances(db, uid) for uid in ids]
        db.commit()
    body = confirmed_payload(ids, cid)
    body['items'][1]['quantity'] = quantity
    body['payments'][0].update(amount_original=(quantity + 1) * 100, amount_gs=(quantity + 1) * 100)
    response = client.post('/api/pdv/sales', json=body)
    assert response.status_code == 409 and 'reservada' in response.json()['detail'], response.text
    assert_no_sale(factory, cid, ids, before)


def test_confirmation_keeps_available_units_and_other_location_reservations(pdv_app):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = make_item(db, current_stock=3, stock_loja=2, stock_deposito=1,
                        reserved_loja=1, reserved_deposito=1).id
        db.commit()
    response = client.post('/api/pdv/sales', json=confirmed_payload([uid], cid))
    assert response.status_code == 201, response.text
    with factory() as db:
        assert balances(db, uid) == (2, 1, 1)
        assert db.query(StockMovement).one().reason == 'pdv_sale'


def test_negative_stock_rejects_integer_underflow(pdv_app):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = make_item(db, current_stock=-2147483648, stock_loja=-2147483648, stock_deposito=0).id
        db.commit()
    response = client.post('/api/pdv/sales', json=confirmed_payload([uid], cid))
    assert response.status_code == 409, response.text
    assert_no_sale(factory, cid, [uid], [(-2147483648, -2147483648, 0)])


def test_partial_return_repairs_negative_stock_in_steps_and_remains_idempotent(pdv_app):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = zero_item(db).id
        db.commit()
    body = confirmed_payload([uid], cid)
    body['items'][0]['quantity'] = 2
    body['payments'][0].update(amount_original=200, amount_gs=200)
    made = client.post('/api/pdv/sales', json=body)
    assert made.status_code == 201, made.text
    sid = made.json()['id']
    line = client.get('/api/pdv/management/' + sid).json()['items'][0]['id']
    for remaining in (-1, 0):
        request, preview = apply(client, sid, command('return', lines=[{'line_id': line, 'quantity': 1, 'restock': True}]))
        assert preview['stock'][0]['after'] == remaining
        replay = client.post(f'/api/pdv/management/{sid}/commit', json=request)
        assert replay.status_code == 200 and replay.json()['replayed']
        with factory() as db:
            assert balances(db, uid) == (remaining, remaining, 0)
    with factory() as db:
        assert db.query(StockMovement).count() == 3
        assert db.get(PdvCliente, cid).saldo_fiado_gs == 20


def test_sale_correction_cannot_increase_negative_stock_without_checkout(pdv_app):
    factory, client, cid = pdv_app
    with factory() as db:
        uid = zero_item(db).id
        db.commit()
    made = client.post('/api/pdv/sales', json=confirmed_payload([uid], cid))
    sid = made.json()['id']
    edit = edit_body(client.get('/api/pdv/management/' + sid).json())
    edit['items'][0]['quantity'] = 2
    edit['payments'][0].update(amount_original=200, amount_gs=200)
    response = client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit))
    assert response.status_code == 409, response.text
    with factory() as db:
        assert balances(db, uid) == (-1, -1, 0)
        assert db.query(StockMovement).count() == 1


def test_order_settlement_cannot_opt_into_exception(pdv_app):
    factory, _, cid = pdv_app
    with factory() as db:
        uid = zero_item(db).id
        user = db.query(Usuario).one()
        with pytest.raises(HTTPException) as failed:
            create_sale_record(db, PdvSaleCreate(**confirmed_payload([uid], cid)), user,
                               frozen_usd_rate=Decimal(6000))
        assert failed.value.status_code == 422
        assert db.query(PdvSale).count() == 0


@pytest.mark.parametrize('movement,extra', [
    ('transfer', {}), ('entry', {}), ('exit', {}),
    ('transfer', {'allow_pdv_negative_stock': True}),
    ('exit', {'allow_pdv_negative_stock': True, 'reason': 'manual'}),
    ('exit', {'allow_pdv_restitution': True}),
])
def test_ordinary_inventory_operations_have_no_negative_stock_bypass(pdv_app, movement, extra):
    factory, _, _ = pdv_app
    with factory() as db:
        uid = make_item(db, current_stock=-1, stock_loja=-1, stock_deposito=0).id
        user = db.query(Usuario).one()
        with pytest.raises(StockMovementError):
            create_movement(db, uid, movement, 1, user.id, **extra)
        assert balances(db, uid) == (-1, -1, 0)
        assert db.query(StockMovement).count() == 0
