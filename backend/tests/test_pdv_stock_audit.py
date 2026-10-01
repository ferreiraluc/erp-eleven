"""PDV stock changes and their audit records must commit or roll back together."""
import uuid

import pytest
from fastapi import HTTPException

from test_pdv_unknown_stock import pdv_app, make_item, sale_payload, balances
from app.api.endpoints import pdv
from app.models.access import AuditEvent
from app.models.pdv import PdvSale
from app.models.usuario import Usuario
from app.schemas.pdv import PdvSaleCreate
from app.services.user_audit import bind_actor


def enable_audit(db, actor):
    AuditEvent.__table__.create(db.get_bind(), checkfirst=True)
    db.info['audit_enabled'] = True
    bind_actor(db, actor)


def test_successful_sale_and_cancel_attribute_stock_changes_to_operator(pdv_app):
    factory, _, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db).id
        db.commit()
        operator = db.query(Usuario).one()
        operator_id = operator.id
        enable_audit(db, operator)
        sale = pdv.create_sale(PdvSaleCreate(**sale_payload([item_id], customer_id)), db, operator)
        sale_id = sale.id
        assert balances(db, item_id) == (9, 5, 4)
        stock_events = db.query(AuditEvent).filter_by(entity='inventory_items', entity_id=str(item_id)).all()
        assert len(stock_events) == 1
        assert stock_events[0].user_id == operator_id
        assert stock_events[0].changes['stock_loja'] == {'before': 6, 'after': 5}
        assert stock_events[0].changes['current_stock'] == {'before': 10, 'after': 9}
        assert db.query(AuditEvent).filter_by(entity='stock_movements', action='create').count() == 1

        pdv.cancel_sale(sale_id, db, operator)
        assert balances(db, item_id) == (10, 6, 4)
        assert db.query(AuditEvent).filter_by(entity='stock_movements', action='create').count() == 2
        assert db.query(AuditEvent).filter_by(entity='pdv_sales', entity_id=str(sale_id)).count() >= 2
        assert {event.user_id for event in db.query(AuditEvent).all()} == {operator_id}


def test_failed_second_item_rolls_back_stock_and_all_mutation_audits(pdv_app):
    factory, _, customer_id = pdv_app
    with factory() as db:
        ids = [make_item(db).id, make_item(db, current_stock=0, stock_loja=0, stock_deposito=0).id]
        db.commit()
        operator = db.query(Usuario).one()
        enable_audit(db, operator)
        with pytest.raises(HTTPException) as rejected:
            pdv.create_sale(PdvSaleCreate(**sale_payload(ids, customer_id)), db, operator)
        assert rejected.value.status_code == 409
        assert balances(db, ids[0]) == (10, 6, 4)
        assert balances(db, ids[1]) == (0, 0, 0)
        assert db.query(PdvSale).count() == 0
        assert db.query(AuditEvent).count() == 0


def test_restricted_operator_cannot_cancel_other_sale_or_generate_stock_audit(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        item_id = make_item(db).id
        db.commit()
    response = client.post('/api/pdv/sales', json=sale_payload([item_id], customer_id))
    assert response.status_code == 201
    sale_id = uuid.UUID(response.json()['id'])
    with factory() as db:
        other = Usuario(nome='Outro operador de teste', email='another@example.test', senha_hash='unused', sales_scope='own')
        db.add(other)
        db.commit()
        enable_audit(db, other)
        with pytest.raises(HTTPException) as rejected:
            pdv.cancel_sale(sale_id, db, other)
        assert rejected.value.status_code == 404
        assert db.get(PdvSale, sale_id).status == 'completed'
        assert balances(db, item_id) == (9, 5, 4)
        assert db.query(AuditEvent).count() == 0
