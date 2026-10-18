"""Bulk editing uses synthetic products, no production database or images."""
import uuid
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app, item
from app.models.inventory import Item, StockMovement
from app.services.inventory_service import create_movement


def seed(factory, count=2):
    with factory() as db:
        ids = [str(item(db, loja=3, deposito=2, color='Branca').id) for _ in range(count)]
        db.commit()
    return ids


def adjustment(identity, **changes):
    return dict(id=identity, stock_loja=4, stock_deposito=2, expected_loja=3,
                expected_deposito=2, expected_total=5, **changes)


def test_final_quantities_color_and_optional_reasons_are_atomic_and_recorded(stock_app):
    factory, client, user_id = stock_app
    first, second = seed(factory)
    a = adjustment(first); a.update(stock_loja=0)
    b = adjustment(second); b.update(stock_deposito=8, reason='Conferência recebimento')
    payload = {'item_ids':[first,second], 'sizes':[{'id':first,'color':'NAVY'},{'id':second,'color':'Navy'}],
               'stock_adjustments':[a,b]}
    response = client.patch('/api/inventory/items/batch/quantities', json=payload)
    assert response.status_code == 200, response.text
    with factory() as db:
        one, two = db.get(Item,uuid.UUID(first)), db.get(Item,uuid.UUID(second))
        assert (one.stock_loja,one.stock_deposito,one.current_stock)==(0,2,2)
        assert (two.stock_loja,two.stock_deposito,two.current_stock)==(4,8,12)
        assert one.color == two.color == 'Navy'
        moves=db.query(StockMovement).all()
        assert len(moves)==3
        assert all(m.created_by==user_id and m.movement_type.value=='adjustment' for m in moves)
        assert {m.reason for m in moves}=={'Conferência de estoque — edição em lote','Conferência recebimento'}
    # A repeated request with stale baselines cannot apply a second adjustment.
    assert client.patch('/api/inventory/items/batch/quantities',json=payload).status_code==409
    with factory() as db: assert db.query(StockMovement).count()==3


def test_sale_or_transfer_since_preview_rejects_entire_batch_including_metadata(stock_app):
    factory,client,user_id=stock_app
    ids=seed(factory)
    with factory() as db:
        create_movement(db,uuid.UUID(ids[1]),'transfer',1,user_id,location_from='loja',location_to='deposito')
        db.commit()
    response=client.patch('/api/inventory/items/batch/quantities',json={
        'item_ids':ids,'brand':'Must not persist','stock_adjustments':[adjustment(i) for i in ids]})
    assert response.status_code==409
    with factory() as db:
        rows=[db.get(Item,uuid.UUID(i)) for i in ids]
        assert all(row.brand is None for row in rows)
        assert (rows[0].stock_loja,rows[1].stock_loja)==(3,2)
        assert db.query(StockMovement).count()==1


@pytest.mark.parametrize('invalid',[-1,1.5,True,2147483648,None])
def test_invalid_quantities_fail_without_partial_changes(stock_app,invalid):
    factory,client,_=stock_app
    ids=seed(factory)
    bad=adjustment(ids[1]);bad['stock_loja']=invalid
    response=client.patch('/api/inventory/items/batch/quantities',json={'item_ids':ids,'brand':'No change','stock_adjustments':[adjustment(ids[0]),bad]})
    assert response.status_code==422
    with factory() as db:
        assert db.query(StockMovement).count()==0
        assert all(row.stock_loja==3 and row.brand is None for row in db.query(Item).all())


@pytest.mark.parametrize('kind',['duplicate','outside','missing','mixed','unknown'])
def test_selection_and_stock_conflicts_never_partially_save(stock_app,kind):
    factory,client,_=stock_app
    ids=seed(factory)
    payload={'item_ids':ids,'sizes':[{'id':ids[0],'color':'Black'}],'stock_adjustments':[adjustment(i) for i in ids]}
    status=422
    if kind=='duplicate': payload['stock_adjustments'].append(adjustment(ids[0]))
    if kind=='outside': payload['sizes'].append({'id':str(uuid.uuid4()),'name':'Outside selection'})
    if kind=='missing': payload['item_ids'].append(str(uuid.uuid4()));status=409
    if kind=='mixed': payload['stock_delta']=1
    if kind=='unknown':
        with factory() as db:
            db.get(Item,uuid.UUID(ids[1])).stock_loja=None;db.commit()
        status=409
    assert client.patch('/api/inventory/items/batch/quantities',json=payload).status_code==status
    with factory() as db:
        assert db.query(StockMovement).count()==0
        assert db.get(Item,uuid.UUID(ids[0])).color=='Branca'


def test_legacy_delta_accepts_no_reason_and_zero_override(stock_app):
    factory,client,user_id=stock_app
    ids=seed(factory)
    response=client.patch('/api/inventory/items/batch',json={'item_ids':ids,'stock_delta':2,
        'sizes':[{'id':ids[0],'stock_delta':0},{'id':ids[1],'stock_delta':1,'stock_reason':'   '}]})
    assert response.status_code==200,response.text
    with factory() as db:
        assert db.get(Item,uuid.UUID(ids[0])).stock_loja==3
        assert db.get(Item,uuid.UUID(ids[1])).stock_loja==4
        movement=db.query(StockMovement).one()
        assert movement.created_by==user_id and movement.reason=='Ajuste de estoque — edição em lote'


def test_unchanged_quantities_create_no_artificial_movements(stock_app):
    factory,client,_=stock_app
    ids=seed(factory,1);a=adjustment(ids[0]);a['stock_loja']=3
    assert client.patch('/api/inventory/items/batch/quantities',json={'item_ids':ids,'stock_adjustments':[a]}).status_code==200
    with factory() as db: assert db.query(StockMovement).count()==0


def test_failure_during_second_adjustment_rolls_back_first_and_metadata(stock_app, monkeypatch):
    from app.api.endpoints import inventory
    from app.services.inventory_service import StockMovementError
    factory,client,_=stock_app
    ids=seed(factory)
    original=inventory.create_movement
    calls=[]
    def movement(**kwargs):
        calls.append(kwargs['item_id'])
        if len(calls)==2:
            raise StockMovementError('Fixture: concurrent stock validation failure',409)
        return original(**kwargs)
    monkeypatch.setattr(inventory,'create_movement',movement)
    response=client.patch('/api/inventory/items/batch/quantities',json={
        'item_ids':ids,'brand':'Do not save','stock_adjustments':[adjustment(i) for i in ids]})
    assert response.status_code==409 and len(calls)==2
    with factory() as db:
        assert db.query(StockMovement).count()==0
        assert all(row.stock_loja==3 and row.brand is None for row in db.query(Item).all())
