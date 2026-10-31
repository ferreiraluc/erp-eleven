"""Canonical shipping owners run on a disposable PostgreSQL schema."""
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_customer_activity import address, print_job
from test_customer_links import customer
from test_customer_purchases import account
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.address_book import SavedAddress, FreightOrder
from app.models.pdv import PdvCliente, PdvSale
from app.models.printing import PrintDevice, PrintJob
from app.api.endpoints.clientes import historico_enderecos_cliente
from app.services.customer_activity import customer_activity
from app.services.customer_shipping_links import address_owners


def test_pdv_and_customer_alias_shipping_history_excludes_conflicts_on_postgres(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Cliente, PdvCliente, PdvSale, Pedido, Rastreamento,
            SavedAddress, PrintDevice, PrintJob, FreightOrder,
        )])
        factory = sessionmaker(bind=isolated, autoflush=False)
        with factory() as db:
            user = Usuario(nome='Gestor QA', email='shipping-qa@example.test', senha_hash='unused')
            db.add(user); db.flush()
            db.add(PrintDevice(id=uuid.UUID(int=1), name='Impressora QA', token_hash='synthetic-device'))
            principal, other = customer(db, 'Principal QA'), customer(db, 'Outro QA')
            alias = customer(db, 'Anterior QA'); alias.merged_into_id = principal.id; alias.ativo = False
            buyer = account(db, alias, ativo=False)
            root = address(db, None, user.id); root.pdv_cliente_id = buyer.id
            old = address(db, None, user.id, parent=root)
            direct = address(db, alias, user.id)
            conflict = address(db, other, user.id); conflict.pdv_cliente_id = buyer.id
            for row in (root, old, direct, conflict):
                print_job(db, row, user.id)
            db.flush()
            owners = address_owners()
            linked = dict(db.execute(sa.select(owners)).all())
            assert linked == {row.id: principal.id for row in (root, old, direct)}
            summaries = customer_activity(db, [principal.id, other.id], user)
            assert summaries[principal.id]['print_count'] == 3
            assert summaries[other.id]['print_count'] == 0
            result = historico_enderecos_cliente(str(principal.id), 0, 30, 'all', db, user)
            assert result['total'] == 3 and len(result['addresses']) == 2
            assert root.cliente_id is None and buyer.cadastro_cliente_id == alias.id
    finally:
        isolated.dispose()
