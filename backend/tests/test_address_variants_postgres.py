"""Address reuse and directed consolidation on disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_address_variants import ADDRESS, VARIANT
from app.database import Base
from app.models import Usuario, Vendedor, Cliente
from app.models.address_book import SavedAddress, FreightOrder
from app.models.pdv import PdvCliente
from app.models.printing import PrintDevice, PrintJob
from app.services.address_book import save_or_reuse
from app.services.address_maintenance import merge_addresses


def test_parallel_spelling_variants_reuse_one_row_and_legacy_pair_merges(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    models = (Usuario, Vendedor, Cliente, PdvCliente, SavedAddress, PrintDevice, PrintJob, FreightOrder)
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in models])
    factory = sessionmaker(bind=isolated, autoflush=False)
    user_id = uuid.uuid4()
    try:
        with factory() as db:
            db.add(Usuario(id=user_id, nome='Fixture', email='fixture@example.test', senha_hash='not-used'))
            db.commit()
        barrier = Barrier(2)

        def save(data):
            with factory() as db:
                barrier.wait(timeout=5)
                row, reused = save_or_reuse(db, data, user_id)
                key = row.id
                db.commit()
                return key, reused

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, [ADDRESS, VARIANT]))
        assert results[0][0] == results[1][0]
        assert sorted(reused for _, reused in results) == [False, True]
        with factory() as db:
            assert db.query(SavedAddress).count() == 1
            assert db.query(SavedAddress).one().data['cpf'] == VARIANT['cpf']
            # Simulate only one pair of old roots under their unchanged hashes.
            target = SavedAddress(label='Legacy target', data=ADDRESS | {'nome': 'Legacy Fixture'}, created_by=user_id)
            source = SavedAddress(label='Legacy source', data=VARIANT | {'nome': 'Legacy Fixture'}, created_by=user_id)
            db.add_all([target, source]); db.commit()
            plan = merge_addresses(db, target.id, source.id)
            assert source.merged_into_id is None
            result = merge_addresses(db, target.id, source.id, apply=True, expected_plan=plan['plan_token'])
            assert result['state'] == 'merged'
            db.commit()
            assert db.query(SavedAddress).filter_by(merged_into_id=None).count() == 2
            assert source.dedup_key is None
            assert target.data['cpf'] == VARIANT['cpf']
    finally:
        isolated.dispose()
