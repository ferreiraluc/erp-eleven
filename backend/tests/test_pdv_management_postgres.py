"""Migration and genuine concurrent revisions on disposable PostgreSQL schemas."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import uuid
from decimal import Decimal
import pytest
import sqlalchemy as sa
from test_access_postgres import pg, upgrade
from test_pdv_stock_postgres import pdv_pg, item, payload, balances
from test_pdv_management import command,review
from app.models.pdv import PdvSale,PdvSaleEvent,PdvSaleItem,PdvFiadoMovement
from app.models.inventory import Item,StockMovement


def test_migration_preserves_legacy_sales_and_initializes_returns(pg):
    engine,schema=pg
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        c.exec_driver_sql('CREATE TABLE usuarios(id uuid PRIMARY KEY)')
        c.exec_driver_sql('CREATE TABLE pdv_sales(id uuid PRIMARY KEY, status text, total_gs numeric(15,2))')
        c.exec_driver_sql('CREATE TABLE pdv_sale_items(id uuid PRIMARY KEY, quantity numeric(10,3))')
        c.exec_driver_sql("INSERT INTO pdv_sales VALUES(gen_random_uuid(),'completed',123.45)")
        c.exec_driver_sql('INSERT INTO pdv_sale_items VALUES(gen_random_uuid(),2)')
        upgrade(c,'a3b4c5d6e7f8_pdv_management.py')
        assert tuple(c.exec_driver_sql('SELECT total_gs,version,refunded_gs,fiado_reversed_gs,deleted_at FROM pdv_sales').one())==(Decimal('123.45'),1,0,0,None)
        assert tuple(c.exec_driver_sql('SELECT quantity,returned_quantity FROM pdv_sale_items').one())==(2,0)
        assert c.exec_driver_sql('SELECT count(*) FROM pdv_sale_events').scalar()==0


def test_concurrent_same_confirmation_returns_stock_once_and_replays(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    rid=item(factory,loja=5)
    sid=client.post('/api/pdv/sales',json=payload(cid,[(rid,2,'loja')])).json()['id']
    request,_=review(client,sid,command('cancel'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:client.post(f'/api/pdv/management/{sid}/commit',json=request),range(2)))
    assert [r.status_code for r in results]==[200,200],[r.text for r in results]
    assert sorted(r.json()['replayed'] for r in results)==[False,True]
    with factory() as db:
        assert balances(db,rid)==(5,5,0) and db.query(PdvSaleEvent).count()==1
        assert db.query(StockMovement).count()==2


def test_two_different_confirmations_cannot_refund_same_piece_twice(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    rid=item(factory,loja=5)
    sid=client.post('/api/pdv/sales',json=payload(cid,[(rid,2,'loja')])).json()['id']
    detail=client.get('/api/pdv/management/'+sid).json()
    body=command('return',lines=[{'line_id':detail['items'][0]['id'],'quantity':1,'restock':True}])
    requests=[review(client,sid,body)[0] for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda b:client.post(f'/api/pdv/management/{sid}/commit',json=b),requests))
    assert sorted(r.status_code for r in results)==[200,409]
    with factory() as db:
        assert balances(db,rid)==(4,4,0) and db.query(PdvSaleEvent).count()==1
        assert db.query(PdvSaleItem).one().returned_quantity==1


def test_review_waits_for_product_lock_and_rejects_changed_stock(pdv_pg):
    factory,client,cid,control,_=pdv_pg
    rid=item(factory,loja=5)
    sid=client.post('/api/pdv/sales',json=payload(cid,[(rid,2,'loja')])).json()['id']
    request,_=review(client,sid,command('cancel'))
    started=Event()
    def commit():
        started.set();return client.post(f'/api/pdv/management/{sid}/commit',json=request)
    with factory() as db,ThreadPoolExecutor(max_workers=1) as pool:
        row=db.query(Item).filter_by(id=rid).with_for_update().one()
        future=pool.submit(commit);assert started.wait(3)
        try:
            with pytest.raises(TimeoutError):future.result(timeout=.2)
        finally:
            row.stock_loja=4;row.current_stock=4;db.commit()
        assert future.result(timeout=5).status_code==409
    with factory() as db:
        assert balances(db,rid)==(4,4,0) and db.query(PdvSaleEvent).count()==0
        assert db.query(PdvSale).one().status=='completed'
