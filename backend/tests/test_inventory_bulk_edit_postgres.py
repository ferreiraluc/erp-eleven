"""Real row-lock validation in a disposable PostgreSQL schema only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from test_access_postgres import pg
from app.database import Base
from app.models import Usuario, Vendedor
from app.models.inventory import Item, Supplier, StockMovement
from app.schemas.inventory import BatchEditRequest
from app.api.endpoints.inventory import batch_edit_items
from test_inventory_ocr import picture


def test_two_preloaded_bulk_previews_cannot_overwrite_each_other(pg):
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Supplier,Item,StockMovement)])
        factory=sessionmaker(bind=isolated,autoflush=False)
        user_id,item_id=uuid.uuid4(),uuid.uuid4()
        with factory() as db:
            db.add(Usuario(id=user_id,nome='Fixture',email='bulk@fixture.local',senha_hash='unused'))
            db.flush()
            db.add(Item(id=item_id,name='Camiseta S',sku_internal='LOCAL-BULK',current_stock=5,stock_loja=3,stock_deposito=2))
            db.commit()
        ready=Barrier(2)
        def edit(quantity):
            with factory() as db:
                preloaded=db.get(Item,item_id)
                assert preloaded.stock_loja==3
                ready.wait(timeout=10)
                request=BatchEditRequest(item_ids=[item_id],brand=f'Winner {quantity}',stock_adjustments=[{
                    'id':item_id,'stock_loja':quantity,'stock_deposito':2,'expected_loja':3,'expected_deposito':2,'expected_total':5}])
                try:
                    batch_edit_items(request,db,SimpleNamespace(id=user_id))
                    return 200,quantity
                except HTTPException as error:
                    db.rollback()
                    return error.status_code,quantity
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(edit,[6,8]))
        assert sorted(status for status,_ in results)==[200,409]
        winner=next(quantity for status,quantity in results if status==200)
        with factory() as db:
            row=db.get(Item,item_id)
            assert (row.stock_loja,row.stock_deposito,row.current_stock)==(winner,2,winner+2)
            assert row.brand==f'Winner {winner}'
            movement=db.query(StockMovement).one()
            assert (movement.quantity_before,movement.quantity_after,movement.created_by)==(5,winner+2,user_id)
    finally:
        isolated.dispose()


def test_photo_groups_wait_for_locks_and_preserve_concurrent_gallery_edit(pg):
    from threading import Event
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    started = Event()
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item, StockMovement)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        ids = [uuid.uuid4(), uuid.uuid4()]
        cover, extra = picture('JPEG', (200, 120)), picture('JPEG', (210, 130))
        with factory() as db:
            db.add_all([Item(id=identity, name='Bege M', sku_internal=str(identity), current_stock=0,
                             stock_loja=0, stock_deposito=0, image_data='original') for identity in ids])
            db.commit()
        # A separate editor holds the product while updating only its gallery.
        with factory() as gallery:
            row = gallery.query(Item).filter(Item.id == ids[0]).with_for_update().one()
            row.additional_images = [extra]
            def replace():
                with factory() as db:
                    started.set()
                    batch_edit_items(BatchEditRequest(item_ids=ids, image_groups=[{
                        'item_ids': ids, 'image_data': cover}]), db, SimpleNamespace(id=uuid.uuid4()))
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(replace)
                try:
                    assert started.wait(timeout=5)
                    with pytest.raises(TimeoutError):
                        future.result(timeout=0.2)
                finally:
                    gallery.commit()
                future.result(timeout=10)
        with factory() as db:
            assert all(db.get(Item, identity).image_data == cover for identity in ids)
            assert db.get(Item, ids[0]).additional_images == [extra]
            assert db.get(Item, ids[1]).additional_images is None
            assert all(db.get(Item, identity).thumbnail_ready is False for identity in ids)
            assert db.query(StockMovement).count() == 0
    finally:
        isolated.dispose()


def test_concurrent_gallery_additions_respect_five_photo_limit_and_roll_back_metadata(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item, StockMovement)])
        factory = sessionmaker(bind=isolated, autoflush=False)
        item_id = uuid.uuid4()
        cover, extra = picture('JPEG', (225, 120)), picture('JPEG', (226, 120))
        with factory() as db:
            db.add(Item(id=item_id, name='Branco S', sku_internal=str(item_id), image_data=cover,
                        additional_images=[extra] * 3, current_stock=0, stock_loja=0, stock_deposito=0))
            db.commit()
        ready = Barrier(2)
        def append(width):
            photo = picture('JPEG', (width, 120))
            with factory() as db:
                # A stale ORM identity must not bypass the locked current gallery count.
                db.get(Item, item_id)
                ready.wait(timeout=10)
                try:
                    batch_edit_items(BatchEditRequest(item_ids=[item_id], description=f'Winner {width}', image_groups=[{
                        'item_ids': [item_id], 'image_data': photo, 'operation': 'add'}]), db, SimpleNamespace(id=uuid.uuid4()))
                    return 200, width, photo
                except HTTPException as error:
                    db.rollback()
                    return error.status_code, width, photo
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(append, [230, 235]))
        assert sorted(status for status, _, _ in results) == [200, 422]
        _, width, photo = next(result for result in results if result[0] == 200)
        with factory() as db:
            row = db.get(Item, item_id)
            assert row.image_data == cover and row.additional_images == [extra] * 3 + [photo]
            assert row.description == f'Winner {width}'
    finally:
        isolated.dispose()


@pytest.mark.parametrize('has_primary,gallery', [(True, None), (True, []), (False, None), (False, [])])
def test_postgres_append_initializes_gallery_or_primary_without_losing_existing_photos(pg, has_primary, gallery):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated, tables=[m.__table__ for m in (Usuario, Vendedor, Supplier, Item, StockMovement)])
        factory = sessionmaker(bind=isolated)
        item_id = uuid.uuid4()
        cover, extra = picture('JPEG', (230, 125)), picture('JPEG', (240, 125))
        with factory() as db:
            db.add(Item(id=item_id, name='Azul M', sku_internal=str(item_id), image_data=cover if has_primary else None,
                        additional_images=gallery, current_stock=0, stock_loja=0, stock_deposito=0))
            db.commit()
            batch_edit_items(BatchEditRequest(item_ids=[item_id], image_groups=[{
                'item_ids': [item_id], 'image_data': extra, 'operation': 'add'}]), db, SimpleNamespace(id=uuid.uuid4()))
        with factory() as db:
            row = db.get(Item, item_id)
            assert row.image_data == (cover if has_primary else extra)
            assert row.additional_images == ([extra] if has_primary else gallery)
    finally:
        isolated.dispose()
