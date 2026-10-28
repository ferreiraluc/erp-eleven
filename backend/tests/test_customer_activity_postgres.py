"""Recursive address history and scoped sort run against disposable PostgreSQL."""
from datetime import datetime, timezone
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_customer_activity import address, print_job
from test_customer_links import customer, order, parcel
from test_customer_purchases import account, sale
from app.config import settings
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente, PdvSale
from app.models.printing import PrintDevice, PrintJob
from app.services.customer_activity import customer_activity, order_customer_directory


def test_recursive_print_history_and_personal_purchase_order_on_postgres(pg, monkeypatch):
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Cliente, PdvCliente, PdvSale, Pedido, Rastreamento,
            SavedAddress, PrintDevice, PrintJob,
        )])
        factory = sessionmaker(bind=isolated, autoflush=False)
        with factory() as db:
            user = Usuario(nome='Funcionário QA', email='activity-qa@example.test', senha_hash='unused', sales_scope='own')
            other = Usuario(nome='Colega QA', email='colleague-qa@example.test', senha_hash='unused')
            db.add_all([user, other]); db.flush()
            db.add(PrintDevice(id=uuid.UUID(int=1), name='Impressora QA', token_hash='synthetic-device'))
            ana = customer(db, 'Ana QA'); bia = customer(db, 'Bia QA'); clara = customer(db, 'Clara QA')
            sale(db, account(db, ana), other.id, day=27)
            sale(db, account(db, bia), user.id, day=2)
            sale(db, account(db, clara), user.id, day=1)
            sale(db, account(db, bia), user.id, day=28, status='cancelled')
            root = address(db, ana, user.id)
            middle = address(db, None, user.id, parent=root)
            old = address(db, None, user.id, parent=middle)
            print_job(db, old, user.id, day=3)
            print_job(db, middle, user.id, day=4, status='uncertain')
            pedido = order(db, ana)
            parcel(db, 'PG-ACTIVITY', pedido=pedido)
            db.commit()
            query = db.query(Cliente).filter(Cliente.ativo.is_(True), Cliente.merged_into_id.is_(None))
            ordered = order_customer_directory(query, db, user, 'ultima_compra').limit(1).all()
            assert [person.nome for person in ordered] == ['Bia QA']
            printed = order_customer_directory(query, db, user, 'ultima_impressao').limit(1).all()
            assert [person.nome for person in printed] == ['Ana QA']
            summaries = customer_activity(db, [ana.id, bia.id, clara.id], user)
            assert summaries[ana.id]['purchase_count'] == 0
            assert summaries[ana.id]['last_purchase_at'] is None
            assert summaries[ana.id]['print_count'] == 2
            assert summaries[ana.id]['shipment_count'] == 1
            assert summaries[ana.id]['uncertain_print_count'] == 1
            assert summaries[ana.id]['last_print_at'].astimezone(timezone.utc).isoformat() == '2026-10-04T13:00:00+00:00'
            assert summaries[bia.id]['purchase_count'] == 1
            assert summaries[bia.id]['last_purchase_at'].replace(tzinfo=None) == datetime(2026, 10, 2, 14)
    finally:
        isolated.dispose()
