from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg, upgrade
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, StockMovement, Supplier, InventorySession, InventorySessionItem
from app.models.pdv import PdvSale, PdvSaleItem, PdvCliente
from app.models.access import AuditEvent
from app.services.inventory_deletion import deletion_preview, delete_from_catalog
from app.services.inventory_service import create_movement, StockMovementError
from app.services.inventory_history import product_history
from app.schemas.inventory_deletion import ItemDeletionConfirmation


def test_catalog_deletion_migration_preserves_existing_data(pg):
    engine,schema=pg
    with engine.begin() as c:
        c.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        c.exec_driver_sql('CREATE TABLE usuarios(id uuid PRIMARY KEY)')
        c.exec_driver_sql('CREATE TABLE inventory_items(id uuid PRIMARY KEY, name text, is_active boolean, current_stock integer)')
        rid=uuid.uuid4()
        c.execute(sa.text('INSERT INTO inventory_items VALUES(:id,:name,true,5)'),{'id':rid,'name':'Existing'})
        upgrade(c,'f2a3b4c5d6e7_inventory_catalog_deletion.py')
        row=c.execute(sa.text('SELECT name,current_stock,deleted_at,deleted_by FROM inventory_items')).one()
        assert tuple(row)==('Existing',5,None,None)
        assert any(i['name']=='ix_inventory_items_deleted_at' for i in sa.inspect(c).get_indexes('inventory_items'))


def test_catalog_removal_serializes_with_stock_and_history_retains_links(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Item,Supplier,StockMovement,InventorySession,InventorySessionItem,PdvSale,PdvSaleItem,PdvCliente,AuditEvent)])
        factory=sessionmaker(bind=isolated,autoflush=False)
        with factory() as db:
            user=Usuario(nome='Lucas',email='lucas@eleven.com',senha_hash='unused',role=UsuarioRole.ADMIN)
            row=Item(name='Fixture',sku_internal='LOCAL-HISTORY',stock_loja=2,stock_deposito=0,current_stock=2)
            sale=PdvSale(status='completed')
            db.add_all([user,row,sale]);db.flush();uid,rid=user.id,row.id
            db.add(PdvSaleItem(sale_id=sale.id,item_id=row.id,item_name=row.name,item_sku=row.sku_internal,quantity=1,unit_price_gs=10,total_gs=10))
            db.commit()
        started=Event()
        def move():
            with factory() as db:
                db.get(Item,rid)  # loaded before the deletion commits
                started.set()
                create_movement(db,rid,'entry',1,uid);db.commit()
        with factory() as db, ThreadPoolExecutor(max_workers=1) as pool:
            user=db.get(Usuario,uid);preview=deletion_preview(db,rid,user)
            assert preview['blockers']==[{'code':'sales','count':1}]
            body=ItemDeletionConfirmation(sku=preview['item']['sku_internal'],plan_token=preview['preserve_history_token'],confirm=True)
            delete_from_catalog(db,rid,user,body)
            future=pool.submit(move);assert started.wait(5)
            try:
                with pytest.raises(TimeoutError): future.result(timeout=.2)
            finally: db.commit()
            with pytest.raises(StockMovementError): future.result(timeout=5)
        with factory() as db:
            data=product_history(db,rid,db.get(Usuario,uid),section='sales')
            assert data['total']==1 and data['product']['name'].startswith('Produto excluído')
            assert db.get(Item,rid).current_stock==2 and db.query(StockMovement).count()==0
    finally:isolated.dispose()
