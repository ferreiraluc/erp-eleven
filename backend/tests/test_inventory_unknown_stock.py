"""Legacy NULL balances stay unknown on reads and never become stock movements."""
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import update

from test_assistant import setup
from test_inventory_ocr import stock_app
from app.models.usuario import Usuario, UsuarioRole
from app.models.inventory import Item, StockMovement
from app.services.inventory_service import _compute_alert_level, create_movement, StockMovementError


STOCK_FIELDS=('current_stock','stock_loja','stock_deposito')
ERROR='Há saldo desconhecido neste produto. Nenhuma movimentação foi registrada; confira os dados do estoque.'


def add(db,name='Camisa',*,key=None,total=6,loja=4,deposito=2,group='Grupo',active=True,missing=None,minimum=None,maximum=None):
    row=Item(id=uuid.UUID(f'a0000000-0000-0000-0000-{key:012x}') if key else uuid.uuid4(),name=name,sku_internal='TEST-'+uuid.uuid4().hex[:8],
        barcode='789001',current_stock=total,stock_loja=loja,stock_deposito=deposito,
        is_active=active,group_key=group,cost_price=Decimal('10.00'))
    db.add(row);db.flush()
    # Force historical NULL after insertion; ORM insert defaults would turn None into 0.
    changes={'min_stock':minimum,'max_stock':maximum}
    if missing:changes[missing]=None
    db.execute(update(Item).where(Item.id==row.id).values(**changes));db.refresh(row)
    return row


def balances(row):
    return tuple(getattr(row,name) for name in STOCK_FIELDS)


def state(factory):
    with factory() as db:
        return [(row.id,balances(row),row.name,row.brand,row.cost_price,row.updated_at)
                for row in db.query(Item).order_by(Item.id)]


@pytest.mark.parametrize('field',STOCK_FIELDS)
def test_every_item_reader_preserves_null_and_group_sum_is_not_partial(stock_app,field):
    factory,client,_=stock_app
    with factory() as db:
        unknown=add(db,'Camisa P',missing=field,total=4,loja=3,deposito=1)
        known=add(db,'Camisa M',total=6,loja=4,deposito=2)
        suggestion=add(db,'Modelo P',group=None,missing=field)
        add(db,'Modelo M',group=None)
        uid,sid=str(unknown.id),str(suggestion.id);db.commit()
    before=state(factory)
    listed=client.get('/api/inventory/items')
    assert listed.status_code==200,listed.text
    row=next(r for r in listed.json()['items'] if r['id']==uid)
    assert row[field] is None and row['alert_level']=='unknown'
    for path in (f'/api/inventory/items/{uid}','/api/inventory/items/barcode/789001'):
        result=client.get(path);assert result.status_code==200,result.text
        data=result.json()
        if isinstance(data,list):data=next(r for r in data if r['id']==uid)
        assert data[field] is None and data['alert_level']=='unknown'
    groups=client.get('/api/inventory/groups');assert groups.status_code==200,groups.text
    group=groups.json()[0]
    assert len(group['items'])==2
    assert group['total_stock']==(None if field=='current_stock' else 10)
    assert next(r for r in group['items'] if r['id']==uid)[field] is None
    suggestions=client.get('/api/inventory/suggestions');assert suggestions.status_code==200,suggestions.text
    suggested=next(r for group in suggestions.json() for r in group['items'] if r['id']==sid)
    assert suggested[field] is None and suggested['alert_level']=='unknown'
    assert state(factory)==before
    with factory() as db:assert db.query(StockMovement).count()==0


def test_alerts_and_filters_keep_unknown_separate_from_zero_low_and_high(stock_app):
    factory,client,_=stock_app
    with factory() as db:
        add(db,'Missing total',group='Missing total',missing='current_stock')
        add(db,'Missing zero',group='Missing zero',missing='stock_loja',total=0,loja=0,deposito=0,minimum=3)
        add(db,'Missing low',group='Missing low',missing='stock_deposito',total=2,loja=2,deposito=0,minimum=5)
        add(db,'Missing high',group='Missing high',missing='stock_deposito',total=20,loja=20,deposito=0,maximum=10)
        inactive=add(db,'Inactive unknown',group='Inactive',missing='current_stock',active=False)
        assert _compute_alert_level(inactive)=='inactive'
        zero=add(db,'Zero',group='Zero',total=0,loja=0,deposito=0)
        assert _compute_alert_level(zero)=='out'
        low=add(db,'Low',group='Low',total=2,loja=2,deposito=0,minimum=3)
        assert _compute_alert_level(low)=='low'
        high=add(db,'High',group='High',total=20,loja=20,deposito=0,maximum=10)
        assert _compute_alert_level(high)=='high'
        normal=add(db,'No limits',group='Normal')
        assert _compute_alert_level(normal)=='ok'
        db.commit()
    before=state(factory)
    r=client.get('/api/inventory/alerts/summary');assert r.status_code==200,r.text
    counts=r.json()
    assert counts['unknown_stock_count']==4 and counts['total_active_items']==8
    assert counts['low_stock_count']==counts['out_of_stock_count']==counts['overstocked_count']==1
    assert counts['inactive_count']==1
    for status,names in [('unknown_stock',{'Missing total','Missing zero','Missing low','Missing high'}),
                         ('low_stock',{'Low'}),('out_of_stock',{'Zero'}),('overstocked',{'High'})]:
        result=client.get('/api/inventory/items',params={'status':status})
        assert result.status_code==200 and {r['name'] for r in result.json()['items']}==names
        assert result.json()['total']==len(names)
        groups=client.get('/api/inventory/groups',params={'status':status})
        assert groups.status_code==200 and {r['group_key'] for r in groups.json()}==names
    zero_group=client.get('/api/inventory/groups',params={'search':'Zero','status':'out_of_stock'}).json()
    assert zero_group[0]['total_stock']==0
    # Known physical location quantities can still be filtered without inferring the missing one.
    location=client.get('/api/inventory/items',params={'status':'unknown_stock','location_stock':'loja'}).json()
    assert {r['name'] for r in location['items']}=={'Missing total','Missing low','Missing high'}
    assert state(factory)==before


def test_unknown_group_filter_returns_all_variants_and_paginates_unknown_items(stock_app):
    factory,client,_=stock_app
    with factory() as db:
        add(db,'First',key=1,missing='current_stock',group='Mixed')
        add(db,'Second',key=2,group='Mixed')
        add(db,'Third',key=3,missing='stock_deposito',group='Other')
        db.commit()
    r=client.get('/api/inventory/groups',params={'status':'unknown_stock','search':'Mixed'})
    assert len(r.json())==1 and len(r.json()[0]['items'])==2 and r.json()[0]['total_stock'] is None
    first=client.get('/api/inventory/items',params={'status':'unknown_stock','page_size':1,'page':1}).json()
    second=client.get('/api/inventory/items',params={'status':'unknown_stock','page_size':1,'page':2}).json()
    assert first['total']==second['total']==2 and first['items'][0]['id']!=second['items'][0]['id']
    assert first['items'][0]['alert_level']==second['items'][0]['alert_level']=='unknown'


@pytest.mark.parametrize('field',STOCK_FIELDS)
def test_metadata_save_returns_unknown_and_does_not_repair_balance(stock_app,field):
    factory,client,user_id=stock_app
    with factory() as db:
        db.get(Usuario,user_id).role=UsuarioRole.GERENTE
        row=add(db,missing=field);uid=str(row.id);expected=balances(row);db.commit()
    response=client.put('/api/inventory/items/'+uid,json={'name':'camisa revisada','brand':'marca', 'min_stock':None,'max_stock':None})
    assert response.status_code==200,response.text
    assert response.json()['name']=='Camisa Revisada' and response.json()['alert_level']=='unknown'
    assert response.json()[field] is None and response.json()['min_stock'] is None
    batch=client.patch('/api/inventory/items/batch',json={'item_ids':[uid],'brand':'Nova marca'})
    assert batch.status_code==200,batch.text
    with factory() as db:
        row=db.get(Item,uuid.UUID(uid))
        assert balances(row)==expected and row.brand=='Nova Marca'
        assert db.query(StockMovement).count()==0


@pytest.mark.parametrize('field',STOCK_FIELDS)
@pytest.mark.parametrize('kind',['entry','exit','transfer','adjustment'])
def test_unknown_balance_blocks_every_movement_before_writes(stock_app,field,kind):
    factory,client,user_id=stock_app
    with factory() as db:
        row=add(db,missing=field);uid=row.id;expected=balances(row);db.commit()
    with factory() as db:
        with pytest.raises(StockMovementError) as raised:
            create_movement(db,uid,kind,0 if kind=='adjustment' else 1,user_id,unit_cost=20,
                            location='loja',location_from='loja',location_to='deposito')
        assert raised.value.status_code==409 and str(raised.value)==ERROR
        assert not db.new and not db.dirty and not db.deleted
        assert balances(db.get(Item,uid))==expected
        assert db.get(Item,uid).cost_price==Decimal('10.00')
    response=client.post('/api/inventory/movements',json={'item_id':str(uid),'movement_type':kind,
        'quantity':0 if kind=='adjustment' else 1,'unit_cost':'20','location':'loja','location_from':'loja','location_to':'deposito'})
    assert response.status_code==409 and response.json()['detail']==ERROR
    quick=client.post(f'/api/inventory/items/{uid}/quick-exit',json={'location':'loja'})
    assert quick.status_code==409
    with factory() as db:
        assert balances(db.get(Item,uid))==expected
        assert db.query(StockMovement).count()==0


@pytest.mark.parametrize('path', ['entry','transfer','metadata_and_movement'])
def test_unknown_second_item_rolls_back_entire_batch_including_metadata(stock_app,path):
    factory,client,_=stock_app
    with factory() as db:
        first=add(db,'Known first',key=1)
        second=add(db,'Unknown second',key=2,missing='stock_deposito')
        ids=[str(first.id),str(second.id)];db.commit()
    before=state(factory)
    if path=='entry':
        r=client.post('/api/inventory/movements/batch',json={'items':[{'item_id':uid,'quantity':1,'unit_cost':'20'} for uid in ids]})
    elif path=='transfer':
        r=client.post('/api/inventory/items/transfer-bulk',json={'direction':'loja_to_deposito','items':[{'item_id':uid,'quantity':1} for uid in ids]})
    else:
        r=client.patch('/api/inventory/items/batch',json={'item_ids':ids,'brand':'Do not persist','cost_price':'20','stock_delta':1,'stock_reason':'Teste'})
    assert r.status_code==409 and r.json()['detail']==ERROR
    assert state(factory)==before
    with factory() as db:assert db.query(StockMovement).count()==0


def test_known_zero_remains_valid_for_entry_and_zero_adjustment(stock_app):
    factory,client,user_id=stock_app
    with factory() as db:
        row=add(db,total=0,loja=0,deposito=0);uid=row.id;db.commit()
    for kind,quantity in [('adjustment',0),('entry',1)]:
        response=client.post('/api/inventory/movements',json={'item_id':str(uid),'movement_type':kind,'quantity':quantity,'location':'loja'})
        assert response.status_code==201,response.text
    with factory() as db:
        assert balances(db.get(Item,uid))==(1,1,0)
        assert db.query(StockMovement).count()==2
