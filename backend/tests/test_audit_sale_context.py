"""Safe facts captured at mutation time; no enrichment of historical audit rows."""
import json
from decimal import Decimal

import pytest
from sqlalchemy import event, inspect
from sqlalchemy.orm import load_only

from app.database import Base
from app.models.access import AuditEvent
from app.models.cliente import Cliente
from app.models.comprovante import Comprovante
from app.models.pdv import PdvCliente, PdvSale
from app.models.usuario import Usuario
from app.models.venda import MoedaTipo, PagamentoMetodo, Venda
from app.services.user_audit import bind_actor, module_name
from test_access import setup  # noqa: F401


def test_pdv_capture_uses_actual_seller_and_frozen_rate_without_private_values(setup):
    _, factory, ids = setup
    with factory() as db:
        bind_actor(db, db.get(Usuario, ids['Lucas'][0]))
        sale = PdvSale(vendedor_id=ids['Sol'][0], total_gs=480000, usd_rate_gs=6000,
                       cliente_nome='PRIVATE CUSTOMER', notas='PRIVATE NOTE')
        db.add(sale)
        db.commit()
        audit = db.query(AuditEvent).filter_by(entity='pdv_sales', action='create').one()
        snapshot = audit.changes['_context']['sale']
        assert snapshot == {'seller_id': str(ids['Sol'][0]), 'seller_name': 'Sol',
                            'total_gs': '480000.00', 'usd_rate_gs': '6000.0000', 'status': 'completed'}
        assert audit.actor_name == 'Lucas'
        assert audit.changes['_context']['sale_id'] == str(sale.id)
        assert 'PRIVATE' not in json.dumps(audit.changes)

        sale.total_gs = 720000
        sale.status = 'cancelled'
        db.get(Usuario, ids['Sol'][0]).nome = 'Novo nome'
        db.commit()
        db.refresh(audit)
        assert audit.changes['_context']['sale'] == snapshot
        latest = db.query(AuditEvent).filter_by(entity='pdv_sales', action='update').one()
        assert latest.changes['_context']['sale']['status'] == 'cancelled'
        assert latest.changes['_context']['sale']['total_gs'] == '720000.00'
        assert latest.changes['_context']['sale']['seller_name'] == 'Novo nome'


@pytest.mark.parametrize('count, expected_queries', [(3, 2), (251, 3)])
def test_safe_sale_projection_is_batched_and_never_lazy_loads_private_fields(setup, count, expected_queries):
    _, factory, ids = setup
    with factory() as db:
        db.add_all([PdvSale(vendedor_id=ids['Sol'][0], total_gs=6000, usd_rate_gs=6000,
                            notas='DO NOT LOAD', cliente_nome='DO NOT LOAD') for _ in range(count)])
        db.commit()
        db.expunge_all()
        bind_actor(db, db.get(Usuario, ids['Lucas'][0]))
        sales = db.query(PdvSale).options(load_only(PdvSale.id, PdvSale.status, raiseload=True)).all()
        for sale in sales:
            sale.status = 'cancelled'
        reads = []

        def capture_reads(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                reads.append(statement.lower())

        engine = db.get_bind()
        event.listen(engine, 'before_cursor_execute', capture_reads)
        try:
            db.flush()
        finally:
            event.remove(engine, 'before_cursor_execute', capture_reads)
        assert len(reads) == expected_queries
        assert all('cliente_nome' not in sql and 'notas' not in sql and 'senha_hash' not in sql for sql in reads)
        assert all('notas' in inspect(sale).unloaded and 'vendedor_id' in inspect(sale).unloaded for sale in sales)
        audits = db.query(AuditEvent).filter_by(entity='pdv_sales').all()
        assert len(audits) == count
        assert all(audit.changes['_context']['sale']['seller_name'] == 'Sol' for audit in audits)
        db.commit()


def test_zero_and_missing_seller_are_preserved_and_rollback_has_no_audit_event(setup):
    _, factory, ids = setup
    with factory() as db:
        bind_actor(db, db.get(Usuario, ids['Lucas'][0]))
        sale = PdvSale(total_gs=0, usd_rate_gs=None, vendedor_id=None)
        db.add(sale)
        db.flush()
        audit = db.query(AuditEvent).filter_by(entity='pdv_sales').one()
        assert audit.changes['_context']['sale'] == {
            'seller_id': None, 'seller_name': None, 'total_gs': '0.00',
            'usd_rate_gs': None, 'status': 'completed',
        }
        db.rollback()
        assert db.query(AuditEvent).count() == 0
        assert db.query(PdvSale).count() == 0


def test_operational_sale_keeps_original_currency_and_its_distinct_seller(setup):
    _, factory, ids = setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[Comprovante.__table__])
        bind_actor(db, db.get(Usuario, ids['Lucas'][0]))
        sale = Venda(vendedor_id=ids['Sol'][1], moeda=MoedaTipo.R_DOLLAR,
                     valor_bruto=Decimal('129.90'), valor_liquido=Decimal('24.5'),
                     metodo_pagamento=PagamentoMetodo.PIX_POWER, observacoes='PRIVATE NOTE')
        db.add(sale)
        db.commit()
        audit = db.query(AuditEvent).filter_by(entity='vendas').one()
        assert audit.changes['_context'] == {'operational_sale': {
            'seller_id': str(ids['Sol'][1]), 'seller_name': 'Sol', 'amount': '129.9000', 'currency': 'R$',
        }}
        assert 'sale_id' not in audit.changes['_context']
        assert 'PRIVATE' not in json.dumps(audit.changes)
        db.delete(sale)
        db.commit()
        deleted = db.query(AuditEvent).filter_by(entity='vendas', action='delete').one()
        assert deleted.changes['_context'] == audit.changes['_context']


def test_customer_field_flags_remain_descriptive_without_storing_private_contents(setup):
    _, factory, ids = setup
    with factory() as db:
        customer = Cliente(nome='PRIVATE ORIGINAL', cpf='PRIVATE DOC', endereco='PRIVATE ADDRESS')
        pdv_customer = PdvCliente(nome='PRIVATE ORIGINAL PDV', doc='PRIVATE PDV DOC')
        db.add_all([customer, pdv_customer])
        db.commit()
        bind_actor(db, db.get(Usuario, ids['Lucas'][0]))
        customer.nome = 'PRIVATE NEW'
        pdv_customer.nome = 'PRIVATE NEW PDV'
        db.commit()
        audits = db.query(AuditEvent).all()
        assert {audit.entity for audit in audits} == {'clientes', 'pdv_clientes'}
        for audit in audits:
            assert audit.changes['nome'] == {'changed': True}
            assert 'PRIVATE' not in json.dumps(audit.changes)
            assert '_context' not in audit.changes


@pytest.mark.parametrize('table', ['pedido_items', 'pedido_payments', 'pedido_operations',
                                  'pedido_payment_refunds', 'pedido_archive_operations'])
def test_order_mutations_are_visible_under_the_orders_module(table):
    assert module_name(table) == 'pedidos'
