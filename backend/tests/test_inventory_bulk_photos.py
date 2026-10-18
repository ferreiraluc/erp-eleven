"""Per-selection covers: atomic, bounded, gallery-preserving and no original reads."""
import uuid
import json
import pytest
import sqlalchemy as sa
from test_assistant import setup
from test_inventory_ocr import stock_app, item, picture
from test_inventory_bulk_edit import adjustment
from app.models.inventory import Item, StockMovement


def seed_photos(factory):
    original = picture('JPEG', (160, 100))
    extra = picture('JPEG', (180, 110))
    with factory() as db:
        ids = []
        for color in ('Bege', 'BEGE', 'Azul', 'Preto'):
            row = item(db, loja=3, deposito=2, color=color, image_data=original,
                       additional_images=[extra], thumbnail_data='old-preview', thumbnail_ready=True)
            ids.append(str(row.id))
        db.commit()
    return ids, original, extra


@pytest.mark.parametrize('change_stock', [False, True])
def test_photo_groups_preserve_gallery_unselected_products_and_stock(stock_app, change_stock):
    factory, client, _ = stock_app
    ids, original, extra = seed_photos(factory)
    beige, blue = picture('JPEG', (170, 100)), picture('JPEG', (190, 100))
    with factory() as db: engine = db.bind
    statements = []
    def capture(conn, cursor, sql, *args): statements.append(sql)
    sa.event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = client.patch('/api/inventory/items/batch/photos', json={
            'item_ids': ids[:3], 'image_groups': [
                {'item_ids': ids[:2], 'image_data': beige},
                {'item_ids': ids[2:3], 'image_data': blue}],
            'sizes': [{'id': ids[0], 'name': 'Camiseta corrigida'}],
            'stock_adjustments': [adjustment(ids[0])] if change_stock else []})
    finally: sa.event.remove(engine, 'before_cursor_execute', capture)
    assert result.status_code == 200, result.text
    # New covers are written once per photo group, not once per variant.
    updates = [sql for sql in statements if sql.startswith('UPDATE inventory_items') and 'image_data=' in sql]
    assert len(updates) == 2
    selects = [sql for sql in statements if sql.startswith('SELECT')]
    assert all('image_data' not in sql and 'additional_images' not in sql for sql in selects)
    with factory() as db:
        rows = [db.get(Item, uuid.UUID(identity)) for identity in ids]
        assert [row.image_data for row in rows] == [beige, beige, blue, original]
        assert all(row.additional_images == [extra] for row in rows)
        assert (rows[0].stock_loja, rows[0].stock_deposito, rows[0].current_stock) == ((4, 2, 6) if change_stock else (3, 2, 5))
        assert all((row.stock_loja, row.stock_deposito, row.current_stock) == (3, 2, 5) for row in rows[1:])
        assert all(row.thumbnail_ready is False and row.thumbnail_data is None for row in rows[:3])
        assert rows[3].thumbnail_ready is True
        assert db.query(StockMovement).count() == int(change_stock)


@pytest.mark.parametrize('kind', ['outside', 'duplicate', 'shared', 'invalid', 'too_many', 'missing', 'stale_stock'])
def test_invalid_photo_batch_never_partially_saves(stock_app, kind):
    factory, client, _ = stock_app
    ids, original, extra = seed_photos(factory)
    new = picture('JPEG', (175, 100))
    group = {'item_ids': ids[:2], 'image_data': new}
    payload = {'item_ids': ids[:3], 'brand': 'Must not persist', 'image_groups': [group]}
    status = 422
    if kind == 'outside': group['item_ids'] = [ids[3]]
    if kind == 'duplicate': payload['image_groups'].append({'item_ids': [ids[0]], 'image_data': new})
    if kind == 'shared': payload['image_data'] = new
    if kind == 'invalid': group['image_data'] = 'data:image/jpeg;base64,bad'
    if kind == 'too_many': payload['image_groups'] = [group] * 21
    if kind == 'missing': payload['item_ids'].append(str(uuid.uuid4())); status = 409
    if kind == 'stale_stock':
        change = adjustment(ids[0]); change['expected_loja'] = 9
        payload['stock_adjustments'] = [change]; status = 409
    assert client.patch('/api/inventory/items/batch/photos', json=payload).status_code == status
    with factory() as db:
        assert all(row.image_data == original and row.brand is None and row.additional_images == [extra] for row in db.query(Item).all())


def test_photo_only_writes_have_per_product_audit_without_image_payload(stock_app):
    from app.database import get_db
    from app.models import Usuario
    from app.models.access import AuditEvent
    from app.services.user_audit import bind_actor
    factory, client, user_id = stock_app
    ids, _, _ = seed_photos(factory)
    with factory() as db: AuditEvent.__table__.create(db.bind, checkfirst=True)
    def session():
        with factory() as db:
            db.info['audit_enabled'] = True
            bind_actor(db, db.get(Usuario, user_id))
            yield db
    client.app.dependency_overrides[get_db] = session
    image = picture('JPEG', (190, 100))
    assert client.patch('/api/inventory/items/batch/photos', json={
        'item_ids': ids[:2], 'image_groups': [{'item_ids': ids[:2], 'image_data': image}]}).status_code == 200
    with factory() as db:
        events = db.query(AuditEvent).filter(AuditEvent.action == 'update').all()
        assert {event.entity_id for event in events} == set(ids[:2])
        assert all(event.user_id == user_id and event.changes == {'image_data': {'changed': True}} for event in events)
        assert image not in json.dumps([event.changes for event in db.query(AuditEvent).all()])


def test_bulk_photo_write_requires_auth(stock_app):
    from app.dependencies import get_current_active_user
    _, client, _ = stock_app
    del client.app.dependency_overrides[get_current_active_user]
    assert client.patch('/api/inventory/items/batch/photos', json={
        'item_ids': [str(uuid.uuid4())]}).status_code == 401
