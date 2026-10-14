"""Synthetic grade writes keep their locks and avoid reading sibling originals."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
import sqlalchemy as sa
from fastapi import HTTPException

from test_assistant import setup
from test_product_intake_grade import manager_stock_app
from test_inventory_ocr import stock_app
from test_access_postgres import pg
from test_inventory_variants import pg_variants, source
from app.models.inventory import Item, StockMovement
from app.schemas.inventory import ItemResponse
from app.schemas.inventory_variants import VariantCreateRequest, VariantCreateResponse
from app.schemas.inventory_duplicate import DuplicateItemRequest
from app.services import inventory_variants as variants, inventory_duplicate as duplicate


def operation_request(operation, version, *, sizes=None):
    if operation == 'variants':
        return VariantCreateRequest(sizes=sizes or ['100'], model_name='Tênis Branco',
                                    source_version=version, initial_stock=2, confirm=True)
    return DuplicateItemRequest(request_id=uuid.uuid4(), source_version=version,
                                item={'name': 'Cópia revisada', 'size': '100', 'color': 'Branco',
                                      'image_data': 'data:image/png;base64,edited'},
                                initial_stock=2, confirm=True)


def execute(operation, db, item_id, request, user_id):
    if operation == 'variants':
        return VariantCreateResponse.model_validate(variants.create_variants(db, item_id, request, user_id))
    return ItemResponse.model_validate(duplicate.duplicate_item(db, item_id, request, user_id))


@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
@pytest.mark.parametrize('operation', ['variants', 'duplicate'])
def test_write_reads_no_sibling_originals_and_response_remains_complete(request, backend, operation):
    values = request.getfixturevalue('manager_stock_app' if backend == 'sqlite' else 'pg_variants')
    factory, user_id = (values[0], values[2]) if backend == 'sqlite' else values
    item_id = source(factory, user_id, group_key='read-grade')
    with factory() as db:
        peers = [Item(name=f'Tênis {size}', size=str(size), color='Branco' if size != 31 else 'Preto',
                      sku_internal=f'READ-{size}', group_key='read-grade', is_active=size != 20,
                      image_data='data:image/png;base64,' + 'x' * (128 * 1024))
                 for size in range(20, 32)]
        db.add_all(peers); db.commit()
        peer_ids = {row.id for row in peers}
        version = variants.source_version(db.get(Item, item_id))
    payload = operation_request(operation, version, sizes=['9', *map(str, range(20, 31)), '100'])
    with factory() as db:
        loaded_peers, peer_photos, after_commit_reads, lock_reads = set(), [], [], []
        committed = False
        def loaded(session, row):
            if isinstance(row, Item) and row.id in peer_ids:
                loaded_peers.add(row.id)
                if 'image_data' in row.__dict__:
                    peer_photos.append(row.id)
        def commit(session):
            nonlocal committed
            committed = True
        def capture(conn, cursor, statement, parameters, context, executemany):
            if 'FOR UPDATE' in statement and 'inventory_items' in statement:
                lock_reads.append(statement)
            if committed and statement.lstrip().upper().startswith('SELECT'):
                after_commit_reads.append(statement)
        sa.event.listen(db, 'loaded_as_persistent', loaded)
        sa.event.listen(db, 'after_commit', commit)
        sa.event.listen(db.bind, 'before_cursor_execute', capture)
        try:
            result = execute(operation, db, item_id, payload, user_id)
        finally:
            sa.event.remove(db.bind, 'before_cursor_execute', capture)
        assert loaded_peers == peer_ids  # Lock scope still includes other colors and inactive members.
        assert not peer_photos
        if backend == 'postgres':
            assert lock_reads and 'image_data' not in lock_reads[0]
        if operation == 'variants':
            assert not after_commit_reads  # Response serialization must not resurrect an N+1.
            assert len(result.existing) == 12 and {row.size for row in result.created} == {'100'}
            assert next(row for row in result.existing if row.size == '20').is_active is False
            created_id = result.created[0].id
        else:
            assert result.image_data == payload.item.image_data and result.name == payload.item.name
            assert result.current_stock == result.stock_loja == 2 and result.stock_deposito == 0
            created_id = result.id
    with factory() as db:
        original, created = db.get(Item, item_id), db.get(Item, created_id)
        assert original.image_data == 'data:image/png;base64,fixture' and original.current_stock == 7
        assert created.group_key == original.group_key and created.current_stock == 2
        assert created.image_data == (original.image_data if operation == 'variants' else payload.item.image_data)
        assert db.query(StockMovement).count() == 1


@pytest.mark.parametrize('operation', ['variants', 'duplicate'])
def test_postgres_photo_changed_while_waiting_for_lock_rejects_reviewed_version(pg_variants, operation):
    factory, user_id = pg_variants
    item_id = source(factory, user_id, group_key='locked-grade')
    with factory() as db:
        version = variants.source_version(db.get(Item, item_id))
    payload = operation_request(operation, version)
    reached_lock = Event()
    engine = factory.kw['bind']
    def observe(conn, cursor, statement, parameters, context, executemany):
        if 'inventory_items' in statement and 'FOR UPDATE' in statement:
            reached_lock.set()
    with factory() as editing:
        editing.get(Item, item_id).image_data = 'data:image/png;base64,new-photo'
        editing.flush()  # Keep the source row locked with an uncommitted photo change.
        sa.event.listen(engine, 'before_cursor_execute', observe)
        try:
            def write():
                with factory() as db:
                    with pytest.raises(HTTPException) as error:
                        execute(operation, db, item_id, payload, user_id)
                    return error.value.status_code
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(write)
                try:
                    assert reached_lock.wait(timeout=5)
                finally:
                    editing.commit()
                assert future.result(timeout=10) == 409
        finally:
            sa.event.remove(engine, 'before_cursor_execute', observe)
    with factory() as db:
        assert db.query(Item).count() == 1 and db.query(StockMovement).count() == 0
        assert db.get(Item, item_id).image_data == 'data:image/png;base64,new-photo'
