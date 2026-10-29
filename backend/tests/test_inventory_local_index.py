"""The device index exports a bounded, read-only catalog, never private fields/stock/photos."""
import uuid
from sqlalchemy import event
from app.models.inventory import Item
from test_inventory_ocr import stock_app
from test_assistant import setup


def test_keyset_index_is_complete_and_does_not_read_photo_or_cost_columns(stock_app):
    factory, client, _ = stock_app
    with factory() as db:
        for i in range(7):
            db.add(Item(id=uuid.UUID('a0000000-0000-0000-0000-'+str(i+1).zfill(12)),sku_internal=f'LOCAL-{i}',name=f'Peça {i}',
                description='keyword '+('x'*2000),sale_price=80,stock_loja=9,
                cost_price=17,image_data='original-private-image',additional_images=['private-gallery']))
        db.commit()
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany): statements.append(statement)
    engine=factory.kw['bind'];event.listen(engine,'before_cursor_execute',capture)
    try:
        cursor=None;found=[]
        while True:
            params={'limit':3,**({'after_id':cursor} if cursor else {})}
            response=client.get('/api/inventory/search-index',params=params)
            assert response.status_code==200,response.text
            result=response.json();found.extend(result['items']);cursor=result['next_cursor']
            if not cursor:break
    finally:event.remove(engine,'before_cursor_execute',capture)
    assert [row['sku_internal'] for row in found]==[f'LOCAL-{i}' for i in range(7)]
    assert len(found[0]['description'])==512 and found[0]['has_image']
    assert not {'cost_price','stock_loja','stock_deposito','current_stock','image_data','additional_images','supplier_id','created_by'}.intersection(found[0])
    reads=[statement.lower() for statement in statements if 'inventory_items' in statement and 'select' in statement.lower()]
    assert all('cost_price' not in sql and 'additional_images' not in sql and 'current_stock' not in sql for sql in reads)
    assert all('image_data as' not in sql and 'count(' not in sql for sql in reads)
    assert client.get('/api/inventory/search-index?limit=501').status_code==422
    assert client.get('/api/inventory/search-index?after_id=invalid').status_code==422
    detail=client.get('/api/inventory/items/'+found[0]['id'],params={'include_images':False}).json()
    assert detail['image_data'] is None and detail['stock_loja']==9 and detail['has_image']


def test_mistyped_model_letter_is_a_suggestion_but_never_a_different_qr_or_numeric_model(stock_app):
    factory,client,_=stock_app
    with factory() as db:
        for code in ('1JRGZ','1HRGZ','1JRZZ','2JRGZ'):
            db.add(Item(name='Camiseta '+code,sku_internal=code))
        db.commit()
    result=client.get('/api/inventory/items',params={'search':'1HRGZ','include_images':False}).json()
    assert [row['sku_internal'] for row in result['items']]==['1HRGZ','1JRGZ']
    assert not client.get('/api/inventory/items',params={'search':'INV-1HRGZ9'}).json()['items']
