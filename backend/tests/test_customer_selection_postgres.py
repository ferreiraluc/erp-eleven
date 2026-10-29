"""Selected-group locking and rollback on disposable PostgreSQL."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
from app.models.pdv import PdvCliente
from app.models.address_book import SavedAddress
from app.models.access import AuditEvent
from app.services.customer_maintenance import merge_customer_selection
from app.services.user_audit import bind_actor


@pytest.fixture
def group(pg, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in
        (Usuario, Vendedor, Cliente, PdvCliente, Pedido, Rastreamento, SavedAddress, AuditEvent)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    uid = uuid.uuid4()
    target_id, first_id, second_id = [uuid.uuid4() for _ in range(3)]
    with factory() as db:
        db.add(Usuario(id=uid, nome='Lucas', email='fixture@example.test', senha_hash='unused'))
        db.add_all([Cliente(id=row_id, nome='Mesmo Cliente') for row_id in (target_id, first_id, second_id)])
        db.flush()
        db.add(SavedAddress(label='Casa', data={'pais': 'PY', 'nome': 'Mesmo Cliente', 'cidade': 'Asunción'},
                            cliente_id=first_id, created_by=uid))
        db.add(PdvCliente(nome='Mesmo Cliente', cadastro_cliente_id=second_id, saldo_fiado_gs=25))
        db.commit()
    try:
        yield factory, uid, target_id, [first_id, second_id]
    finally:
        isolated.dispose()


def test_group_merge_serializes_concurrent_retries_and_keeps_unique_documents(group):
    factory, uid, target_id, source_ids = group
    with factory() as db:
        db.get(Cliente, source_ids[0]).cpf = '12345678909'
        db.commit()
        plan = merge_customer_selection(db, target_id, source_ids)['plan_token']
        db.rollback()
    barrier = Barrier(2)
    def run(_):
        with factory() as db:
            bind_actor(db, db.get(Usuario, uid))
            barrier.wait(timeout=10)
            result = merge_customer_selection(db, target_id, source_ids, apply=True, expected_plan=plan)
            db.commit()
            return result['state']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == ['already_merged', 'merged']
    with factory() as db:
        assert db.get(Cliente, target_id).cpf is None
        assert db.get(Cliente, source_ids[0]).cpf == '12345678909'
        assert all(db.get(Cliente, source_id).merged_into_id == target_id for source_id in source_ids)
        assert db.query(SavedAddress).one().cliente_id == target_id
        assert db.query(PdvCliente).one().cadastro_cliente_id == target_id
        assert db.query(PdvCliente).one().saldo_fiado_gs == 25
        assert db.query(AuditEvent).filter_by(action='customers_merged').count() == 1


def test_rollback_reverts_whole_group_and_relationships(group):
    factory, uid, target_id, source_ids = group
    with factory() as db:
        plan = merge_customer_selection(db, target_id, source_ids)['plan_token']
        bind_actor(db, db.get(Usuario, uid))
        merge_customer_selection(db, target_id, source_ids, apply=True, expected_plan=plan)
        db.rollback()
    with factory() as db:
        assert all(db.get(Cliente, source_id).merged_into_id is None for source_id in source_ids)
        assert db.query(SavedAddress).one().cliente_id == source_ids[0]
        assert db.query(PdvCliente).one().cadastro_cliente_id == source_ids[1]
        assert db.query(AuditEvent).count() == 0


def test_changed_relationship_invalidates_preview_under_postgres_locks(group):
    factory, _, target_id, source_ids = group
    with factory() as db:
        token = merge_customer_selection(db, target_id, source_ids)['plan_token']; db.rollback()
    with factory() as writer:
        writer.query(SavedAddress).one().cliente_id = source_ids[1]
        writer.commit()
    with factory() as db:
        with pytest.raises(HTTPException, match='nova prévia'):
            merge_customer_selection(db, target_id, source_ids, apply=True, expected_plan=token)
        db.rollback()
        assert all(db.get(Cliente, source_id).merged_into_id is None for source_id in source_ids)


def test_overlapping_groups_cannot_move_one_source_to_different_principals(group):
    factory, _, first_target, source_ids = group
    second_target, shared_source = source_ids
    with factory() as db:
        first_token = merge_customer_selection(db, first_target, [shared_source])['plan_token']; db.rollback()
        second_token = merge_customer_selection(db, second_target, [shared_source])['plan_token']; db.rollback()
    barrier = Barrier(2)
    def run(pair):
        target, token = pair
        with factory() as db:
            barrier.wait(timeout=10)
            try:
                result = merge_customer_selection(db, target, [shared_source], apply=True, expected_plan=token)
                db.commit()
                return result['state']
            except HTTPException as exc:
                assert exc.status_code == 409
                db.rollback()
                return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [(first_target, first_token), (second_target, second_token)])) == ['conflict', 'merged']
    with factory() as db:
        assert db.get(Cliente, shared_source).merged_into_id in {first_target, second_target}
        assert sum(db.get(Cliente, customer_id).merged_into_id is None for customer_id in [first_target, second_target]) == 2
