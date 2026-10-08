"""PDV rejects unknown balances atomically; fixtures never use the real database."""
from decimal import Decimal
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints import pdv
from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models import Usuario, Vendedor, Cambista, Cliente
from app.models.address_book import SavedAddress
from app.models.usuario import UsuarioRole
from app.models.access import AuditEvent
from app.models.inventory import Item, Supplier, StockMovement
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement, PdvSaleEvent
from app.schemas.pdv import PdvSaleItemCreate


BALANCES = ("current_stock", "stock_loja", "stock_deposito")
TABLES = (Usuario, Vendedor, Cambista, Cliente, SavedAddress, Supplier, Item, StockMovement,
          PdvCliente, PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement, PdvSaleEvent, AuditEvent)


@pytest.fixture
def pdv_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in TABLES])
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        user = Usuario(nome="Lucas sintético", email="lucas@eleven.com", role=UsuarioRole.ADMIN, senha_hash="unused")
        customer = PdvCliente(nome="Cliente sintético", saldo_fiado_gs=20)
        db.add_all([user, customer])
        db.flush()
        ids = user.id, customer.id
        db.commit()

    app = FastAPI()
    app.include_router(pdv.router, prefix="/api/pdv")

    def session():
        with factory() as db:
            yield db

    def user():
        with factory() as db:
            return db.get(Usuario, ids[0])

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = user
    with TestClient(app) as client:
        yield factory, client, ids[1]
    engine.dispose()


def make_item(db, **balances):
    item = Item(name="Produto sintético", sku_internal=str(uuid.uuid4()),
                current_stock=10, stock_loja=6, stock_deposito=4)
    db.add(item)
    db.flush()
    # SQL UPDATE is intentional: ORM defaults replace None on INSERT with zero.
    if balances:
        db.execute(update(Item).where(Item.id == item.id).values(**balances))
        db.refresh(item)
    return item


def sale_payload(item_ids, customer_id, location="loja", avulso=False):
    total = len(item_ids) * 100
    return {
        "cliente_id": str(customer_id),
        "items": [{"item_id": str(item_id) if item_id else None, "item_name": "Produto sintético",
                   "quantity": 1, "unit_price_gs": 100, "location": location, "is_avulso": avulso}
                  for item_id in item_ids],
        "payments": [{"method": "fiado", "amount_original": total, "amount_gs": total}],
    }


def balances(db, item_id):
    item = db.get(Item, item_id)
    return tuple(getattr(item, field) for field in BALANCES)


@pytest.mark.parametrize("field", BALANCES)
@pytest.mark.parametrize("location", ("loja", "deposito"))
def test_unknown_balance_rejects_whole_sale_without_financial_or_stock_writes(pdv_app, field, location):
    factory, client, customer_id = pdv_app
    with factory() as db:
        healthy, unknown = make_item(db), make_item(db, **{field: None})
        item_ids = healthy.id, unknown.id
        before = [balances(db, item_id) for item_id in item_ids]
        db.commit()
    # Healthy first verifies no partial decrement precedes the unknown second item.
    response = client.post("/api/pdv/sales", json=sale_payload(item_ids, customer_id, location))
    assert response.status_code == 409, response.text
    assert "Estoque não informado" in response.json()["detail"]
    with factory() as db:
        assert [balances(db, item_id) for item_id in item_ids] == before
        assert db.get(PdvCliente, customer_id).saldo_fiado_gs == Decimal("20")
        for model in (PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement, StockMovement):
            assert db.query(model).count() == 0


@pytest.mark.parametrize("field", BALANCES)
@pytest.mark.parametrize("location", ("loja", "deposito"))
def test_unknown_balance_prevents_partial_cancellation_and_preserves_sale(pdv_app, field, location):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_ids = make_item(db).id, make_item(db).id
        db.commit()
    created = client.post("/api/pdv/sales", json=sale_payload(item_ids, customer_id, location))
    assert created.status_code == 201, created.text
    sale_id = uuid.UUID(created.json()["id"])
    with factory() as db:
        db.execute(update(Item).where(Item.id == item_ids[1]).values(**{field: None}))
        db.commit()
        before = [balances(db, item_id) for item_id in item_ids]

    response = client.post(f"/api/pdv/sales/{sale_id}/cancel")
    assert response.status_code == 409, response.text
    with factory() as db:
        sale = db.get(PdvSale, sale_id)
        assert sale.status == "completed" and sale.stock_applied is True
        assert [balances(db, item_id) for item_id in item_ids] == before
        assert db.get(PdvCliente, customer_id).saldo_fiado_gs == Decimal("220")
        assert db.query(StockMovement).count() == 2
        assert db.query(PdvSale).count() == 1
        assert db.query(PdvSaleItem).count() == 2
        assert db.query(PdvPayment).count() == db.query(PdvFiadoMovement).count() == 1


def test_known_zero_is_not_unknown_but_cannot_cover_a_sale(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db, **dict.fromkeys(BALANCES, 0)).id
        db.commit()
    response = client.post("/api/pdv/sales", json=sale_payload([item_id], customer_id))
    assert response.status_code == 409, response.text
    assert "Saldo insuficiente" in response.json()["detail"]
    with factory() as db:
        assert balances(db, item_id) == (0, 0, 0)
        assert db.query(StockMovement).count() == db.query(PdvSale).count() == 0


@pytest.mark.parametrize("referenced_unknown_item", (False, True))
def test_avulso_sale_does_not_consult_or_modify_inventory(pdv_app, referenced_unknown_item):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db, **dict.fromkeys(BALANCES)).id
        db.commit()
    payload = sale_payload([item_id if referenced_unknown_item else None], customer_id, avulso=True)
    response = client.post("/api/pdv/sales", json=payload)
    assert response.status_code == 201, response.text
    assert client.post(f"/api/pdv/sales/{response.json()['id']}/cancel").status_code == 200
    with factory() as db:
        assert balances(db, item_id) == (None, None, None)
        assert db.query(StockMovement).count() == 0
        assert db.query(PdvPayment).count() == 1
        assert db.query(PdvFiadoMovement).count() == 2
        assert db.query(PdvFiadoMovement).filter_by(tipo='credit').one().valor_gs == 100


def test_helper_refreshes_cached_balances_and_rolls_back_pending_work_on_rejection(pdv_app):
    factory, _, customer_id = pdv_app
    with factory() as db:
        item = make_item(db)
        db.commit()
        assert item.current_stock == 10
        db.execute(update(Item).where(Item.id == item.id).values(stock_deposito=None),
                   execution_options={"synchronize_session": False})
        assert item.stock_deposito == 4  # stale ORM identity before the helper's re-read
        pending = PdvSale(cliente_id=customer_id, status="completed")
        db.add(pending)
        with pytest.raises(HTTPException) as rejected:
            pdv._lock_sale_stock(db, [PdvSaleItemCreate(item_id=item.id, item_name="Fixture", unit_price_gs=1)])
        assert rejected.value.status_code == 409
        assert db.query(PdvSale).count() == 0
        assert balances(db, item.id) == (10, 6, 4)  # rollback also undoes this fixture's uncommitted UPDATE
