"""PDV stock conservation through real HTTP routes and isolated synthetic data."""
from decimal import Decimal
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from test_pdv_unknown_stock import pdv_app, make_item, sale_payload, balances
from app.models.inventory import Item, StockMovement, MovementType
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement
from app.schemas.pdv import PdvSaleItemCreate


def model(**changes):
    return PdvSaleItemCreate(item_name="Synthetic", unit_price_gs=1, **{
        "item_id": uuid.uuid4(), **changes,
    })


@pytest.mark.parametrize("quantity", [True, False, 0, -1, 1.5, "NaN", "Infinity", "-Infinity", None, 10_000_000])
def test_catalog_quantity_is_finite_positive_bounded_and_integral(quantity):
    with pytest.raises(ValidationError):
        model(quantity=quantity)


@pytest.mark.parametrize("quantity", [True, 0, -1, "NaN", "Infinity", None, "0.0001", "1.0001", "9999999.9991", 10_000_000, "1e-9999999"])
def test_avulso_quantity_fits_exactly_in_numeric_10_3(quantity):
    with pytest.raises(ValidationError):
        model(quantity=quantity, is_avulso=True)


@pytest.mark.parametrize("quantity,avulso", [(1, False), ("9999999", False), ("0.001", True), ("2.125", True), ("9999999.999", True), ("1.0000", True)])
def test_schema_preserves_valid_exact_quantity(quantity, avulso):
    assert model(quantity=quantity, is_avulso=avulso).quantity == Decimal(str(quantity))


@pytest.mark.parametrize("location", [None, "", "warehouse", "LOJA"])
def test_sale_item_requires_an_explicit_supported_location(location):
    with pytest.raises(ValidationError):
        model(location=location)


def test_catalog_requires_id_and_avulso_can_keep_legacy_reference():
    with pytest.raises(ValidationError):
        model(item_id=None)
    assert model(item_id=None, is_avulso=True).item_id is None
    item_id = uuid.uuid4()
    assert model(item_id=item_id, is_avulso=True).item_id == item_id


def assert_nothing_sold(factory, customer_id, item_ids, before):
    with factory() as db:
        assert [balances(db, item_id) for item_id in item_ids] == before
        assert db.get(PdvCliente, customer_id).saldo_fiado_gs == Decimal("20")
        for entity in (PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement, StockMovement):
            assert db.query(entity).count() == 0


@pytest.mark.parametrize("change", [{"quantity": 1.25}, {"quantity": 0}, {"quantity": True}, {"quantity": "NaN"},
                                    {"location": "wrong"}, {"item_id": None}])
def test_invalid_new_payload_returns_422_without_creating_sale(pdv_app, change):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db).id
        db.commit()
    payload = sale_payload([item_id], customer_id)
    payload["items"][0].update(change)
    response = client.post("/api/pdv/sales", json=payload)
    assert response.status_code == 422, response.text
    assert_nothing_sold(factory, customer_id, [item_id], [(10, 6, 4)])


@pytest.mark.parametrize("bad_item", ["missing", "inactive", "inconsistent", "negative", "insufficient_local"])
def test_later_line_conflict_rolls_back_sale_payments_fiado_and_earlier_stock(pdv_app, bad_item):
    factory, client, customer_id = pdv_app
    with factory() as db:
        healthy = make_item(db)
        bad = make_item(db)
        if bad_item == "inactive":
            bad.is_active = False
        elif bad_item == "inconsistent":
            bad.current_stock = 9
        elif bad_item == "negative":
            bad.stock_loja, bad.stock_deposito = -1, 11
        item_ids = [healthy.id, bad.id]
        before = [balances(db, item_id) for item_id in item_ids]
        db.commit()
    payload = sale_payload(item_ids, customer_id)
    if bad_item == "missing":
        payload["items"][1]["item_id"] = str(uuid.uuid4())
    elif bad_item == "insufficient_local":
        payload["items"][1].update(location="deposito", quantity=5)
    response = client.post("/api/pdv/sales", json=payload)
    assert response.status_code == 409, response.text
    assert_nothing_sold(factory, customer_id, item_ids, before)


def test_repeated_catalog_lines_accumulate_instead_of_resetting_the_balance(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db).id
        db.commit()
    payload = sale_payload([item_id, item_id], customer_id)
    for line in payload["items"]:
        line["quantity"] = 4
    response = client.post("/api/pdv/sales", json=payload)
    assert response.status_code == 409, response.text
    assert "Saldo insuficiente" in response.json()["detail"]
    assert_nothing_sold(factory, customer_id, [item_id], [(10, 6, 4)])


def test_multiple_lines_and_locations_consume_exactly_and_cancel_to_original_locals_even_inactive(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db).id
        db.commit()
    payload = sale_payload([item_id] * 4, customer_id)
    for line, quantity, location in zip(payload["items"], [2, 3, 4, 1], ["loja", "deposito", "loja", "deposito"]):
        line.update(quantity=quantity, location=location)
    payload['payments'][0].update(amount_original=1000,amount_gs=1000)
    response = client.post("/api/pdv/sales", json=payload)
    assert response.status_code == 201, response.text
    sale_id = uuid.UUID(response.json()["id"])
    with factory() as db:
        assert balances(db, item_id) == (0, 0, 0)
        exits = db.query(StockMovement).order_by(StockMovement.created_at).all()
        assert [(m.quantity_before, m.quantity_after) for m in exits] == [(10, 8), (8, 5), (5, 1), (1, 0)]
        assert [m.location_from for m in exits] == ["loja", "deposito", "loja", "deposito"]
        assert all(m.movement_type == MovementType.exit and m.reason == "pdv_sale"
                   and m.reference_id == str(sale_id) and m.reference_type == "pdv_sale" for m in exits)
        db.get(Item, item_id).is_active = False
        db.commit()
    cancelled = client.post(f"/api/pdv/sales/{sale_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert client.post(f"/api/pdv/sales/{sale_id}/cancel").status_code == 400
    with factory() as db:
        assert balances(db, item_id) == (10, 6, 4)
        sale = db.get(PdvSale, sale_id)
        assert sale.status == "cancelled" and sale.stock_applied is False
        entries = db.query(StockMovement).filter_by(movement_type=MovementType.entry).order_by(StockMovement.created_at).all()
        assert [(m.quantity_before, m.quantity_after) for m in entries] == [(0, 4), (4, 10)]
        assert {(m.location_to,m.quantity) for m in entries} == {('loja',6),('deposito',4)}
        assert [m.location_to for m in entries] == ["deposito", "loja"]
        assert all(m.location_from is None and m.reason == "pdv_cancel"
                   and m.reference_id == str(sale_id) and m.reference_type == "pdv_sale" for m in entries)


def test_avulso_fraction_is_charged_and_stored_without_truncating_or_changing_stock(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db, is_active=False, current_stock=None).id
        db.commit()
    payload = sale_payload([item_id], customer_id, avulso=True)
    payload["items"][0]["quantity"] = "2.125"
    payload["payments"][0].update(amount_original=212.5, amount_gs=212.5)
    response = client.post("/api/pdv/sales", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["items"][0]["quantity"] == 2.125
    assert response.json()["total_gs"] == 212.5
    assert client.post(f"/api/pdv/sales/{response.json()['id']}/cancel").status_code == 200
    with factory() as db:
        assert db.query(PdvSaleItem).one().quantity == Decimal("2.125")
        assert db.query(StockMovement).count() == 0
        assert balances(db, item_id) == (None, 6, 4)


@pytest.mark.parametrize("changes", [
    {"quantity": 0}, {"quantity": -1}, {"quantity": Decimal("1.500")}, {"quantity": 10_000_000}, {"quantity": None},
    {"location": None}, {"location": "unknown"}, {"item_id": None}, {"item_id": uuid.uuid4()},
])
def test_invalid_legacy_stock_line_blocks_cancellation_atomically(pdv_app, changes):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_ids = [make_item(db).id, make_item(db).id]
        db.commit()
    created = client.post("/api/pdv/sales", json=sale_payload(item_ids, customer_id))
    assert created.status_code == 201, created.text
    sale_id = uuid.UUID(created.json()["id"])
    with factory() as db:
        db.execute(update(PdvSaleItem).where(PdvSaleItem.sale_id == sale_id, PdvSaleItem.item_id == item_ids[1]).values(**changes))
        db.commit()
    response = client.post(f"/api/pdv/sales/{sale_id}/cancel")
    assert response.status_code == 409, response.text
    with factory() as db:
        assert [balances(db, item_id) for item_id in item_ids] == [(9, 5, 4), (9, 5, 4)]
        sale = db.get(PdvSale, sale_id)
        assert sale.status == "completed" and sale.stock_applied is True
        assert db.query(StockMovement).count() == 2
        assert db.query(PdvSaleItem).count() == 2
        assert db.query(PdvPayment).count() == db.query(PdvFiadoMovement).count() == 1
        assert db.get(PdvCliente, customer_id).saldo_fiado_gs == Decimal("220")


def test_cancel_rolls_back_earlier_restitution_when_later_item_would_overflow(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_ids = [make_item(db).id, make_item(db).id]
        db.commit()
    created = client.post("/api/pdv/sales", json=sale_payload(item_ids, customer_id))
    assert created.status_code == 201, created.text
    sale_id = uuid.UUID(created.json()["id"])
    with factory() as db:
        db.execute(update(Item).where(Item.id == item_ids[1]).values(current_stock=2_147_483_647, stock_loja=2_147_483_647, stock_deposito=0))
        db.commit()
    response = client.post(f"/api/pdv/sales/{sale_id}/cancel")
    assert response.status_code == 409, response.text
    with factory() as db:
        assert [balances(db, item_id) for item_id in item_ids] == [(9, 5, 4), (2_147_483_647, 2_147_483_647, 0)]
        sale = db.get(PdvSale, sale_id)
        assert sale.status == "completed" and sale.stock_applied is True
        assert db.query(StockMovement).count() == 2
        assert db.get(PdvCliente, customer_id).saldo_fiado_gs == Decimal("220")
