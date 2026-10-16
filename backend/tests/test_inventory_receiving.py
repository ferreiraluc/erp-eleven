"""Metadata-only arrival collections; isolated fixtures, no real inventory writes."""
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_assistant import setup
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg, upgrade
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier, StockMovement
from app.models.inventory_receiving import ReceivingLot, ReceivingLotItem
from app.api.endpoints import inventory_receiving as service


@pytest.fixture
def lots_app(manager_stock_app):
    factory, client, user_id = manager_stock_app
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[ReceivingLot.__table__, ReceivingLotItem.__table__])
    return factory, client, user_id


def seed(factory):
    with factory() as db:
        items = [Item(name=f'Produto {index}', sku_internal=f'RCV-{index}',
                      created_at=datetime.fromisoformat(moment), current_stock=7, stock_loja=7,
                      group_key='same-family', image_data='x'*200000)
                 for index, moment in enumerate(['2026-10-14T23:59:59','2026-10-15T00:00:00','2026-10-15T23:59:59','2026-10-16T00:00:00'])]
        db.add_all(items); db.commit()
        return [row.id for row in items]


def payload(ids):
    return dict(request_id=str(uuid.uuid4()), name='Leva 1', notes='Container', received_on='2026-10-15', item_ids=list(map(str,ids)), confirm=True)


def test_date_selection_boundaries_freezes_explicit_ids_without_photos(lots_app):
    factory, client, _=lots_app
    ids=seed(factory)
    result=client.get('/api/inventory/receiving-candidates',params={'date_from':'2026-10-15','date_to':'2026-10-15'})
    assert result.status_code==200, result.text
    assert {r['id'] for r in result.json()['items']}==set(map(str,ids[1:3]))
    assert 'image_data' not in result.text and len(result.content)<1500
    body=payload(ids[1:3]); response=client.post('/api/inventory/receiving-lots',json=body)
    assert response.status_code==201, response.text
    assert client.post('/api/inventory/receiving-lots',json=body).json()['id']==response.json()['id']
    assert client.post('/api/inventory/receiving-lots',json={**body,'name':'changed'}).status_code==409
    filtered=client.get('/api/inventory/items',params={'receiving_lot_id':response.json()['id'],'include_images':False}).json()
    assert filtered['total']==2
    groups=client.get('/api/inventory/groups',params={'receiving_lot_id':response.json()['id'],'include_images':False}).json()
    assert len(groups)==1 and {i['id'] for i in groups[0]['items']}==set(map(str,ids[1:3]))
    with factory() as db:
        assert db.query(ReceivingLot).count()==1 and db.query(ReceivingLotItem).count()==2
        assert db.query(StockMovement).count()==0
        assert all(i.current_stock==7 and i.group_key=='same-family' for i in db.query(Item))


def test_add_remove_multiple_lots_and_edit_preserve_products(lots_app):
    factory,client,_=lots_app; ids=seed(factory)
    lot=client.post('/api/inventory/receiving-lots',json=payload(ids[:1])).json()
    for _ in range(2):
        response=client.post(f"/api/inventory/receiving-lots/{lot['id']}/items",json={'item_ids':list(map(str,ids[:3])),'confirm':True})
        assert response.status_code==200 and response.json()['item_count']==3
    assert client.post('/api/inventory/receiving-lots',json=payload(ids[:1])).status_code==201
    updated=client.patch(f"/api/inventory/receiving-lots/{lot['id']}",json={'name':'Leva corrigida','notes':'Revisão','received_on':'2026-10-16'})
    assert updated.status_code==200 and updated.json()['name']=='Leva corrigida'
    page=client.get(f"/api/inventory/receiving-lots/{lot['id']}/items",params={'page_size':1}).json()
    assert page['lot']['item_count']==3 and len(page['items'])==1
    member=page['items'][0]
    assert client.delete(f"/api/inventory/receiving-lots/{lot['id']}/items/{member['id']}").status_code==204
    with factory() as db: assert db.query(Item).count()==4 and db.query(StockMovement).count()==0


def test_invalid_missing_and_role_checks(lots_app):
    factory,client,user_id=lots_app; ids=seed(factory)
    assert client.post('/api/inventory/receiving-lots',json=payload([uuid.uuid4()])).status_code==409
    assert client.post('/api/inventory/receiving-lots',json={**payload(ids[:1]),'confirm':False}).status_code==422
    assert client.get('/api/inventory/receiving-candidates',params={'date_from':'2026-10-16','date_to':'2026-10-15'}).status_code==422
    assert client.get('/api/inventory/receiving-candidates',params={'date_from':'2026-01-01','date_to':'2026-10-15'}).status_code==422
    with factory() as db:
        assert db.query(ReceivingLot).count()==0
        from app.models.usuario import UsuarioRole
        db.get(Usuario,user_id).role=UsuarioRole.VENDEDOR; db.commit()
    assert client.post('/api/inventory/receiving-lots',json=payload(ids[:1])).status_code==403
    assert client.get('/api/inventory/receiving-lots').status_code==200


def test_postgres_migration_concurrent_membership_and_deleted_snapshot(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Supplier,Item)])
        with isolated.begin() as c:
            upgrade(c,'j2e3f4a5b6c7_inventory_receiving.py')
        factory=sessionmaker(bind=isolated,autoflush=False)
        with factory() as db:
            user=Usuario(nome='Teste',email='test@example.com',senha_hash='unused');db.add(user);db.commit();uid=user.id
        ids=seed(factory)
        with factory() as db:
            body=service.LotCreate(**payload(ids[:1])); lot=service.create_lot(body,db,db.get(Usuario,uid))
        barrier=Barrier(2)
        def attach(_):
            with factory() as db:
                user=db.get(Usuario,uid);barrier.wait(timeout=5)
                return service.attach(lot['id'],service.LotAttach(item_ids=ids[:3],confirm=True),db,user)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(attach,range(2)))
        assert all(r['item_count']==3 for r in results)
        with factory() as db:
            assert db.query(ReceivingLotItem).count()==3
            db.execute(sa.delete(Item).where(Item.id==ids[0]));db.commit()
            orphan=db.query(ReceivingLotItem).filter(ReceivingLotItem.item_id.is_(None)).one()
            assert orphan.item_name=='Produto 0' and orphan.item_sku=='RCV-0'
    finally: isolated.dispose()


def test_postgres_creation_dates_use_brasilia_midnight_not_utc(pg):
    from types import SimpleNamespace
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Supplier,Item)])
        factory=sessionmaker(bind=isolated)
        with factory() as db:
            for index,moment in enumerate(['2026-10-15T02:59:59','2026-10-15T03:00:00','2026-10-16T02:59:59','2026-10-16T03:00:00']):
                db.add(Item(name=f'Produto {index}',sku_internal=f'TZ-{index}',created_at=datetime.fromisoformat(moment)))
            db.commit()
            result=service.candidates(datetime(2026,10,15).date(),datetime(2026,10,15).date(),db,SimpleNamespace())
            assert {r['sku_internal'] for r in result['items']}=={'TZ-1','TZ-2'}
    finally: isolated.dispose()
