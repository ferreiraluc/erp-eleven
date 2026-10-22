"""Bulk editing uses synthetic products, no production database or images."""
import uuid
import re
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app, item
from test_product_intake_grade import manager_stock_app
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


def test_bulk_all_details_override_clear_and_keep_legacy_identity(manager_stock_app):
    factory, client, user_id = manager_stock_app
    ids = seed(factory)
    from app.models.inventory import Supplier
    with factory() as db:
        supplier = Supplier(name='Fornecedor teste'); db.add(supplier); db.flush(); supplier_id=str(supplier.id)
        db.get(Item, uuid.UUID(ids[0])).size = 'S'
        db.get(Item, uuid.UUID(ids[1])).size = 'M'
        db.flush()
        versions = {identity: db.get(Item, uuid.UUID(identity)).updated_at.isoformat() for identity in ids}
        before = [(db.get(Item,uuid.UUID(i)).sku_internal, db.get(Item,uuid.UUID(i)).inventory_code) for i in ids]
        db.commit()
    response = client.patch('/api/inventory/items/batch/details', json={
        'item_ids': ids, 'description': 'Placa de metal', 'brand': 'PRADA', 'category': 'Camisetas',
        'unit': 'peça', 'location': 'A3', 'supplier_id': supplier_id, 'group_key': 'Família teste',
        'cost_currency': 'USD', 'sale_currency': 'BRL', 'currency': 'USD', 'min_stock': 2, 'max_stock': 8,
        'is_active': False, 'cost_price': 12.25, 'sale_price': 90,
        'sizes': [{'id':ids[0], 'expected_updated_at':versions[ids[0]],
                   'description':'Logo emborrachado', 'barcode':'00123S'},
                  {'id':ids[1], 'expected_updated_at':versions[ids[1]],
                   'supplier_id':None, 'location':'', 'barcode':'00123M'}]})
    assert response.status_code == 200, response.text
    with factory() as db:
        rows=[db.get(Item,uuid.UUID(i)) for i in ids]
        assert [r.description for r in rows] == ['Logo emborrachado','Placa de metal']
        assert [r.barcode for r in rows] == ['00123S','00123M']
        assert rows[0].supplier_id == uuid.UUID(supplier_id) and rows[1].supplier_id is None
        assert rows[1].location == ''
        assert all(r.brand == 'Prada' and r.min_stock == 2 and r.max_stock == 8 and not r.is_active for r in rows)
        assert all(r.cost_currency == 'USD' and r.sale_currency == 'BRL' and r.unit == 'peça' for r in rows)
        assert [(r.sku_internal,r.inventory_code) for r in rows] == before
        assert all(r.current_stock == 5 for r in rows)
        assert db.query(StockMovement).count() == 0
    response=client.patch('/api/inventory/items/batch/details',json={'item_ids':ids,'description':None})
    assert response.status_code==200
    with factory() as db: assert all(db.get(Item,uuid.UUID(i)).description is None for i in ids)


@pytest.mark.parametrize('patch',[{'unit':' '},{'name':''},{'brand':'x'*101},{'cost_price':-1},
    {'sale_currency':'XYZ'},{'min_stock':1.5},{'min_stock':8,'max_stock':2},{'supplier_id':str(uuid.uuid4())}])
def test_invalid_bulk_details_roll_back_entire_selection(stock_app,patch):
    factory,client,_=stock_app
    ids=seed(factory)
    response=client.patch('/api/inventory/items/batch/details',json={'item_ids':ids,'description':'Must not persist',**patch})
    assert response.status_code==422,response.text
    with factory() as db: assert all(db.get(Item,uuid.UUID(i)).description is None for i in ids)


def test_stale_description_preview_is_rejected_atomically(stock_app):
    factory,client,_=stock_app
    ids=seed(factory)
    with factory() as db:
        row=db.get(Item,uuid.UUID(ids[1])); timestamp=row.updated_at.isoformat()
        row.description='Editado por outro usuário';db.commit()
    response=client.patch('/api/inventory/items/batch/details',json={'item_ids':ids,'description':'Old preview',
        'sizes':[{'id':ids[1],'expected_updated_at':timestamp}]})
    assert response.status_code==409,response.text
    with factory() as db:
        assert db.get(Item,uuid.UUID(ids[0])).description is None
        assert db.get(Item,uuid.UUID(ids[1])).description=='Editado por outro usuário'


def test_new_short_reference_and_old_sku_both_find_the_product(stock_app):
    factory,client,_=stock_app
    identity=seed(factory,1)[0]
    with factory() as db:
        row=db.get(Item,uuid.UUID(identity));code,sku=row.inventory_code,row.sku_internal
    assert re.fullmatch(r'INV-[A-Z2-9]{6}',code)
    for value in [code,code.lower(),sku]:
        result=client.get('/api/inventory/items',params={'search':value})
        assert result.status_code==200,result.text
        assert any(i['id']==identity for i in result.json()['items'])
