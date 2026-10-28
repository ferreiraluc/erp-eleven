"""One reviewed historical plan is atomic and idempotent under concurrent retries."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.pdv import PdvCliente
from app.models.address_book import SavedAddress
from app.models.access import AuditEvent
from app.services.customer_reconciliation import preview_customer_links, apply_customer_links


def test_concurrent_history_confirmations_apply_one_reviewed_plan_and_preserve_snapshots(pg, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in
            (Usuario, Vendedor, Cliente, Pedido, Rastreamento, PdvCliente, SavedAddress, AuditEvent)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        uid, cid = uuid.uuid4(), uuid.uuid4()
        with factory() as db:
            db.add(Usuario(id=uid, nome='Fixture', email='fixture@example.test', senha_hash='unused'))
            db.add(Cliente(id=cid, nome='Pessoa Teste', telefone='+595972123456')); db.flush()
            order = Pedido(numero_pedido='HISTORICAL-PG', descricao='Conteúdo original', valor_total=45,
                cliente_nome='Pessoa Teste', cliente_telefone='+595972123456')
            db.add(order); db.flush()
            db.add(Rastreamento(codigo_rastreio='HISTORICAL-PARCEL', pedido_id=order.id,
                destinatario='Destinatário original'))
            db.commit()
            token = preview_customer_links(db, db.get(Cliente, cid))['token']; db.rollback()
        barrier = Barrier(2)
        def confirm():
            with factory() as db:
                customer, actor = db.get(Cliente, cid), db.get(Usuario, uid)
                barrier.wait(timeout=10)
                result = apply_customer_links(db, customer, token, actor)
                db.commit()
                return result['already_applied']
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: confirm(), range(2)))
        assert sorted(outcomes) == [False, True]
        with factory() as db:
            order = db.query(Pedido).one(); parcel = db.query(Rastreamento).one()
            assert order.cliente_id == parcel.cliente_id == cid
            assert order.descricao == 'Conteúdo original' and order.valor_total == 45
            assert parcel.destinatario == 'Destinatário original'
            assert db.query(AuditEvent).filter_by(action='customer_history_reconciled').count() == 1
    finally:
        isolated.dispose()
