from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, joinedload
from test_access_postgres import pg, upgrade
from app.database import Base
from app.models import Usuario, Vendedor, Cliente
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, StockMovement, Supplier, InventorySession, InventorySessionItem
from app.models.pdv import PdvSale, PdvSaleItem, PdvCliente
from app.models.access import AuditEvent
from app.services.inventory_deletion import deletion_preview, delete_from_catalog
from app.services.inventory_service import create_movement, StockMovementError
from app.services.inventory_history import product_history
from app.services.inventory_movement_visibility import movement_read_responses
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
        Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Cliente,Item,Supplier,StockMovement,InventorySession,InventorySessionItem,PdvSale,PdvSaleItem,PdvCliente,AuditEvent)])
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


def test_movement_visibility_normalizes_native_postgres_uuids_without_rewriting_rows(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[model.__table__ for model in (
            Usuario, Vendedor, Cliente, Item, Supplier, StockMovement, PdvSale, PdvCliente,
        )])
        factory = sessionmaker(bind=isolated, autoflush=False)
        with factory() as db:
            owner = Usuario(nome='Lucas', email='lucas@eleven.com', senha_hash='unused', role=UsuarioRole.ADMIN)
            manager = Usuario(nome='Wissam', email='wissam@eleven.com', senha_hash='unused', role=UsuarioRole.GERENTE)
            seller = Usuario(nome='Denis', email='denis@eleven.com', senha_hash='unused', sales_scope='own')
            product = Item(name='Fixture', sku_internal='LOCAL-MOVEMENT-READ', current_stock=3, stock_loja=3, stock_deposito=0)
            db.add_all([owner, manager, seller, product]); db.flush()
            own = PdvSale(vendedor_id=seller.id)
            other = PdvSale(vendedor_id=manager.id)
            deleted = PdvSale(vendedor_id=seller.id, deleted_at=datetime(2026, 10, 14, tzinfo=timezone.utc))
            db.add_all([own, other, deleted]); db.flush()
            refs = {
                'hex': own.id.hex, 'upper': str(own.id).upper(), 'other': other.id.hex,
                'deleted': str(deleted.id).upper(), 'invalid': 'not-a-uuid',
                'missing': uuid.uuid4().hex, 'manual': 'manual-reference',
            }
            for kind, reference in refs.items():
                db.add(StockMovement(item_id=product.id, movement_type='entry', quantity=1,
                                     quantity_before=2, quantity_after=3, location_from='loja',
                                     reference_type='manual' if kind == 'manual' else 'pdv_sale',
                                     reference_id=reference, reason=kind, notes='fixture note',
                                     created_by=manager.id, unit_cost=Decimal('12.34')))
            profiles = [(owner.id, set()), (manager.id, {'deleted', 'invalid', 'missing'}),
                        (seller.id, {'other', 'deleted', 'invalid', 'missing'})]
            db.commit()
        with factory() as db:
            rows = db.query(StockMovement).options(joinedload(StockMovement.item)).all()
            kinds = {row.id: row.reason for row in rows}
            for uid, denied in profiles:
                responses = movement_read_responses(db, rows, db.get(Usuario, uid))
                assert not db.dirty
                for response in responses:
                    kind = kinds[response.id]
                    assert response.quantity == 1 and response.quantity_before == 2 and response.quantity_after == 3
                    assert response.reference_id == (None if kind in denied else refs[kind])
                    assert response.unit_cost == (None if kind in denied else Decimal('12.34'))
                    assert response.reason == (None if kind in denied else kind)
            for row in rows:
                assert row.reference_id == refs[kinds[row.id]] and row.unit_cost == Decimal('12.34')
                assert row.notes == 'fixture note' and row.created_by is not None
    finally:
        isolated.dispose()
