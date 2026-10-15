import uuid
import sqlalchemy as sa
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app
from test_product_intake_grade import manager_stock_app
from test_access_postgres import pg, upgrade
from app.models.inventory import Item
from app.schemas.inventory import GradeCreateRequest
from app.services.inventory_taxonomy_v2 import canonical, canonical_size


@pytest.mark.parametrize('brand', ['DG', 'D&G', 'DolceGabbana', 'Dolce&Gabbana', 'dolce gabbana'])
def test_dg_aliases(brand):
    assert canonical(brand, 'brand') == 'Dolce & Gabbana'


@pytest.mark.parametrize('size,expected', [('P','S'), ('s','S'), ('G','L'), ('GG','XL'), ('XXL','2XL'), ('11.5 US','11.5 US'), ('40','40')])
def test_size_aliases_do_not_convert_shoe_scales(size, expected):
    assert canonical_size(size) == expected


def test_search_aliases_and_common_typos_preserve_literal_model_codes(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        db.add_all([Item(name='T-shirt DN0281 G', sku_internal='ALIAS-1', size='G', brand='DolceGabbana', current_stock=2),
                    Item(name='Camiseta P', sku_internal='ALIAS-2', size='P', brand='DG', current_stock=3),
                    Item(name='Camisa', sku_internal='ALIAS-3', size='GG', brand='Boss', current_stock=1)])
        db.commit()
        item=db.query(Item).filter_by(sku_internal='ALIAS-1').one()
        assert (item.name,item.size,item.brand)==('T-shirt DN0281 L','L','Dolce & Gabbana')
        # Old rows still match before the data migration and keep their barcode.
        db.execute(sa.text("UPDATE inventory_items SET size='G', brand='Dolce&Gabbana', barcode='LEGACYG' WHERE sku_internal='ALIAS-1'")); db.commit()
    for search in ['tsirt G', 'camseta L', 'camiseta DG G', 'T-shirt DolceGabbana L', 'DN0281 G', 'LEGACYG']:
        result=client.get('/api/inventory/items',params={'search':search}).json()
        assert [r['sku_internal'] for r in result['items']]==['ALIAS-1'],search
    assert client.get('/api/inventory/items',params={'search':'DN0282 G'}).json()['total']==0
    assert client.get('/api/inventory/items',params={'size':'L','brand':'DG'}).json()['total']==1
    assert client.get('/api/inventory/items',params={'search':'camseta P'}).json()['total']==1
    assert client.get('/api/inventory/items',params={'search':'camisa XL'}).json()['total']==1
    assert client.get('/api/inventory/items/distinct-values').json()['brands']==['Boss','Dolce & Gabbana']


def test_grade_aliases_deduplicate_and_keep_quantity_explicit():
    request=GradeCreateRequest(name='Camiseta',sizes=['P','S','G','L','XXL'], stock_by_size={'P':3,'G':4,'XXL':8})
    assert request.sizes==['S','L','2XL']
    assert request.stock_by_size=={'S':3,'L':4,'2XL':8}
    with pytest.raises(ValueError):
        GradeCreateRequest(name='Camiseta',sizes=['P','S'],stock_by_size={'P':3,'S':8})


def test_postgres_catalog_backfill_preserves_identities_conflicting_variants_and_history(pg):
    engine,schema=pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE inventory_items (id uuid PRIMARY KEY, name text, size text, brand text, deleted_at timestamp, current_stock int, barcode text, group_key text, updated_at timestamp)')
        ids=[uuid.uuid4() for _ in range(503)]
        for n,item_id in enumerate(ids):
            conn.execute(sa.text("INSERT INTO inventory_items VALUES (:id,:name,:size,:brand,:deleted,3,:barcode,'same-group','2025-01-01')"),dict(id=item_id,name='T-shirt DN0281 P',size='P' if n%2==0 else 'S',brand='DolceGabbana',deleted='2025-01-02' if n==502 else None,barcode=f'OLD-{n}P'))
        before=conn.execute(sa.text('SELECT id,current_stock,barcode,group_key,updated_at FROM inventory_items ORDER BY id')).all()
        upgrade(conn,'i1d2e3f4a5b6_catalog_brand_size_aliases.py')
        assert conn.execute(sa.text('SELECT id,current_stock,barcode,group_key,updated_at FROM inventory_items ORDER BY id')).all()==before
        assert conn.execute(sa.text('SELECT DISTINCT size,brand FROM inventory_items WHERE deleted_at IS NULL')).all()==[('S','Dolce & Gabbana')]
        assert conn.execute(sa.text('SELECT count(*) FROM inventory_catalog_snapshot_v2')).scalar()==502
        assert conn.execute(sa.text('SELECT size FROM inventory_items WHERE deleted_at IS NOT NULL')).scalar()=='P'
        snapshot=conn.execute(sa.text('SELECT "before", "after" FROM inventory_catalog_snapshot_v2 WHERE item_id=:id'),dict(id=str(ids[0]))).one()
        assert snapshot.before['name']=='T-shirt DN0281 P'
        assert snapshot.after['name']=='T-shirt DN0281 S'


def test_existing_grade_does_not_recreate_p_as_s_or_repeat_stock(manager_stock_app):
    factory, client, _ = manager_stock_app
    with factory() as db:
        row=Item(name='Camiseta S',sku_internal='KEEP-S',size='S',group_key='same',color='Branco',current_stock=3,stock_loja=3,stock_deposito=0)
        db.add(row); db.commit(); identity=str(row.id)
    context=client.get(f'/api/inventory/items/{identity}/variants').json()
    result=client.post(f'/api/inventory/items/{identity}/variants',json=dict(sizes=['P','S'],model_name='Camiseta',source_version=context['source_version'],initial_stock=8,confirm=True))
    assert result.status_code==201,result.text
    assert result.json()['created']==[]
    assert [r['id'] for r in result.json()['existing']]==[identity]
    with factory() as db:
        assert db.query(Item).count()==1
        assert db.get(Item,uuid.UUID(identity)).current_stock==3
