"""Read-only product history from existing records, with financial access enforced."""
from collections import defaultdict
from datetime import timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import load_only
from sqlalchemy import cast, String, func, or_, and_

from ..config import settings
from ..models.inventory import Item, StockMovement, InventorySessionItem, InventorySession
from ..models.pdv import PdvSale, PdvSaleItem, PdvSaleEvent
from ..models.usuario import Usuario
from ..models.access import AuditEvent
from .access_policy import is_owner, own_sales, sales_query
from .inventory_links import product_sale_link

PRODUCT_FIELDS = ('id', 'name', 'sku_internal', 'barcode', 'brand', 'size', 'color',
                  'category', 'is_active', 'created_at', 'updated_at', 'created_by',
                  'current_stock', 'stock_loja', 'stock_deposito', 'deleted_at', 'deleted_by')
# Never expose arbitrary audit JSON (photos, private payloads or request context).
CHANGE_FIELDS = {'name', 'description', 'category', 'brand', 'size', 'color', 'unit',
                 'location', 'barcode', 'sku_internal', 'supplier_id', 'cost_price',
                 'sale_price', 'currency', 'cost_currency', 'sale_currency', 'min_stock',
                 'max_stock', 'current_stock', 'stock_loja', 'stock_deposito', 'group_key', 'is_active'}


def timestamp(value, *, utc=False):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc if utc else settings.tz)
    return value.isoformat()


def amount(value):
    return str(value) if value is not None else None


def names(db, ids):
    ids = {v for v in ids if v}
    return dict(db.query(Usuario.id, Usuario.nome).filter(Usuario.id.in_(ids)).all()) if ids else {}


def product_history(db, item_id, user, *, section='movements', page=1, page_size=20):
    item = db.query(Item).options(load_only(*(getattr(Item, key) for key in PRODUCT_FIELDS))).filter_by(id=item_id).first()
    if item is None:
        raise HTTPException(404, 'Produto não encontrado. Atualize a lista de estoque.')
    owner = is_owner(user)
    if section == 'changes' and not owner:
        raise HTTPException(403, 'Somente Lucas pode consultar a auditoria do produto.')
    link = product_sale_link(item)
    sale_ids = db.query(PdvSaleItem.sale_id).filter(link)
    movement_sale_ids = db.query(PdvSale.id).join(StockMovement, and_(StockMovement.item_id == item.id,
        StockMovement.reference_type == 'pdv_sale', func.replace(StockMovement.reference_id, '-', '') == func.replace(cast(PdvSale.id, String), '-', '')))
    sales = sales_query(db.query(PdvSale).filter(or_(PdvSale.id.in_(sale_ids), PdvSale.id.in_(movement_sale_ids))), PdvSale, user, pdv=True)
    moves = db.query(StockMovement).filter_by(item_id=item.id)
    counts = db.query(InventorySessionItem).filter_by(item_id=item.id)
    changes = db.query(AuditEvent).filter(AuditEvent.entity == 'inventory_items',
        AuditEvent.entity_id == str(item.id), AuditEvent.action.in_(['create', 'update', 'delete', 'item_catalog_deleted']))
    totals = {'movements': moves.count(), 'sales': sales.count(), 'counts': counts.count(),
              'changes': changes.count() if owner else None}
    people = names(db, [item.created_by, item.deleted_by])
    creator = people.get(item.created_by)
    product = {key: getattr(item, key) for key in PRODUCT_FIELDS if key not in ('created_by', 'deleted_by')}
    product.update(created_by=creator, created_at=timestamp(item.created_at), updated_at=timestamp(item.updated_at))
    product.update(name=item.history_name, deleted_at=timestamp(item.deleted_at, utc=True), deleted_by=people.get(item.deleted_by))
    offset = (page - 1) * page_size
    rows = []
    if section == 'sales':
        batch = sales.order_by(PdvSale.created_at.desc(), PdvSale.id.desc()).offset(offset).limit(page_size).all()
        actors = names(db, [v for sale in batch for v in (sale.vendedor_id, sale.created_by)])
        lines = defaultdict(list)
        for line in db.query(PdvSaleItem).filter(link, PdvSaleItem.sale_id.in_([sale.id for sale in batch])).order_by(PdvSaleItem.id):
            lines[line.sale_id].append({
                'id': str(line.id), 'link': 'item_id' if line.item_id else 'legacy_sku',
                'name': f'Produto excluído — {line.item_name}' if item.deleted_at else line.item_name,
                'sku': line.item_sku, 'size': line.item_size, 'color': line.item_color,
                'quantity': amount(line.quantity), 'unit_price_gs': amount(line.unit_price_gs),
                'discount_gs': amount(line.discount_gs), 'total_gs': amount(line.total_gs),
                'location': line.location, 'is_avulso': line.is_avulso})
        # A correction can replace this product with another one. Keep its
        # original sale link discoverable through the stock ledger and revision.
        if owner:
            missing = [sale.id for sale in batch if not lines[sale.id]]
            events = db.query(PdvSaleEvent).filter(PdvSaleEvent.sale_id.in_(missing)).order_by(PdvSaleEvent.created_at).all() if missing else []
            for event in events:
                if lines[event.sale_id]: continue
                for line in (event.before or {}).get('items', []):
                    if line.get('item_id') != str(item.id): continue
                    lines[event.sale_id].append({'id':line['id'],'link':'revision',
                        'name':f"Produto excluído — {line['item_name']}" if item.deleted_at else line['item_name'],
                        'sku':line.get('item_sku'),'size':line.get('item_size'),'color':line.get('item_color'),
                        'quantity':line['quantity'],'unit_price_gs':line['unit_price_gs'],'discount_gs':line['discount_gs'],
                        'total_gs':line['total_gs'],'location':line['location'],'is_avulso':line['is_avulso']})
        rows = [{'id': str(sale.id), 'at': timestamp(sale.created_at), 'status': sale.status,
                 'updated_at': timestamp(sale.updated_at), 'seller': actors.get(sale.vendedor_id),
                 'actor': actors.get(sale.created_by), 'customer': sale.cliente_nome,
                 'stock_applied': sale.stock_applied, 'sale_total_gs': amount(sale.total_gs),
                 'lines': lines[sale.id]} for sale in batch]
    elif section == 'movements':
        batch = moves.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).offset(offset).limit(page_size).all()
        actors = names(db, [m.created_by for m in batch])
        pdv_refs = set()
        for m in batch:
            if m.reference_type == 'pdv_sale':
                try: pdv_refs.add(UUID(m.reference_id or ''))
                except ValueError: pass
        allowed_refs = {str(sid) for (sid,) in sales_query(db.query(PdvSale.id).filter(PdvSale.id.in_(pdv_refs)), PdvSale, user, pdv=True)}
        for m in batch:
            restricted = own_sales(user) and m.reference_type == 'pdv_sale' and m.reference_id not in allowed_refs
            rows.append({'id': str(m.id), 'at': timestamp(m.created_at), 'type': m.movement_type.value,
                'quantity': m.quantity, 'before': m.quantity_before, 'after': m.quantity_after,
                'location_from': m.location_from, 'location_to': m.location_to,
                'actor': None if restricted else actors.get(m.created_by),
                'reason': None if restricted else m.reason, 'notes': None if restricted else m.notes,
                'reference_type': m.reference_type, 'reference_id': None if restricted else m.reference_id,
                'restricted': restricted})
    elif section == 'counts':
        batch = counts.join(InventorySession).add_entity(InventorySession).order_by(
            InventorySession.started_at.desc(), InventorySessionItem.id.desc()).offset(offset).limit(page_size).all()
        actors = names(db, [r.counted_by for r, _ in batch])
        rows = [{'id': str(r.id), 'at': timestamp(r.scanned_at or session.started_at),
                 'session_id': str(session.id), 'name': session.name, 'status': session.status.value,
                 'location': session.count_location, 'system_quantity': r.system_quantity,
                 'counted_quantity': r.counted_quantity, 'actor': actors.get(r.counted_by),
                 'applied_at': timestamp(session.applied_at)} for r, session in batch]
    elif section == 'changes':
        batch = changes.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).offset(offset).limit(page_size).all()
        rows = [{'id': str(event.id), 'at': timestamp(event.occurred_at, utc=True), 'actor': event.actor_name,
                 'action': event.action, 'source': event.source,
                 'fields': {key: {k: v for k, v in detail.items() if k in ('before', 'after', 'changed')}
                            for key, detail in (event.changes or {}).items()
                            if key in CHANGE_FIELDS and isinstance(detail, dict)}} for event in batch]
    return {'product': product, 'section': section, 'page': page, 'page_size': page_size,
            'total': totals[section], 'totals': totals, 'rows': [dict(row, kind=section) for row in rows],
            'own_sales_only': own_sales(user), 'can_view_changes': owner}
