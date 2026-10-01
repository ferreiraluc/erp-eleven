"""Inventory count races and additive migration in disposable local PG schemas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg, upgrade
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier, StockMovement, InventorySession, InventorySessionItem, SessionStatus
from app.schemas.inventory import ScanItemCreate
from app.api.endpoints.inventory import scan_item
from app.services.inventory_service import apply_session, create_movement, StockMovementError


@pytest.fixture
def session_pg(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema} -clock_timeout=5000 -cstatement_timeout=10000'})
    Base.metadata.create_all(isolated,tables=[m.__table__ for m in (
        Usuario,Vendedor,Supplier,Item,StockMovement,InventorySession,InventorySessionItem)])
    factory=sessionmaker(bind=isolated,autoflush=False)
    uid,pid,sid=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=uid,nome='Local test',email='fixture@example.com',senha_hash='unused'));db.flush()
        db.add(Item(id=pid,name='Local test',sku_internal='LOCAL',current_stock=10,stock_loja=6,stock_deposito=4,created_by=uid))
        db.add(InventorySession(id=sid,name='Local test',count_location='deposito',status=SessionStatus.open,created_by=uid));db.commit()
    try:yield factory,uid,pid,sid
    finally:isolated.dispose()


def reviewed(factory,pid,sid,quantity=3):
    with factory() as db:
        db.get(InventorySession,sid).status=SessionStatus.reviewing
        db.add(InventorySessionItem(session_id=sid,item_id=pid,system_quantity=4,counted_quantity=quantity));db.commit()


def test_count_migration_keeps_legacy_scope_null_and_all_history(pg):
    engine,schema=pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE inventory_sessions(id uuid PRIMARY KEY,name text,location_filter text,status text)')
        conn.exec_driver_sql('CREATE TABLE inventory_session_items(id uuid PRIMARY KEY,session_id uuid,item_id uuid,system_quantity integer,counted_quantity integer)')
        sid,pid=uuid.uuid4(),uuid.uuid4()
        conn.execute(sa.text('INSERT INTO inventory_sessions VALUES(:id,\'Legacy\',\'deposito\',\'reviewing\')'),{'id':sid})
        # Duplicate historical readings remain untouched and diagnosable.
        for quantity in (10,11):
            conn.execute(sa.text('INSERT INTO inventory_session_items VALUES(:id,:sid,:pid,10,:qty)'),dict(id=uuid.uuid4(),sid=sid,pid=pid,qty=quantity))
        upgrade(conn,'b8c9d0e1f2a3_inventory_count_location.py')
        row=conn.execute(sa.text('SELECT id,location_filter,status,count_location FROM inventory_sessions')).one()
        assert row==(sid,'deposito','reviewing',None)
        assert conn.execute(sa.text('SELECT counted_quantity FROM inventory_session_items ORDER BY counted_quantity')).scalars().all()==[10,11]
        column=next(c for c in sa.inspect(conn).get_columns('inventory_sessions',schema=schema) if c['name']=='count_location')
        assert column['nullable'] and column['default'] is None


def test_two_scans_serialize_without_duplicate_rows(session_pg):
    factory,uid,pid,sid=session_pg
    ready=Barrier(2)
    def count(quantity):
        with factory() as db:
            assert db.get(InventorySession,sid).status==SessionStatus.open
            assert db.get(Item,pid).stock_deposito==4
            ready.wait(timeout=5)
            return scan_item(str(sid),ScanItemCreate(item_id=pid,counted_quantity=quantity),db,SimpleNamespace(id=uid))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(count,[2,3]))
    assert len(results)==2
    with factory() as db:
        reading=db.query(InventorySessionItem).one()
        assert reading.counted_quantity in (2,3) and reading.system_quantity==4
        assert db.get(InventorySession,sid).status==SessionStatus.counting
        assert db.query(StockMovement).count()==0
        assert db.get(Item,pid).current_stock==10


def test_concurrent_apply_refreshes_preloaded_terminal_state_and_runs_once(session_pg):
    factory,uid,pid,sid=session_pg
    reviewed(factory,pid,sid)
    ready=Barrier(2)
    def apply(_):
        with factory() as db:
            row=db.get(InventorySession,sid)
            assert row.status==SessionStatus.reviewing and len(row.session_items)==1
            assert db.get(Item,pid).stock_deposito==4
            ready.wait(timeout=5)
            try:return ('applied',len(apply_session(db,sid,uid)))
            except StockMovementError as error:
                db.rollback();return ('rejected',error.status_code)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,range(2)))
    assert sorted(results)==[('applied',1),('rejected',409)]
    with factory() as db:
        assert db.query(StockMovement).count()==1
        product=db.get(Item,pid)
        assert (product.stock_loja,product.stock_deposito,product.current_stock)==(6,3,9)


def test_movement_committed_while_apply_waits_cannot_be_overwritten(session_pg):
    factory,uid,pid,sid=session_pg
    reviewed(factory,pid,sid)
    reached_item_lock=Event()
    isolated=factory.kw['bind']
    def observe(conn,cursor,statement,parameters,context,executemany):
        if 'inventory_items' in statement and 'FOR UPDATE' in statement:
            reached_item_lock.set()
    with factory() as moving:
        create_movement(moving,pid,'exit',1,uid,location='deposito')
        sa.event.listen(isolated,'before_cursor_execute',observe)
        try:
            def apply():
                with factory() as db:
                    assert db.get(Item,pid).stock_deposito==4
                    try:apply_session(db,sid,uid)
                    except StockMovementError as error:
                        db.rollback();return error.status_code,str(error)
                    return 200,''
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(apply)
                assert reached_item_lock.wait(timeout=5)
                moving.commit()
                code,message=future.result(timeout=10)
                assert code==409 and 'mudou após' in message
        finally:sa.event.remove(isolated,'before_cursor_execute',observe)
    with factory() as db:
        assert db.get(Item,pid).stock_deposito==3
        assert db.query(StockMovement).count()==1
        assert db.get(InventorySession,sid).status==SessionStatus.reviewing


def test_two_sessions_with_reversed_item_insertion_do_not_deadlock(session_pg):
    factory,uid,pid,sid=session_pg
    pid2,sid2=uuid.uuid4(),uuid.uuid4()
    with factory() as db:
        db.add(Item(id=pid2,name='Second',sku_internal='SECOND',current_stock=10,stock_loja=6,stock_deposito=4));db.flush()
        db.get(InventorySession,sid).status=SessionStatus.reviewing
        db.add(InventorySession(id=sid2,name='Second count',count_location='deposito',status=SessionStatus.reviewing,created_by=uid));db.flush()
        for session_id,ids in ((sid,[pid,pid2]),(sid2,[pid2,pid])):
            for product_id in ids:
                db.add(InventorySessionItem(session_id=session_id,item_id=product_id,system_quantity=4,counted_quantity=3))
        db.commit()
    ready=Barrier(2)
    def apply(session_id):
        with factory() as db:
            ready.wait(timeout=5)
            try:return ('applied',len(apply_session(db,session_id,uid)))
            except StockMovementError as error:
                db.rollback();return ('rejected',error.status_code)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,[sid,sid2]))
    assert sorted(results)==[('applied',2),('rejected',409)]
    with factory() as db:
        assert db.query(StockMovement).count()==2
        assert {r.stock_deposito for r in db.query(Item)}=={3}


def test_scan_waiting_for_session_lock_reloads_cancelled_state(session_pg):
    from fastapi import HTTPException
    factory,uid,pid,sid=session_pg
    reached_session_lock=Event()
    isolated=factory.kw['bind']
    def observe(conn,cursor,statement,parameters,context,executemany):
        if 'inventory_sessions' in statement and 'FOR UPDATE' in statement:
            reached_session_lock.set()
    with factory() as closing:
        row=closing.query(InventorySession).filter_by(id=sid).with_for_update().one()
        row.status=SessionStatus.cancelled;closing.flush()
        sa.event.listen(isolated,'before_cursor_execute',observe)
        try:
            def scan():
                with factory() as db:
                    assert db.get(InventorySession,sid).status==SessionStatus.open
                    try:scan_item(str(sid),ScanItemCreate(item_id=pid,counted_quantity=3),db,SimpleNamespace(id=uid))
                    except HTTPException as error:
                        db.rollback();return error.status_code
                    return 201
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(scan)
                assert reached_session_lock.wait(timeout=5)
                closing.commit()
                assert future.result(timeout=10)==409
        finally:sa.event.remove(isolated,'before_cursor_execute',observe)
    with factory() as db:
        assert db.query(InventorySessionItem).count()==0
        assert db.get(InventorySession,sid).status==SessionStatus.cancelled
