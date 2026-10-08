import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor, Cliente
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, Supplier, StockMovement, InventorySession, InventorySessionItem
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem
from app.models.access import AuditEvent
from app.services.inventory_deletion import deletion_preview, permanently_delete_item
from app.schemas.inventory_deletion import ItemDeletionConfirmation


def test_deletion_rolls_back_and_serializes_with_concurrent_sale_reference(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Cliente,Item,Supplier,StockMovement,
            InventorySession,InventorySessionItem,PdvCliente,PdvSale,PdvSaleItem,AuditEvent)])
        factory = sessionmaker(bind=isolated,autoflush=False)
        with factory() as db:
            user = Usuario(nome='Lucas',email='lucas@eleven.com',senha_hash='unused',role=UsuarioRole.ADMIN)
            row = Item(name='Test only',sku_internal='LOCAL-DELETE')
            sale = PdvSale(status='completed')
            db.add_all([user,row,sale]);db.flush()
            uid,rid,sid=user.id,row.id,sale.id;db.commit()
        with factory() as db:
            body=ItemDeletionConfirmation(sku='LOCAL-DELETE',plan_token=deletion_preview(db,rid,db.get(Usuario,uid))['plan_token'],confirm=True)
            permanently_delete_item(db,rid,db.get(Usuario,uid),body);db.rollback()
            assert db.get(Item,rid) is not None and db.query(AuditEvent).count()==0
        started=Event()
        def link():
            with factory() as db:
                db.add(PdvSaleItem(sale_id=sid,item_id=rid,item_name='Test only',unit_price_gs=1,total_gs=1))
                started.set();db.commit()
        with factory() as db, ThreadPoolExecutor(max_workers=1) as pool:
            permanently_delete_item(db,rid,db.get(Usuario,uid),body)
            future=pool.submit(link)
            assert started.wait(5)
            try:
                with pytest.raises(TimeoutError): future.result(timeout=.2)
            finally:
                db.commit()  # release FK waiter, even if the assertion fails
            with pytest.raises(sa.exc.IntegrityError): future.result(timeout=5)
        with factory() as db:
            assert db.get(Item,rid) is None and db.query(PdvSaleItem).count()==0
            assert db.query(AuditEvent).filter_by(action='item_permanently_deleted').count()==1
    finally: isolated.dispose()
