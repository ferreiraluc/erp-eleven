"""Real HTTP races against disposable local PostgreSQL, never the store database."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from queue import Queue
from threading import Barrier, Event
from time import monotonic, sleep
import uuid

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from test_access_postgres import pg
from test_pdv_unknown_stock import TABLES
from app.api.endpoints import pdv
from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, StockMovement
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem, PdvPayment, PdvFiadoMovement


@pytest.fixture
def pdv_pg(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={
        'options':f'-csearch_path={schema} -clock_timeout=8000 -cstatement_timeout=12000'})
    Base.metadata.create_all(isolated,tables=[model.__table__ for model in TABLES])
    factory=sessionmaker(bind=isolated,autoflush=False)
    uid,cid=uuid.uuid4(),uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=uid,nome='Local PDV owner',email='lucas@eleven.com',role=UsuarioRole.ADMIN,senha_hash='unused'))
        db.add(PdvCliente(id=cid,nome='Local PDV customer',saldo_fiado_gs=0))
        db.commit()
    app=FastAPI();app.include_router(pdv.router,prefix='/api/pdv')
    control={}
    def session():
        with factory() as db:
            if control.get('before_request'):control['before_request'](db)
            yield db
    def user():
        with factory() as db:return db.get(Usuario,uid)
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_active_user]=user
    try:
        with TestClient(app) as client:yield factory,client,cid,control,engine
    finally:isolated.dispose()


def item(factory,*,loja=10,deposito=0):
    with factory() as db:
        row=Item(name='Synthetic product',sku_internal='LOCAL-'+uuid.uuid4().hex[:12],
            current_stock=loja+deposito,stock_loja=loja,stock_deposito=deposito)
        db.add(row);db.flush();uid=row.id;db.commit();return uid


def payload(cid,lines):
    total=sum(quantity*10 for _,quantity,_ in lines)
    return {'cliente_id':str(cid),
        'items':[{'item_id':str(uid),'item_name':'Synthetic product','quantity':quantity,
                  'unit_price_gs':10,'location':location} for uid,quantity,location in lines],
        'payments':[{'method':'cash_gs','amount_original':total,'amount_gs':total}]}


def balances(db,uid):
    row=db.get(Item,uid)
    return row.current_stock,row.stock_loja,row.stock_deposito


def preload_barrier(control,item_ids,expected,sale_id=None):
    ready=Barrier(2)
    def preload(db):
        # Keep strong references: SQLAlchemy's identity map otherwise weakly holds
        # objects and a subsequent query could create fresh instances accidentally.
        loaded=[db.get(Item,uid) for uid in item_ids]
        assert [(r.current_stock,r.stock_loja,r.stock_deposito) for r in loaded]==expected
        if sale_id:
            sale=db.get(PdvSale,sale_id)
            assert sale.status=='completed' and sale.stock_applied is True
            loaded.extend([sale,*sale.items])
        db.info['held_preloaded_rows']=loaded
        ready.wait(timeout=10)
    control['before_request']=preload


def post_two(client,paths,payloads=None):
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(client.post,path,json=body) for path,body in zip(paths,payloads or [None,None])]
        return [future.result(timeout=15) for future in futures]


def test_two_eight_unit_sales_against_ten_have_one_success_and_one_conflict(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    uid=item(factory)
    preload_barrier(control,[uid],[(10,10,0)])
    body=payload(cid,[(uid,8,'loja')])
    responses=post_two(client,['/api/pdv/sales']*2,[body,body])
    control.clear()
    assert sorted(r.status_code for r in responses)==[201,409],[r.text for r in responses]
    with factory() as db:
        assert balances(db,uid)==(2,2,0)
        sale=db.query(PdvSale).one()
        assert sale.status=='completed' and sale.stock_applied is True
        assert db.query(PdvSaleItem).count()==db.query(PdvPayment).count()==1
        assert db.query(PdvFiadoMovement).count()==0
        movement=db.query(StockMovement).one()
        assert (movement.quantity,movement.quantity_before,movement.quantity_after)==(8,10,2)
        assert movement.movement_type.value=='exit' and movement.location_from=='loja'
        assert movement.reference_id==str(sale.id)


def test_repeated_item_lines_from_both_locations_compete_as_one_atomic_sale(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    uid=item(factory,loja=6,deposito=4)
    preload_barrier(control,[uid],[(10,6,4)])
    # Each request alone is valid; the second must reject the whole sale after
    # refreshing the item, even when only one location has become insufficient.
    body=payload(cid,[(uid,2,'loja'),(uid,3,'deposito')])
    responses=post_two(client,['/api/pdv/sales']*2,[body,body])
    control.clear()
    assert sorted(r.status_code for r in responses)==[201,409],[r.text for r in responses]
    with factory() as db:
        assert balances(db,uid)==(5,4,1)
        assert db.query(PdvSale).count()==db.query(PdvPayment).count()==1
        assert db.query(PdvSaleItem).count()==2
        movements=db.query(StockMovement).all()
        assert len(movements)==2
        assert {(m.location_from,m.quantity) for m in movements}=={('loja',2),('deposito',3)}


def test_two_cancellations_restore_each_original_location_exactly_once(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    uid=item(factory,loja=6,deposito=4)
    made=client.post('/api/pdv/sales',json=payload(cid,[(uid,2,'loja'),(uid,3,'deposito')]))
    assert made.status_code==201,made.text
    sale_id=uuid.UUID(made.json()['id'])
    preload_barrier(control,[uid],[(5,4,1)],sale_id)
    responses=post_two(client,[f'/api/pdv/sales/{sale_id}/cancel']*2)
    control.clear()
    assert sorted(r.status_code for r in responses)==[200,400],[r.text for r in responses]
    with factory() as db:
        assert balances(db,uid)==(10,6,4)
        sale=db.get(PdvSale,sale_id)
        assert sale.status=='cancelled' and sale.stock_applied is False
        movements=db.query(StockMovement).all()
        exits=[r for r in movements if r.movement_type.value=='exit']
        returns=[r for r in movements if r.movement_type.value=='entry']
        assert len(exits)==len(returns)==2
        assert {(r.location_to,r.quantity) for r in returns}=={('loja',2),('deposito',3)}
        assert all(r.reference_id==str(sale_id) for r in movements)
        assert db.query(PdvSale).count()==db.query(PdvPayment).count()==1
        assert db.query(PdvSaleItem).count()==2


def test_reversed_product_order_in_two_sales_locks_consistently_and_conserves_stock(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    a,b=item(factory,loja=6,deposito=4),item(factory,loja=6,deposito=4)
    preload_barrier(control,[a,b],[(10,6,4),(10,6,4)])
    bodies=[payload(cid,[(a,3,'loja'),(b,2,'deposito')]),
            payload(cid,[(b,3,'loja'),(a,2,'deposito')])]
    responses=post_two(client,['/api/pdv/sales']*2,bodies)
    control.clear()
    assert [r.status_code for r in responses]==[201,201],[r.text for r in responses]
    with factory() as db:
        assert balances(db,a)==balances(db,b)==(5,3,2)
        assert db.query(PdvSale).count()==db.query(PdvPayment).count()==2
        assert db.query(PdvSaleItem).count()==4
        for uid in (a,b):
            moves=db.query(StockMovement).filter_by(item_id=uid).all()
            assert len(moves)==2 and sum(r.quantity for r in moves)==5
            assert any(r.quantity_before==10 for r in moves) and any(r.quantity_after==5 for r in moves)


@pytest.mark.parametrize('change',[
    {'current_stock':2,'stock_loja':2},  # insufficient after another completed exit
    {'current_stock':10,'stock_loja':2},  # a preexisting/manual total mismatch
])
def test_sale_waits_for_real_lock_then_rejects_new_balance_or_mismatch(pdv_pg,change):
    factory,client,cid,control,observer_engine=pdv_pg
    uid=item(factory)
    reader_ready=Queue();start_lock=Event()
    def preload(db):
        row=db.get(Item,uid)
        assert (row.current_stock,row.stock_loja,row.stock_deposito)==(10,10,0)
        db.info['held_preloaded_rows']=[row]
        reader_ready.put(db.scalar(sa.text('SELECT pg_backend_pid()')))
        assert start_lock.wait(timeout=10)
    control['before_request']=preload
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(client.post,'/api/pdv/sales',json=payload(cid,[(uid,8,'loja')]))
        reader_pid=reader_ready.get(timeout=10)
        with factory() as writer:
            row=writer.query(Item).filter_by(id=uid).with_for_update().one()
            for field,value in change.items():setattr(row,field,value)
            writer.flush();start_lock.set()
            deadline=monotonic()+5;blocked=False
            with observer_engine.connect() as observer:
                while monotonic()<deadline:
                    blocked=bool(observer.scalar(sa.text('SELECT pg_blocking_pids(:pid)'),{'pid':reader_pid}))
                    if blocked:break
                    sleep(.01)
            assert blocked,'PDV must wait for the writer transaction, not use its stale ORM balances'
            writer.commit()
        response=future.result(timeout=15)
    control.clear()
    assert response.status_code==409,response.text
    with factory() as db:
        assert balances(db,uid)==(change['current_stock'],change['stock_loja'],0)
        assert db.get(PdvCliente,cid).saldo_fiado_gs==Decimal('0')
        for model in (PdvSale,PdvSaleItem,PdvPayment,PdvFiadoMovement,StockMovement):
            assert db.query(model).count()==0


@pytest.mark.parametrize('change',[
    {'current_stock':9,'stock_loja':8},  # mismatch committed while cancel waits
    {'current_stock':2_147_483_647,'stock_loja':2_147_483_647},  # return would overflow
])
def test_cancel_waits_reloads_and_does_not_partially_cancel_invalid_return(pdv_pg,change):
    factory,client,cid,control,observer_engine=pdv_pg
    uid=item(factory)
    made=client.post('/api/pdv/sales',json=payload(cid,[(uid,2,'loja')]))
    assert made.status_code==201,made.text
    sale_id=uuid.UUID(made.json()['id'])
    reader_ready=Queue();start_lock=Event()
    def preload(db):
        row=db.get(Item,uid);sale=db.get(PdvSale,sale_id)
        assert row.current_stock==row.stock_loja==8 and sale.status=='completed'
        db.info['held_preloaded_rows']=[row,sale,*sale.items]
        reader_ready.put(db.scalar(sa.text('SELECT pg_backend_pid()')))
        assert start_lock.wait(timeout=10)
    control['before_request']=preload
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(client.post,f'/api/pdv/sales/{sale_id}/cancel')
        reader_pid=reader_ready.get(timeout=10)
        with factory() as writer:
            row=writer.query(Item).filter_by(id=uid).with_for_update().one()
            for field,value in change.items():setattr(row,field,value)
            writer.flush();start_lock.set()
            deadline=monotonic()+5;blocked=False
            with observer_engine.connect() as observer:
                while monotonic()<deadline:
                    blocked=bool(observer.scalar(sa.text('SELECT pg_blocking_pids(:pid)'),{'pid':reader_pid}))
                    if blocked:break
                    sleep(.01)
            assert blocked,'Cancellation must wait and re-read the current stock'
            writer.commit()
        response=future.result(timeout=15)
    control.clear()
    assert response.status_code==409,response.text
    with factory() as db:
        assert balances(db,uid)==(change['current_stock'],change['stock_loja'],0)
        sale=db.get(PdvSale,sale_id)
        assert sale.status=='completed' and sale.stock_applied is True
        assert db.query(PdvSale).count()==db.query(PdvSaleItem).count()==db.query(PdvPayment).count()==1
        movement=db.query(StockMovement).one()
        assert movement.movement_type.value=='exit' and movement.quantity==2
