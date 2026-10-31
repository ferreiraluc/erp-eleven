"""Freight identity cannot reintroduce a customer alias during consolidation."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import uuid

import pytest
import sqlalchemy as sa

from test_access_postgres import pg
from test_superfrete_tracking_concurrency_postgres import shipping_pg
from app.database import Base
from app.models import Cliente, Rastreamento
from app.models.access import AuditEvent
from app.models.address_book import FreightOrder
from app.services.customer_maintenance import merge_customers
from app.services.superfrete import sync_tracking


@pytest.fixture
def merging_pg(shipping_pg):
    factory, engine, ids = shipping_pg
    target_id = uuid.uuid4()
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[AuditEvent.__table__])
        db.add(Cliente(id=target_id, nome='Destinatário Sintético Atual'))
        db.commit()
        token = merge_customers(db, target_id, ids[1])['plan_token']
        db.rollback()
    return factory, engine, ids, target_id, token


def test_sync_waits_for_merge_and_resolves_cached_source_to_principal(merging_pg):
    factory, engine, ids, target_id, token = merging_pg
    _, source_id, _, rid, fid = ids
    loaded, waiting, start = Event(), Event(), Barrier(2)
    def before_execute(conn, cursor, statement, parameters, context, many):
        if conn.info.get('merge_sync_test') and statement == 'LOCK TABLE clientes IN ROW EXCLUSIVE MODE':
            waiting.set()
    def synchronize_cached():
        with factory() as db:
            info = db.connection().info
            info['merge_sync_test'] = True
            try:
                cached = db.get(Cliente, source_id)
                freight = db.get(FreightOrder, fid)
                assert cached.merged_into_id is None
                loaded.set()
                start.wait(timeout=10)
                sync_tracking(db, freight)
                db.commit()
            finally:
                info.pop('merge_sync_test', None)
    sa.event.listen(engine, 'before_cursor_execute', before_execute)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            syncing = executor.submit(synchronize_cached)
            assert loaded.wait(timeout=10)
            with factory() as merger:
                assert merge_customers(merger, target_id, source_id, apply=True, expected_plan=token)['state'] == 'merged'
                start.wait(timeout=10)
                try:
                    assert waiting.wait(timeout=10)
                    assert not syncing.done()
                finally:
                    merger.commit()
            syncing.result(timeout=10)
        with factory() as db:
            assert db.get(Cliente, source_id).merged_into_id == target_id
            assert db.get(Rastreamento, rid).cliente_id == target_id
            assert db.get(FreightOrder, fid).payload['_customer_id'] == str(source_id)
    finally:
        sa.event.remove(engine, 'before_cursor_execute', before_execute)


def test_merge_waits_for_sync_then_moves_its_new_customer_link(merging_pg):
    factory, engine, ids, target_id, _ = merging_pg
    _, source_id, _, rid, fid = ids
    guarded, merging, release_sync = Event(), Event(), Event()
    def after_execute(conn, cursor, statement, parameters, context, many):
        if conn.info.get('merge_sync_test') and statement == 'LOCK TABLE clientes IN ROW EXCLUSIVE MODE':
            guarded.set()
            assert release_sync.wait(timeout=10)
    def before_execute(conn, cursor, statement, parameters, context, many):
        if conn.info.get('customer_merge_test') and 'IN SHARE ROW EXCLUSIVE MODE' in statement:
            merging.set()
    def synchronize():
        with factory() as db:
            info = db.connection().info
            info['merge_sync_test'] = True
            try:
                sync_tracking(db, db.get(FreightOrder, fid))
                db.commit()
            finally:
                info.pop('merge_sync_test', None)
    def merge_after_sync():
        with factory() as db:
            info = db.connection().info
            info['customer_merge_test'] = True
            try:
                # The reviewed plan is built only after the concurrent sync
                # releases its guard, so it includes the newly linked parcel.
                plan = merge_customers(db, target_id, source_id)
                result = merge_customers(db, target_id, source_id, apply=True, expected_plan=plan['plan_token'])
                db.commit()
                return result['state']
            finally:
                info.pop('customer_merge_test', None)
    sa.event.listen(engine, 'before_cursor_execute', before_execute)
    sa.event.listen(engine, 'after_cursor_execute', after_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            syncing = executor.submit(synchronize)
            try:
                assert guarded.wait(timeout=10)
                consolidating = executor.submit(merge_after_sync)
                assert merging.wait(timeout=10)
                assert not consolidating.done()
            finally:
                release_sync.set()
            syncing.result(timeout=10)
            assert consolidating.result(timeout=10) == 'merged'
        with factory() as db:
            assert db.get(Cliente, source_id).merged_into_id == target_id
            assert db.get(Rastreamento, rid).cliente_id == target_id
            assert db.get(FreightOrder, fid).payload['_customer_id'] == str(source_id)
    finally:
        sa.event.remove(engine, 'before_cursor_execute', before_execute)
        sa.event.remove(engine, 'after_cursor_execute', after_execute)
