"""A customer selection cannot restore a directory alias after a concurrent merge."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from app.config import settings
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.access import AuditEvent
from app.models.address_book import SavedAddress
from app.models.pdv import PdvCliente
from app.services import address_book, pdv_customers
from app.services.customer_maintenance import merge_customers


def test_pdv_selection_rechecks_cached_identity_after_concurrent_customer_merge(pg, monkeypatch):
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Cliente, Pedido, Rastreamento, PdvCliente, SavedAddress, AuditEvent,
        )])
        factory = sessionmaker(bind=isolated, autoflush=False)
        uid, source_id, target_id, pdv_id = (uuid.uuid4() for _ in range(4))
        with factory() as db:
            db.add(Usuario(id=uid, nome='Fixture QA', email='fixture-qa@example.test', senha_hash='unused'))
            db.add_all([
                Cliente(id=source_id, nome='Ana Correia', telefone='+5511987654321'),
                Cliente(id=target_id, nome='Ana Correia Silva'),
                PdvCliente(id=pdv_id, nome='Ana Correia', telefone='+5511987654321'),
            ])
            db.commit()
            token = merge_customers(db, target_id, source_id)['plan_token']
            db.rollback()
        loaded, run_selection, lock_requested = Event(), Event(), Event()
        original_lock = address_book.lock_addresses
        def selection_lock(db):
            lock_requested.set()
            return original_lock(db)
        monkeypatch.setattr(address_book, 'lock_addresses', selection_lock)

        def select_cached():
            with factory() as db:
                # Keep strong references: SQLAlchemy's identity map must really
                # contain the pre-merge customer and unlinked account.
                stale_customer = db.get(Cliente, source_id)
                stale_account = db.get(PdvCliente, pdv_id)
                actor = db.get(Usuario, uid)
                assert stale_customer.ativo and stale_customer.merged_into_id is None
                assert stale_account.cadastro_cliente_id is None
                loaded.set()
                assert run_selection.wait(timeout=10)
                selected = pdv_customers.select(db, SimpleNamespace(source='pdv', id=pdv_id), actor)
                linked = selected.cadastro_cliente_id
                db.commit()
                return linked

        with ThreadPoolExecutor(max_workers=1) as executor:
            selection = executor.submit(select_cached)
            assert loaded.wait(timeout=10)
            with factory() as db:
                result = merge_customers(db, target_id, source_id, apply=True, expected_plan=token)
                assert result['state'] == 'merged'
                # The consolidation holds the shared identity lock. Selection
                # must wait for it before reading or assigning the directory ID.
                run_selection.set()
                try:
                    assert lock_requested.wait(timeout=5)
                    assert not selection.done()
                finally:
                    db.commit()
            assert selection.result(timeout=10) == target_id
        with factory() as db:
            assert db.get(Cliente, source_id).merged_into_id == target_id
            assert db.get(PdvCliente, pdv_id).cadastro_cliente_id == target_id
    finally:
        isolated.dispose()
