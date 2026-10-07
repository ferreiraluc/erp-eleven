"""Permanent deletion is owner-only, reviewed and preserves operational links."""
import uuid
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app, item
from app.database import Base
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, StockMovement, InventorySession, InventorySessionItem
from app.models.pdv import PdvSale, PdvSaleItem
from app.models.access import AuditEvent
from app.services.inventory_service import create_movement
from app.dependencies import get_current_active_user


@pytest.fixture
def deletion_app(stock_app):
    factory, client, uid = stock_app
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[m.__table__ for m in
            (PdvSaleItem, InventorySession, InventorySessionItem, AuditEvent)])
        user = db.get(Usuario, uid); user.email = 'lucas@eleven.com'; user.role = UsuarioRole.ADMIN
        row = item(db, loja=0, deposito=0, image_data='fixture-photo', group_key='Same model', barcode='SHARED')
        create_movement(db, row.id, 'entry', 2, uid, reason='Cadastro de teste')
        row_id = str(row.id); db.commit()
    return factory, client, uid, row_id


def confirm(client, row_id):
    result = client.get(f'/api/inventory/items/{row_id}/deletion-preview')
    assert result.status_code == 200, result.text
    preview = result.json()
    return preview, {'sku':preview['item']['sku_internal'], 'plan_token':preview['plan_token'], 'confirm':True}


def test_anonymous_requests_cannot_inspect_or_delete(deletion_app):
    _, client, _, rid = deletion_app
    client.app.dependency_overrides.pop(get_current_active_user)
    assert client.get(f'/api/inventory/items/{rid}/deletion-preview').status_code == 401
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json={'sku':'forged','plan_token':'0'*64,'confirm':True}).status_code == 401


@pytest.mark.parametrize(('email','role'), [('wissam@eleven.com',UsuarioRole.GERENTE),
    ('denis@eleven.com',UsuarioRole.VENDEDOR), ('other-admin@eleven.com',UsuarioRole.ADMIN),
    ('lucas@eleven.com',UsuarioRole.GERENTE)])
def test_only_owner_can_preview_or_delete(deletion_app, email, role):
    factory, client, uid, rid = deletion_app
    with factory() as db:
        user = db.get(Usuario, uid); user.email = email; user.role = role; db.commit()
    assert client.get(f'/api/inventory/items/{rid}/deletion-preview').status_code == 403
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json={'sku':'forged','plan_token':'0'*64,'confirm':True}).status_code == 403
    with factory() as db: assert db.get(Item,uuid.UUID(rid)) is not None


def test_deletes_photo_and_unlinked_stock_preserves_other_variant_and_audits(deletion_app):
    factory, client, uid, rid = deletion_app
    with factory() as db:
        other = item(db, group_key='Same model',barcode='SHARED'); other_id = other.id; db.commit()
    preview, body = confirm(client,rid)
    assert preview['allowed'] and preview['movement_count'] == 1 and preview['item']['stock_loja'] == 2
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json=body).json()['deleted']
    with factory() as db:
        assert db.get(Item,uuid.UUID(rid)) is None and db.query(StockMovement).count() == 0
        assert db.get(Item,other_id) is not None
        audit = db.query(AuditEvent).filter_by(action='item_permanently_deleted').one()
        assert audit.user_id == uid and audit.changes['movements_removed'] == 1
        assert audit.changes['stock_removed']['total'] == 2 and 'fixture-photo' not in str(audit.changes)
    assert client.get(f'/api/inventory/items/{rid}').status_code == 404
    assert client.get('/api/inventory/items').json()['total'] == 1
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json=body).status_code == 404


@pytest.mark.parametrize('change', ['sku','plan_token','confirm','stock','name','movement'])
def test_stale_or_missing_confirmation_never_deletes(deletion_app,change):
    factory, client, uid, rid = deletion_app
    _, body = confirm(client,rid)
    if change in ('sku','plan_token'): body[change] = 'wrong' if change == 'sku' else '0'*64
    elif change == 'confirm': body['confirm'] = False
    else:
        with factory() as db:
            row = db.get(Item,uuid.UUID(rid))
            if change == 'stock': create_movement(db,row.id,'entry',1,uid)
            elif change == 'name': row.name = 'Updated name'
            else: db.query(StockMovement).one().reason = 'Revised movement'
            db.commit()
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json=body).status_code in (409,422)
    with factory() as db:
        assert db.get(Item,uuid.UUID(rid)) is not None
        assert db.query(StockMovement).count() >= 1 and db.query(AuditEvent).count() == 0


@pytest.mark.parametrize('link', ['completed','cancelled','legacy_sku','count','pedido','unknown','reference_only'])
def test_new_links_block_even_after_valid_preview(deletion_app,link):
    factory, client, uid, rid = deletion_app
    _, body = confirm(client,rid)
    with factory() as db:
        row = db.get(Item,uuid.UUID(rid))
        if link in ('completed','cancelled','legacy_sku'):
            sale = PdvSale(status='cancelled' if link=='cancelled' else 'completed'); db.add(sale); db.flush()
            db.add(PdvSaleItem(sale_id=sale.id,item_id=None if link=='legacy_sku' else row.id,item_sku=row.sku_internal,
                              item_name=row.name,quantity=1,unit_price_gs=10,total_gs=10))
        elif link == 'count':
            count = InventorySession(name='Inventário'); db.add(count); db.flush()
            db.add(InventorySessionItem(session_id=count.id,item_id=row.id,system_quantity=2))
        else:
            movement = db.query(StockMovement).one()
            movement.reference_type = None if link=='reference_only' else link
            movement.reference_id = str(uuid.uuid4())
        db.commit()
    preview = client.get(f'/api/inventory/items/{rid}/deletion-preview').json()
    assert not preview['allowed'] and preview['plan_token'] is None and preview['blockers']
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json=body).status_code == 409
    with factory() as db: assert db.get(Item,uuid.UUID(rid)) is not None and db.query(StockMovement).count() == 1


def test_inactive_bot_created_test_item_can_be_removed(deletion_app):
    factory, client, _, rid = deletion_app
    with factory() as db:
        db.get(Item,uuid.UUID(rid)).is_active=False
        movement=db.query(StockMovement).one();movement.reference_type='assistant_action';movement.reference_id=str(uuid.uuid4())
        db.commit()
    _, body = confirm(client,rid)
    assert client.request('DELETE',f'/api/inventory/items/{rid}/permanent',json=body).status_code == 200
