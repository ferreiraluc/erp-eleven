"""History explains existing links without creating sales, audit events or movements."""
import uuid
from datetime import datetime, timezone
import pytest
from test_assistant import setup
from test_inventory_ocr import stock_app, item
from app.database import Base
from app.dependencies import get_current_active_user
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.inventory import Item, StockMovement, InventorySession, InventorySessionItem
from app.models.pdv import PdvSale, PdvSaleItem
from app.models.access import AuditEvent
from app.services.inventory_service import create_movement


@pytest.fixture
def history_app(stock_app):
    factory, client, uid = stock_app
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[m.__table__ for m in (PdvSaleItem, InventorySession, InventorySessionItem, AuditEvent)])
        user = db.get(Usuario, uid); user.email = 'lucas@eleven.com'; user.nome = 'Lucas'; user.role = UsuarioRole.ADMIN
        row = item(db, loja=2, deposito=0, created_by=uid, barcode='REPEATED', image_data='PRIVATE_PHOTO')
        row_id = row.id; db.commit()
    return factory, client, uid, row_id


def sale(db, row, uid, *, status='completed', legacy=False, lines=1):
    s = PdvSale(vendedor_id=uid, created_by=uid, status=status, total_gs=6000, stock_applied=status=='completed', cliente_nome='Cliente da venda')
    db.add(s); db.flush()
    for _ in range(lines):
        db.add(PdvSaleItem(sale_id=s.id, item_id=None if legacy else row.id, item_sku=row.sku_internal,
                          item_name=row.name, quantity=1, unit_price_gs=3000, total_gs=3000, location='loja'))
    db.flush()
    return s


def get(client, rid, section='movements', **params):
    result = client.get(f'/api/inventory/items/{rid}/history', params={'section': section, **params})
    assert result.status_code == 200, result.text
    return result.json()


def test_metadata_stock_adjustment_counts_and_read_only(history_app):
    factory, client, uid, rid = history_app
    with factory() as db:
        create_movement(db, rid, 'entry', 3, uid, reason='Recebimento')
        adjustment = create_movement(db, rid, 'adjustment', 1, uid, reason='Conferência física')
        adjustment.created_at = datetime(2090, 1, 1)
        count = InventorySession(name='Contagem da loja', count_location='loja'); db.add(count); db.flush()
        db.add(InventorySessionItem(session_id=count.id, item_id=rid, system_quantity=1, counted_quantity=None))
        db.commit()
    result = get(client, rid, page_size=1)
    assert result['product']['created_by'] == 'Lucas' and result['product']['created_at']
    assert result['product']['current_stock'] == 1 and result['totals']['movements'] == 2
    assert 'image_data' not in result['product'] and 'PRIVATE_PHOTO' not in str(result)
    assert result['rows'][0]['type'] == 'adjustment'
    assert (result['rows'][0]['quantity'], result['rows'][0]['before'], result['rows'][0]['after']) == (1, 5, 1)
    next_page = get(client, rid, page=2, page_size=1)
    assert next_page['rows'][0]['reason'] == 'Recebimento'
    count_result = get(client, rid, 'counts')['rows'][0]
    assert count_result['name'] == 'Contagem da loja' and count_result['counted_quantity'] is None
    with factory() as db:
        assert db.query(AuditEvent).count() == 0 and db.query(StockMovement).count() == 2
        assert db.query(PdvSale).count() == 0


def test_distinct_sales_legacy_sku_cancelled_and_shared_barcode(history_app):
    factory, client, uid, rid = history_app
    with factory() as db:
        row = db.get(Item, rid)
        a = sale(db, row, uid, lines=2); a_id = str(a.id)
        b = sale(db, row, uid, legacy=True, status='cancelled'); b_id = str(b.id)
        other = item(db, barcode=row.barcode); sale(db, other, uid)
        db.commit()
    result = get(client, rid, 'sales')
    assert result['total'] == 2 and {r['id'] for r in result['rows']} == {a_id, b_id}
    by_id = {r['id']: r for r in result['rows']}
    assert len(by_id[a_id]['lines']) == 2
    assert by_id[b_id]['status'] == 'cancelled' and by_id[b_id]['lines'][0]['link'] == 'legacy_sku'
    assert by_id[a_id]['lines'][0]['link'] == 'item_id'
    preview = client.get(f'/api/inventory/items/{rid}/deletion-preview').json()
    assert {'code': 'sales', 'count': 2} in preview['blockers']


def test_personal_sales_scope_applies_before_totals_pagination_and_movement_details(history_app):
    factory, client, uid, rid = history_app
    with factory() as db:
        user = db.get(Usuario, uid); user.sales_scope = 'own'; user.role = UsuarioRole.GERENTE
        other = Usuario(nome='Colega',email='colleague@test.local',senha_hash='unused',role=UsuarioRole.GERENTE)
        db.add(other); db.flush()
        row = db.get(Item, rid); own = sale(db,row,uid); own_id = str(own.id)
        hidden = sale(db,row,other.id); hidden_id = str(hidden.id)
        create_movement(db,rid,'exit',1,other.id,reference_type='pdv_sale',reference_id=hidden_id,
                        reason='Cliente e valor privado',notes='nota privada')
        db.commit()
    result = get(client,rid,'sales',page_size=1)
    assert result['total'] == result['totals']['sales'] == 1 and result['rows'][0]['id'] == own_id
    assert hidden_id not in str(result) and result['own_sales_only']
    assert not result['can_view_changes'] and result['totals']['changes'] is None
    move = get(client,rid)['rows'][0]
    assert move['restricted'] and move['reference_id'] is None and move['notes'] is None and move['actor'] is None
    assert 'privad' not in str(move) and (move['before'], move['after']) == (2,1)
    assert client.get(f'/api/inventory/items/{rid}/history?section=changes').status_code == 403


def test_audit_owner_only_allowlist_and_unknown_values(history_app):
    factory, client, uid, rid = history_app
    with factory() as db:
        db.add(AuditEvent(user_id=uid,actor_name='Lucas',occurred_at=datetime(2026,10,7,15,tzinfo=timezone.utc),
            action='update',module='inventory',entity='inventory_items',entity_id=str(rid),
            changes={'name': {'changed':True}, 'current_stock': {'before':None,'after':0},
                     'image_data': {'after':'PRIVATE_PHOTO'}, 'payload': {'after':'PRIVATE_BODY'}}))
        db.commit()
    result = get(client,rid,'changes')
    assert result['rows'][0]['fields'] == {'name': {'changed':True}, 'current_stock':{'before':None,'after':0}}
    assert result['rows'][0]['at'].endswith('+00:00') and 'PRIVATE' not in str(result)
    with factory() as db:
        db.get(Item,rid).stock_deposito=None;db.commit()
    assert get(client,rid)['product']['stock_deposito'] is None


def test_history_authentication_invalid_ids_and_pagination(history_app):
    _, client, _, rid = history_app
    assert client.get('/api/inventory/items/bad/history').status_code == 400
    assert client.get(f'/api/inventory/items/{uuid.uuid4()}/history').status_code == 404
    assert client.get(f'/api/inventory/items/{rid}/history?section=unknown').status_code == 422
    assert client.get(f'/api/inventory/items/{rid}/history?page_size=101').status_code == 422
    client.app.dependency_overrides.pop(get_current_active_user)
    assert client.get(f'/api/inventory/items/{rid}/history').status_code == 401
