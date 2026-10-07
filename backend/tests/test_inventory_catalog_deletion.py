import uuid
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app, item
from test_inventory_history import history_app, sale, get
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, StockMovement
from app.models.pdv import PdvSale, PdvSaleItem
from app.models.access import AuditEvent
from app.services.assistant_queries import query_stock, StockArgs
from test_pdv_unknown_stock import pdv_app, make_item, sale_payload, balances
from app.config import settings
from app.models.pdv import PdvPayment, PdvFiadoMovement


def prepare(client,rid):
    preview=client.get(f'/api/inventory/items/{rid}/deletion-preview').json()
    return {'sku':preview['item']['sku_internal'],'confirm':True,'plan_token':preview['preserve_history_token']}


def test_linked_product_removed_from_every_catalog_but_sales_movements_and_history_remain(history_app):
    factory,client,uid,rid=history_app
    with factory() as db:
        row=db.get(Item,rid); sku=row.sku_internal
        s=sale(db,row,uid); sid=s.id
        db.add(StockMovement(item_id=rid,movement_type='exit',quantity=1,quantity_before=1,quantity_after=0,
                             reference_type='pdv_sale',reference_id=str(sid),created_by=uid))
        other=item(db,barcode=row.barcode);other_id=other.id
        db.commit()
    body=prepare(client,rid)
    result=client.post(f'/api/inventory/items/{rid}/delete-from-catalog',json=body)
    assert result.status_code==200 and result.json()['history_preserved']
    for params in ({},{'alert_level':'inactive'},{'search':sku}):
        assert str(rid) not in str(client.get('/api/inventory/items',params=params).json())
    assert client.get(f'/api/inventory/items/{rid}').status_code==404
    assert client.put(f'/api/inventory/items/{rid}',json={'is_active':True}).status_code==404
    assert client.post('/api/inventory/movements',json={'item_id':str(rid),'movement_type':'entry','quantity':1}).status_code==409
    assert client.post(f'/api/inventory/items/{rid}/quick-exit').status_code==409
    assert client.post(f'/api/inventory/items/{rid}/delete-from-catalog',json=body).status_code==404
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json=body).status_code==404
    history=get(client,rid,'sales')
    assert history['product']['name']=='Produto excluído — Camiseta' and history['product']['deleted_by']=='Lucas'
    assert history['rows'][0]['id']==str(sid) and history['rows'][0]['lines'][0]['name'].startswith('Produto excluído')
    deleted=client.get('/api/inventory/items/deleted-history',params={'q':sku}).json()
    assert deleted['total']==1 and deleted['items'][0]['id']==str(rid)
    assert client.get(f'/api/inventory/movements/item/{rid}').json()[0]['item_name'].startswith('Produto excluído')
    with factory() as db:
        row=db.get(Item,rid)
        assert row.name=='Camiseta' and row.deleted_at and not row.is_active and row.image_data is None
        assert row.current_stock==2 and db.get(Item,other_id).deleted_at is None
        assert db.query(PdvSaleItem).count()==1 and db.get(PdvSale,sid).status=='completed'
        assert db.query(StockMovement).count()==1 and db.query(AuditEvent).filter_by(action='item_catalog_deleted').count()==1
        assert str(rid) not in str(query_stock(db,StockArgs(termo=sku)))


@pytest.mark.parametrize('change',['sku','token','stock','user','sale_link'])
def test_catalog_removal_requires_owner_and_fresh_review(history_app,change):
    factory,client,uid,rid=history_app
    body=prepare(client,rid)
    if change=='sku': body['sku']='WRONG'
    elif change=='token':body['plan_token']='f'*64
    else:
        with factory() as db:
            if change=='stock': db.get(Item,rid).current_stock=7
            elif change=='user':
                db.get(Usuario,uid).role=UsuarioRole.GERENTE
            else: sale(db, db.get(Item,rid), uid, legacy=True)
            db.commit()
    assert client.post(f'/api/inventory/items/{rid}/delete-from-catalog',json=body).status_code in (403,409)
    with factory() as db: assert db.get(Item,rid).deleted_at is None
    if change=='user': assert client.get('/api/inventory/items/deleted-history').status_code==403


@pytest.mark.parametrize('legacy', [False, True])
def test_pdv_history_labels_deleted_product_without_changing_sale_snapshot(pdv_app, legacy):
    factory, client, customer_id = pdv_app
    with factory() as db:
        row = make_item(db); rid = row.id; sku = row.sku_internal
        db.commit()
    result = client.post('/api/pdv/sales', json=sale_payload([rid], customer_id))
    assert result.status_code == 201, result.text
    sid = result.json()['id']
    with factory() as db:
        row = db.get(Item, rid); row.deleted_at = settings.now(); row.is_active = False
        line = db.query(PdvSaleItem).one(); line.item_sku = sku
        if legacy: line.item_id = None
        db.commit()
    response = client.get(f'/api/pdv/sales/{sid}')
    assert response.status_code == 200
    assert response.json()['items'][0]['item_name'] == 'Produto excluído — Produto sintético'
    assert response.json()['total_gs'] == 100
    with factory() as db:
        assert db.query(PdvSaleItem).one().item_name == 'Produto sintético'


def test_deleted_product_cannot_be_sold_or_returned_to_catalog_through_cancellation(pdv_app):
    factory, client, customer_id = pdv_app
    with factory() as db:
        rid = make_item(db).id; db.commit()
    result = client.post('/api/pdv/sales', json=sale_payload([rid], customer_id))
    assert result.status_code == 201, result.text
    sid = uuid.UUID(result.json()['id'])
    with factory() as db:
        row = db.get(Item, rid); row.deleted_at = settings.now(); row.is_active = False
        db.commit(); before = balances(db, rid)
    assert client.post(f'/api/pdv/sales/{sid}/cancel').status_code == 409
    assert client.post('/api/pdv/sales', json=sale_payload([rid], customer_id)).status_code == 409
    with factory() as db:
        assert balances(db, rid) == before
        assert db.get(PdvSale, sid).status == 'completed' and db.get(PdvSale, sid).stock_applied
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == db.query(PdvFiadoMovement).count() == 1
        assert db.query(StockMovement).count() == 1
