"""Sale snapshot UUIDs/decimals and rollback on a disposable PostgreSQL schema."""
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import load_only, sessionmaker

from app.database import Base
from app.models.access import AuditEvent
from app.models.cliente import Cliente
from app.models.pdv import PdvCliente, PdvSale
from app.models.usuario import Usuario
from app.models.vendedor import Vendedor
from app.services.user_audit import bind_actor
from test_access_postgres import pg  # noqa: F401


def test_postgres_sale_capture_has_safe_frozen_facts_and_rolls_back(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
        Usuario, Vendedor, Cliente, PdvCliente, PdvSale, AuditEvent)])
    factory = sessionmaker(bind=isolated, info={'audit_enabled': True})
    actor_id, seller_id, sale_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        with factory() as db:
            db.add_all([Usuario(id=actor_id, nome='Lucas', email='actor@example.test', senha_hash='unused'),
                        Usuario(id=seller_id, nome='Sol', email='seller@example.test', senha_hash='unused')])
            db.flush()
            db.add(PdvSale(id=sale_id, vendedor_id=seller_id, total_gs=480000, usd_rate_gs=6000,
                           cliente_nome='PRIVATE CUSTOMER', notas='PRIVATE NOTE'))
            db.commit()
            bind_actor(db, db.get(Usuario, actor_id))
            sale = db.query(PdvSale).options(load_only(PdvSale.id, PdvSale.status, raiseload=True)).one()
            sale.status = 'cancelled'
            db.flush()
            audit = db.query(AuditEvent).filter_by(entity='pdv_sales').one()
            assert audit.changes['_context'] == {'sale_id': str(sale_id), 'sale': {
                'seller_id': str(seller_id), 'seller_name': 'Sol', 'total_gs': '480000.00',
                'usd_rate_gs': '6000.0000', 'status': 'cancelled',
            }}
            assert 'cliente_nome' in sa.inspect(sale).unloaded
            db.rollback()
            assert db.query(AuditEvent).count() == 0
            assert db.get(PdvSale, sale_id).status == 'completed'
    finally:
        isolated.dispose()
