"""PostgreSQL-only claims, read-only safety and 50k-row index evidence."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from threading import Barrier

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.inventory import Item
from app.models.system_quality import QualityConfig, QualityRun
from app.services import quality_checks, system_quality
from test_access_postgres import pg
from test_system_quality import MODELS, MOMENT


@pytest.fixture
def factory(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in MODELS])
    factory = sessionmaker(bind=isolated, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add(QualityConfig(id=1, first_run_on=MOMENT.date(), local_time='08:30'))
        db.commit()
    try:
        yield factory
    finally:
        isolated.dispose()


def test_overlapping_workers_claim_daily_report_once(factory):
    ready = Barrier(2)
    def claim(_):
        with factory() as db:
            ready.wait(timeout=10)
            result = system_quality.claim_run(db, MOMENT)
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(claim, range(2)))
    assert sum(claim is not None for claim in claims) == 1
    with factory() as db:
        assert db.query(QualityRun).count() == 1
        assert db.query(QualityRun).one().attempts == 1


def test_checker_transaction_cannot_write_even_if_future_checker_has_bug(factory, monkeypatch):
    def writes(db, moment, output, health):
        db.query(QualityConfig).filter_by(id=1).update({'enabled': False})
    monkeypatch.setitem(quality_checks.FUNCTIONS, 'inventory', writes)
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online'})
    assert report['coverage']['inventory']['error'] == 'check_unavailable'
    with factory() as db:
        assert db.get(QualityConfig, 1).enabled is True


def test_daily_and_manual_workers_share_one_provider_budget_even_with_stale_config(factory):
    from app.models.system_quality import QualityRun
    import uuid
    identities = [uuid.uuid4(), uuid.uuid4()]
    with factory() as db:
        for identity, kind in zip(identities, ('daily', 'manual')):
            db.add(QualityRun(id=identity, run_day=MOMENT.date(), kind=kind, status='running',
                lease_token=str(identity), lease_until=MOMENT + timedelta(minutes=3), started_at=MOMENT))
        db.commit()
    ready = Barrier(2)
    report = {'counters': {}, 'findings': [], 'coverage': {'inventory': {'checked': 0, 'complete': True}}}
    def reserve(identity):
        with factory() as db:
            stale = db.get(QualityConfig, 1)
            assert stale.ai_reserved_on is None
            claim = system_quality.QualityClaim(identity, str(identity), True, False)
            ready.wait(timeout=10)
            result = system_quality._save_report(db, claim, report, MOMENT)
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, identities))
    assert sorted(results) == [False, True]


def test_old_run_cannot_move_new_day_provider_reservation_backwards(factory):
    import uuid
    identities = [uuid.uuid4(), uuid.uuid4()]
    report = {'counters': {}, 'findings': [], 'coverage': {'inventory': {'checked': 0, 'complete': True}}}
    with factory() as db:
        for identity in identities:
            db.add(QualityRun(id=identity, run_day=MOMENT.date(), kind='manual', status='running',
                             lease_token=str(identity), lease_until=MOMENT + timedelta(minutes=3), created_at=MOMENT))
        db.commit()
    newer = MOMENT + timedelta(days=1)
    with factory() as db:
        first = system_quality.QualityClaim(identities[0], str(identities[0]), True, False)
        assert system_quality._save_report(db, first, report, newer)
        db.commit()
    with factory() as db:
        older = system_quality.QualityClaim(identities[1], str(identities[1]), True, False)
        assert not system_quality._save_report(db, older, report, MOMENT)
        db.commit()
        assert db.get(QualityConfig, 1).ai_reserved_on == newer.astimezone(system_quality.BRT).date()
        assert db.get(QualityRun, identities[1]).ai_status == 'budget_exhausted'


def test_overlapping_workers_retire_exhausted_report_with_one_alert(factory):
    import uuid
    from app.models.notification import Notification
    from app.models.usuario import Usuario, UsuarioRole
    identity = uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=uuid.uuid4(), nome='Lucas', email='lucas@eleven.com', senha_hash='unused', role=UsuarioRole.ADMIN))
        db.get(QualityConfig, 1).local_time = '23:59'
        db.add(QualityRun(id=identity, run_day=MOMENT.date(), kind='manual', status='running', attempts=3,
                         lease_token='expired-fixture', lease_until=MOMENT - timedelta(seconds=1), created_at=MOMENT))
        db.commit()
    ready = Barrier(2)
    def retire(_):
        with factory() as db:
            ready.wait(timeout=10)
            result = system_quality.claim_run(db, MOMENT)
            db.commit()
            return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(retire, range(2))) == [None, None]
    with factory() as db:
        row = db.get(QualityRun, identity)
        assert row.status == 'failed' and row.finished_at is not None
        assert row.lease_token is None and row.lease_until is None
        assert db.query(Notification).filter_by(dedupe_key='quality-failed:' + str(identity)).count() == 1


@pytest.mark.parametrize('database_timezone', ['UTC', 'America/Sao_Paulo'])
def test_recent_window_preserves_legacy_naive_timestamp_model_convention(pg, database_timezone):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema} -ctimezone={database_timezone}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in MODELS])
        factory = sessionmaker(bind=isolated, expire_on_commit=False)
        with factory() as db:
            # Uses the existing Item.updated_at default settings.now() (BRT,
            # aware) and the existing TIMESTAMP WITHOUT TIME ZONE model column.
            db.add(Item(name='Local timestamp fixture', sku_internal='LOCAL-TIMEZONE', current_stock=0,
                        stock_loja=0, stock_deposito=0, brand='Fixture', category='Fixture', sale_price=1))
            db.commit()
        report = quality_checks.collect(factory, datetime.now(timezone.utc), {'notifications': 'online'})
        assert report['coverage']['inventory']['checked'] == 1
        assert report['coverage']['inventory']['complete']
    finally:
        isolated.dispose()


def test_migration_preserves_rows_and_recent_window_uses_index_with_50000_items(pg):
    engine, schema = pg
    module_path = Path(__file__).parents[1] / 'alembic' / 'versions' / 'q9f0a1b2c3d4_quality_recent_indexes.py'
    spec = importlib.util.spec_from_file_location('quality_migration', module_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as conn:
        conn.exec_driver_sql(f'SET search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE inventory_items (id uuid PRIMARY KEY, updated_at timestamp NOT NULL, is_active boolean, deleted_at timestamptz, name varchar(200), color varchar(50), size varchar(50))')
        conn.exec_driver_sql('CREATE TABLE clientes (id uuid PRIMARY KEY, updated_at timestamp, merged_into_id uuid)')
        conn.exec_driver_sql('CREATE TABLE saved_addresses (id uuid PRIMARY KEY, updated_at timestamptz, merged_into_id uuid)')
        conn.exec_driver_sql('CREATE TABLE print_jobs (id uuid PRIMARY KEY, status varchar(20), created_at timestamptz)')
        conn.execute(sa.text("""INSERT INTO inventory_items SELECT md5(n::text)::uuid,
            :recent - CASE WHEN n > 49980 THEN INTERVAL '1 hour' ELSE INTERVAL '30 days' END, true, NULL,
            'Modelo ' || lpad(mod(n,1000)::text,4,'0'),
            CASE WHEN mod(n,10)=0 THEN NULL WHEN mod(n,2)=0 THEN 'Preto' ELSE 'Branco' END,
            CASE WHEN mod(n,7)=0 THEN NULL WHEN mod(n,3)=0 THEN 'L' ELSE 'M' END
            FROM generate_series(1,50000) n"""), {'recent': MOMENT})
        conn.exec_driver_sql('ANALYZE inventory_items')
        catalog_sql = ('SELECT id,name,color,size FROM inventory_items WHERE deleted_at IS NULL '
                       'ORDER BY name,color,size,id OFFSET 0 LIMIT 50')
        before_ids = [row.id for row in conn.exec_driver_sql(catalog_sql)]
        before_catalog = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + catalog_sql).scalar()[0]
        conn.commit()
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            with context.begin_transaction():
                migration.upgrade()
        conn.commit()
        assert conn.exec_driver_sql('SELECT count(*) FROM inventory_items').scalar() == 50000
        conn.exec_driver_sql('ANALYZE inventory_items')
        plan = conn.execute(sa.text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id FROM inventory_items WHERE deleted_at IS NULL AND is_active IS true AND updated_at >= :since AND updated_at <= :moment ORDER BY updated_at,id LIMIT 501'), {'since': MOMENT - timedelta(days=1), 'moment': MOMENT}).scalar()[0]
        indexes = []
        def walk(node):
            if 'Index Name' in node: indexes.append(node['Index Name'])
            for child in node.get('Plans', []): walk(child)
        walk(plan['Plan'])
        assert 'ix_quality_inventory_recent' in indexes
        assert plan['Plan']['Actual Rows'] == 20
        after_catalog = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + catalog_sql).scalar()[0]
        assert before_ids == [row.id for row in conn.exec_driver_sql(catalog_sql)]
        def nodes(node):
            yield node
            for child in node.get('Plans', []):
                yield from nodes(child)
        before_nodes = list(nodes(before_catalog['Plan']))
        after_nodes = list(nodes(after_catalog['Plan']))
        assert any(node['Node Type'] == 'Sort' for node in before_nodes)
        assert sum(node['Actual Rows'] * node['Actual Loops'] for node in before_nodes
                   if 'Seq Scan' in node['Node Type']) >= 50000
        assert any(node.get('Index Name') == 'ix_inventory_catalog_order' for node in after_nodes)
        assert not any(node['Node Type'] == 'Sort' for node in after_nodes)
        assert after_catalog['Plan']['Actual Rows'] == 50
        print(f"Catalog 50k fixture default order: before={before_catalog['Execution Time']:.3f} ms, "
              f"after={after_catalog['Execution Time']:.3f} ms, 50 identical IDs")
        # Retry after a separately committed concurrent index build preserves both
        # existing rows and the same deterministic ordering, including NULL facets.
        conn.commit()
        with Operations.context(context), context.begin_transaction():
            migration.upgrade()
        assert conn.exec_driver_sql('SELECT count(*) FROM inventory_items').scalar() == 50000
        assert before_ids == [row.id for row in conn.exec_driver_sql(catalog_sql)]
        # Do not turn local fixture timings into a production SLA.
        print(f"Quality 50k fixture recent IDs: {plan['Execution Time']:.3f} ms, 20 rows, index={indexes[0]}")


def test_transactional_tables_migration_preserves_users_and_daily_uniqueness(pg):
    import uuid
    engine, schema = pg
    module_path = Path(__file__).parents[1] / 'alembic' / 'versions' / 'p8e9f0a1b2c3_daily_quality.py'
    spec = importlib.util.spec_from_file_location('quality_table_migration', module_path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    identity = uuid.uuid4()
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE usuarios(id uuid PRIMARY KEY, nome varchar(100))')
        conn.execute(sa.text('INSERT INTO usuarios VALUES(:id,:name)'), {'id': identity, 'name': 'Fixture'})
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        assert conn.execute(sa.text('SELECT nome FROM usuarios WHERE id=:id'), {'id': identity}).scalar() == 'Fixture'
        actual = {column['name'] for column in sa.inspect(conn).get_columns('quality_runs', schema=schema)}
        assert actual == {column.name for column in QualityRun.__table__.columns}
        actual_config = {column['name'] for column in sa.inspect(conn).get_columns('quality_config', schema=schema)}
        assert actual_config == {column.name for column in QualityConfig.__table__.columns}
        assert 'uq_quality_run_daily' in {index['name'] for index in sa.inspect(conn).get_indexes('quality_runs', schema=schema)}
        assert 'ix_quality_runs_created' in {index['name'] for index in sa.inspect(conn).get_indexes('quality_runs', schema=schema)}
