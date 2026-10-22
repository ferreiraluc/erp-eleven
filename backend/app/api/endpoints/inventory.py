from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, defer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, func, or_, case
from typing import List, Optional, Literal
from datetime import datetime, date
import uuid
import re
import io
import csv
import xml.etree.ElementTree as ET

from ...database import get_db
from ...config import settings
from ...models.inventory import (
    Item, Supplier, StockMovement, MovementType,
    InventorySession, InventorySessionItem, SessionStatus
)
from ...models.usuario import Usuario
from ...schemas.inventory import (
    ItemCreate, ItemUpdate, ItemResponse, ItemListResponse,
    SupplierCreate, SupplierResponse,
    MovementCreate, MovementResponse, BatchMovementCreate,
    SessionCreate, SessionResponse, SessionStatusUpdate, ScanItemCreate,
    SessionItemResponse, AlertSummary, GroupItemsRequest,
    GroupResponse, SuggestionResponse, RenameGroupRequest, UngroupRequest,
    BatchEditRequest, BatchSizeEntry, BatchProductFields, GradeCreateRequest, GradeCreateResponse,
    BulkTransferRequest,
    RelatedItemsResponse,
    GradeAttachRequest, GradeMembershipResponse, GradeDirectoryResponse,
    GradeSuggestionResponse, UngroupedGradeSuggestionsResponse,
    GradeMembersResponse,
)
from ...schemas.inventory_diagnostics import InventoryDiagnostics, IssueFilter
from ...dependencies import get_current_active_user, require_role, require_owner
from ...schemas.inventory_deletion import ItemDeletionConfirmation
from ...services.inventory_deletion import deletion_preview, permanently_delete_item, delete_from_catalog
from ...services.inventory_history import product_history
from ...services.inventory_movement_visibility import movement_read_responses
from ...services.inventory_service import create_movement, apply_session, _compute_alert_level, StockMovementError
from ..validators import validate_uuid
from datetime import datetime as dt

from ...schemas.inventory_duplicate import DuplicateItemRequest
from ...services.inventory_duplicate import duplicate_item
from ...schemas.inventory_variants import VariantContext, VariantCreateRequest, VariantCreateResponse
from ...services.inventory_variants import variant_context, create_variants

from ...services.inventory_taxonomy import canonical, clean_product_name, vocabulary, facet_filters
from ...services.inventory_search import build_search
from ...services.inventory_images import catalog_query, catalog_response, product_thumbnail, product_thumbnails
from ...services.inventory_related import related_products
from ...services.inventory_grade_management import (
    group_directory, item_grade_suggestions, ungrouped_grade_suggestions,
    attach_existing_grade, detach_grade, lock_grade,
    model_name as grade_model_name, variant_identity, same_model,
    grade_members,
)

from .inventory_receiving import router as receiving_router, lot_filter
from uuid import UUID

router = APIRouter()
router.include_router(receiving_router)


@router.get('/items/{item_id}/related', response_model=RelatedItemsResponse)
def get_related_products(item_id: UUID, limit: int = Query(12, ge=1, le=24),
                         after_rank: int | None = Query(None, ge=0, le=3), after_id: UUID | None = None,
                         db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return related_products(db, item_id, limit=limit, after_rank=after_rank, after_id=after_id)


@router.get('/items/{item_id}/grade-suggestions', response_model=GradeSuggestionResponse)
def get_item_grade_suggestions(item_id: UUID, limit: int = Query(8, ge=1, le=20),
                               db: Session = Depends(get_db),
                               current_user: Usuario = Depends(get_current_active_user)):
    return item_grade_suggestions(db, item_id, limit)


@router.post('/items/{item_id}/duplicate', response_model=ItemResponse, status_code=201)
def copy_inventory_item(item_id: str, request: DuplicateItemRequest, db: Session = Depends(get_db),
                        current_user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    return duplicate_item(db, validate_uuid(item_id, 'ID do item'), request, current_user.id)


@router.get('/items/{item_id}/variants', response_model=VariantContext)
def get_variant_context(item_id: str, all_colors: bool = False, db: Session = Depends(get_db),
                        current_user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    return variant_context(db, validate_uuid(item_id, 'ID do item'), all_colors=all_colors)


@router.post('/items/{item_id}/variants', response_model=VariantCreateResponse, status_code=201)
def add_item_variants(item_id: str, request: VariantCreateRequest, db: Session = Depends(get_db),
                      current_user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    return create_variants(db, validate_uuid(item_id, 'ID do item'), request, current_user.id)


@router.get('/diagnostics', response_model=InventoryDiagnostics)
def inventory_diagnostics(
    issue: IssueFilter = 'all', q: str = Query('', max_length=150),
    page: int = Query(1, ge=1, le=20000), page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user),
):
    from ...services.inventory_diagnostics import diagnose_inventory
    return diagnose_inventory(db, issue=issue, q=q, page=page, page_size=page_size)


# ── Text normalization ────────────────────────────────────────────────────────
def _normalize_item(data: dict) -> dict:
    """Canonicalize filter facets, preserving the product name's chosen casing."""
    if 'name' in data:
        data['name'] = clean_product_name(data['name'])
    for field in ('brand', 'color', 'category'):
        if field in data and data[field]:
            data[field] = canonical(data[field], field)
    return data

# ── Size ordering ─────────────────────────────────────────────────────────────
import re as _re

_KNOWN_SIZE_ORDER = {
    # International
    "XXS": 0, "XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5,
    "2XL": 6, "XXL": 6, "3XL": 7, "XXXL": 7,
    "4XL": 8, "XXXXL": 8, "5XL": 9, "XXXXXL": 9,
    # Brazilian/Portuguese
    "PP": 10, "P": 11, "G": 12, "GG": 13, "XG": 14, "XGG": 15, "XXG": 16, "XXXG": 17,
    # Universal
    "U": 99, "UN": 99,
}

def _size_sort_key(size):
    """Returns a tuple for correct size ordering: numeric shoe sizes < clothing sizes < unknown < null."""
    if size is None:
        return (3, 0.0, "")
    s = size.strip().upper()
    if s in _KNOWN_SIZE_ORDER:
        return (1, float(_KNOWN_SIZE_ORDER[s]), s)
    # Pure numeric only (shoe/pant sizes: 36, 37, 38...) — avoids "2XL" matching as 2.0
    if _re.match(r'^\d+(\.\d+)?$', s):
        return (0, float(s), s)
    return (2, 0.0, s)


def _generate_sku() -> str:
    date_part = dt.now().strftime("%Y%m%d")
    rand_part = uuid.uuid4().hex[:4].upper()
    return f"INV-{date_part}-{rand_part}"


def _item_to_response(item: Item) -> dict:
    data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    data["alert_level"] = _compute_alert_level(item)
    return data


def _known_stock_filter():
    return and_(Item.current_stock.isnot(None), Item.stock_loja.isnot(None), Item.stock_deposito.isnot(None))


# --- Suppliers ---------------------------------------------------------------

@router.get("/suppliers", response_model=List[SupplierResponse])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    return db.query(Supplier).filter(Supplier.is_active == True).all()


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
def create_supplier(
    supplier: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    db_supplier = Supplier(**supplier.dict())
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier


# --- Items -------------------------------------------------------------------

@router.get('/items/deleted-history')
def deleted_product_history(q: str = Query('', max_length=150), page: int = Query(1, ge=1, le=20000),
                            db: Session = Depends(get_db), owner: Usuario = Depends(require_owner)):
    query = db.query(Item.id, Item.name, Item.sku_internal, Item.deleted_at).filter(Item.deleted_at.isnot(None))
    if q.strip():
        term = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(or_(Item.name.ilike(f'%{term}%', escape='\\'), Item.sku_internal.ilike(f'%{term}%', escape='\\')))
    total = query.count()
    rows = query.order_by(Item.deleted_at.desc(), Item.id.desc()).offset((page-1)*20).limit(20).all()
    return {'total': total, 'page': page, 'page_size': 20, 'items': [
        {'id': row.id, 'name': f'Produto excluído — {row.name}', 'sku': row.sku_internal, 'deleted_at': row.deleted_at} for row in rows]}

@router.get("/items/distinct-values")
def get_distinct_values(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    brands = db.query(Item.brand).filter(Item.deleted_at.is_(None), Item.brand.isnot(None), Item.brand != '').distinct().all()
    categories = db.query(Item.category).filter(Item.deleted_at.is_(None), Item.category.isnot(None), Item.category != '').distinct().all()
    return {
        "brands": sorted(vocabulary([b[0] for b in brands], "brand").values()),
        "categories": sorted(vocabulary([c[0] for c in categories], "category").values()),
    }


@router.get("/items", response_model=ItemListResponse)
def list_items(
    receiving_lot_id: UUID | None = None,
    search: Optional[str] = Query(None, max_length=256),
    category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    item_status: Optional[str] = Query(None, alias="status"),
    supplier_id: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    ungrouped_only: bool = Query(False),
    location_stock: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_images: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    taxonomy_filter = facet_filters(db)
    query = db.query(Item).filter(Item.deleted_at.is_(None))

    if receiving_lot_id:
        query = query.filter(lot_filter(receiving_lot_id))

    searched = build_search(db, search or '', taxonomy_filter=taxonomy_filter, brand_context=brand or '', size=size) if search or size else None
    if searched:
        query = query.filter(searched.condition)
    if category:
        query = query.filter(taxonomy_filter(Item.category, category))
    if brand:
        query = query.filter(taxonomy_filter(Item.brand, brand))
    if location:
        query = query.filter(Item.location.ilike(f"%{location}%"))
    if color:
        query = query.filter(taxonomy_filter(Item.color, color))
    if supplier_id:
        sup_uuid = validate_uuid(supplier_id, "supplier_id")
        query = query.filter(Item.supplier_id == sup_uuid)
    if ungrouped_only:
        query = query.filter(Item.group_key == None)
    if location_stock == "loja":
        query = query.filter(Item.stock_loja > 0)
    elif location_stock == "deposito":
        query = query.filter(Item.stock_deposito > 0)

    # Status filters
    if item_status in ('low_stock', 'out_of_stock', 'overstocked'):
        query = query.filter(_known_stock_filter())
    if item_status == "low_stock":
        query = query.filter(Item.is_active == True, Item.current_stock > 0, Item.current_stock < Item.min_stock)
    elif item_status == "out_of_stock":
        query = query.filter(Item.is_active == True, Item.current_stock <= 0)
    elif item_status == "overstocked":
        query = query.filter(Item.is_active == True, Item.max_stock > 0, Item.current_stock > Item.max_stock)
    elif item_status == "unknown_stock":
        query = query.filter(Item.is_active == True, ~_known_stock_filter())
    elif item_status == "inactive":
        query = query.filter(Item.is_active == False)
    elif item_status == "active":
        query = query.filter(Item.is_active == True)
    else:
        pass  # no filter, show all

    total = query.count()
    offset = (page - 1) * page_size
    query = catalog_query(query, include_images)
    if sort_by == "updated_at":
        items = query.order_by(Item.updated_at.desc()).offset(offset).limit(page_size).all()
    elif sort_by == "created_at":
        items = query.order_by(Item.created_at.desc(), Item.id.desc()).offset(offset).limit(page_size).all()
    else:
        items = query.order_by(*([searched.rank] if searched else []), Item.name, Item.color, Item.size, Item.id).offset(offset).limit(page_size).all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    item_responses = []
    for item, has_image in items:
        resp = catalog_response(item, has_image, include_images)
        resp.alert_level = _compute_alert_level(item)
        item_responses.append(resp)

    return ItemListResponse(
        items=item_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/items", response_model=ItemResponse, status_code=201)
def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    sku = _generate_sku()
    # Ensure uniqueness
    while db.query(Item).filter(Item.sku_internal == sku).first():
        sku = _generate_sku()

    item_data = _normalize_item(item.dict())
    group_key = (item_data.get('group_key') or '').strip()
    if item_data.get('group_key') is not None and (not group_key or len(group_key) > 100):
        raise HTTPException(422, 'O nome da grade deve ter entre 1 e 100 caracteres.')
    if group_key:
        lock_grade(db, group_key)
        members = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
            Item.deleted_at.is_(None), Item.group_key == group_key
        ).order_by(Item.id).with_for_update().all()
        from types import SimpleNamespace
        proposed = SimpleNamespace(**item_data)
        if any(not same_model(proposed, member) for member in members):
            raise HTTPException(409, 'A grade já contém outro modelo. Escolha uma grade diferente.')
        if any(variant_identity(member.size, member.color) ==
               variant_identity(item_data.get('size'), item_data.get('color')) for member in members):
            raise HTTPException(409, 'A grade já contém esta combinação de tamanho e cor.')
    db_item = Item(**item_data, sku_internal=sku, created_by=current_user.id)
    db.add(db_item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating item")
    db.refresh(db_item)
    resp = ItemResponse.model_validate(db_item)
    resp.alert_level = _compute_alert_level(db_item)
    return resp


@router.get("/items/barcode/{code}", response_model=List[ItemResponse])
def get_items_by_barcode(
    code: str,
    include_images: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    normalized = code.strip().upper()
    identity = Item.inventory_code == normalized if re.fullmatch(r'INV-[A-Z0-9]{6}', normalized) else or_(
        Item.barcode == code, Item.sku_internal == code, Item.inventory_code == normalized)
    query = db.query(Item).filter(Item.deleted_at.is_(None), identity, Item.is_active == True)
    items = catalog_query(query, include_images).all()
    result = []
    for item, has_image in items:
        resp = catalog_response(item, has_image, include_images)
        resp.alert_level = _compute_alert_level(item)
        result.append(resp)
    return result


@router.get("/alerts/summary", response_model=AlertSummary)
def get_alerts_summary(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    active = Item.is_active.is_(True)
    known = _known_stock_filter()
    def count_where(condition):
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)
    # Aggregate in SQL: never load catalog photos (or whole product rows) for counters.
    counts = db.query(
        count_where(active & known & (Item.current_stock > 0) & (Item.current_stock < Item.min_stock)).label('low_stock_count'),
        count_where(active & known & (Item.current_stock <= 0)).label('out_of_stock_count'),
        count_where(active & known & (Item.max_stock > 0) & (Item.current_stock > Item.max_stock)).label('overstocked_count'),
        count_where(active & ~known).label('unknown_stock_count'),
        count_where(active).label('total_active_items'),
        count_where(Item.is_active.is_(False)).label('inactive_count'),
        func.count(func.distinct(case((active, Item.group_key)))).label('group_count'),
        count_where(active & Item.group_key.isnot(None) & (Item.group_key != '')).label('grouped_items_count'),
        count_where(active & (Item.stock_loja > 0)).label('loja_count'),
        count_where(active & (Item.stock_deposito > 0)).label('deposito_count'),
    ).filter(Item.deleted_at.is_(None)).one()
    return AlertSummary(**dict(counts._mapping))


@router.get("/groups", response_model=List[GroupResponse])
def get_groups(
    receiving_lot_id: UUID | None = None,
    search: Optional[str] = Query(None, max_length=256),
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_status: Optional[str] = Query(None, alias="status"),
    location_stock: Optional[str] = Query(None),
    include_images: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Returns all groups with their items from DB, with optional filters.
    Filters are applied at the group level: a group is included if at least
    one of its items matches the filter criteria."""

    # Match the entire search and filters on the SAME variant.
    # A group is included if ANY item matches — then ALL items of that group are shown.
    matching_keys: Optional[list] = None
    matching_counts: dict = {}
    taxonomy_filter = facet_filters(db)
    searched = build_search(db, search, taxonomy_filter=taxonomy_filter, brand_context=brand or '') if search else None
    if search or brand or category or item_status or location_stock or receiving_lot_id:
        kq = db.query(Item.group_key, func.count(Item.id)).filter(Item.deleted_at.is_(None),
            Item.group_key.isnot(None),
            Item.is_active == True,
        )
        if receiving_lot_id:
            kq = kq.filter(lot_filter(receiving_lot_id))
        if searched:
            kq = kq.filter(searched.condition)
        if brand:
            kq = kq.filter(taxonomy_filter(Item.brand, brand))
        if category:
            kq = kq.filter(taxonomy_filter(Item.category, category))
        if item_status in ('low_stock', 'out_of_stock', 'overstocked'):
            kq = kq.filter(_known_stock_filter())
        if item_status == "low_stock":
            kq = kq.filter(Item.current_stock > 0, Item.current_stock < Item.min_stock)
        elif item_status == "out_of_stock":
            kq = kq.filter(Item.current_stock <= 0)
        elif item_status == "overstocked":
            kq = kq.filter(Item.max_stock > 0, Item.current_stock > Item.max_stock)
        elif item_status == "unknown_stock":
            kq = kq.filter(~_known_stock_filter())
        if location_stock == "loja":
            kq = kq.filter(Item.stock_loja > 0)
        elif location_stock == "deposito":
            kq = kq.filter(Item.stock_deposito > 0)
        kq = kq.group_by(Item.group_key)
        if searched:
            kq = kq.order_by(func.min(searched.rank), Item.group_key)
        matching_counts = dict(kq.all())
        matching_keys = list(matching_counts)
        if not matching_keys:
            return []

    # Preserve the full grade as context for the matching variant.
    item_query = db.query(Item).filter(Item.deleted_at.is_(None), Item.group_key.isnot(None), Item.is_active == True)
    if receiving_lot_id:
        item_query = item_query.filter(lot_filter(receiving_lot_id))
    if matching_keys is not None:
        item_query = item_query.filter(Item.group_key.in_(matching_keys))
    items = catalog_query(item_query, include_images).order_by(Item.group_key, Item.name).all()

    # Build GroupResponse objects
    groups_dict: dict = {}
    for item, has_image in items:
        key = item.group_key
        if key not in groups_dict:
            groups_dict[key] = []
        resp = catalog_response(item, has_image, include_images)
        resp.alert_level = _compute_alert_level(item)
        groups_dict[key].append(resp)

    result = []
    for key, item_list in groups_dict.items():
        sorted_items = sorted(item_list, key=lambda i: ((i.color or '').lower(), _size_sort_key(i.size)))
        total_stock = None if any(i.current_stock is None for i in sorted_items) else sum(i.current_stock for i in sorted_items)
        result.append(GroupResponse(group_key=key, items=sorted_items, total_stock=total_stock,
                                    matching_count=matching_counts.get(key, len(sorted_items))))
    if searched and matching_keys:
        order = {key: index for index, key in enumerate(matching_keys)}
        result.sort(key=lambda group: order[group.group_key])
    return result


@router.get('/groups/directory', response_model=GradeDirectoryResponse)
def grade_directory(search: str = Query('', max_length=100), limit: int = Query(20, ge=1, le=50),
                    db: Session = Depends(get_db),
                    current_user: Usuario = Depends(get_current_active_user)):
    return group_directory(db, search, limit)


@router.get('/groups/suggestions', response_model=UngroupedGradeSuggestionsResponse)
def suggest_ungrouped_for_grade(group_key: str = Query(..., min_length=1, max_length=100),
                                limit: int = Query(12, ge=1, le=30),
                                db: Session = Depends(get_db),
                                current_user: Usuario = Depends(get_current_active_user)):
    return ungrouped_grade_suggestions(db, group_key, limit)


@router.get('/groups/members', response_model=GradeMembersResponse)
def get_grade_members(group_key: str = Query(..., min_length=1, max_length=100),
                      page: int = Query(1, ge=1), limit: int = Query(100, ge=1, le=200),
                      db: Session = Depends(get_db),
                      current_user: Usuario = Depends(get_current_active_user)):
    return grade_members(db, group_key, page, limit)


@router.patch("/groups", status_code=200)
def rename_group(
    body: RenameGroupRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Rename a group — updates group_key on all items in the group without touching item names"""
    old_key = body.old_key.strip()
    new_key = body.new_key.strip()
    if not old_key or not new_key or len(new_key) > 100:
        raise HTTPException(status_code=400, detail="Informe nomes de grade válidos (até 100 caracteres).")
    if new_key == old_key:
        return {"message": "Nenhuma alteração", "count": 0}
    for key in sorted((old_key, new_key)):
        lock_grade(db, key)
    items = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.group_key == old_key).order_by(Item.id).with_for_update().all()
    if not items:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if db.query(Item.id).filter(Item.deleted_at.is_(None), Item.group_key == new_key).first():
        raise HTTPException(status_code=409, detail="Já existe uma grade com esse nome. Vincule os itens explicitamente.")
    for item in items:
        item.group_key = new_key
    db.commit()
    return {"message": f"Grupo renomeado de '{old_key}' para '{new_key}'", "count": len(items)}


@router.get("/suggestions", response_model=List[SuggestionResponse])
def get_suggestions(
    include_images: bool = Query(False),
    limit: int = Query(1000, ge=2, le=2000),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Suggest recent avulsos, bounded for large catalogs; manual search sees all."""
    items = (
        catalog_query(db.query(Item), include_images).filter(Item.deleted_at.is_(None))
        .filter(Item.group_key == None, Item.is_active == True)
        .order_by(Item.created_at.desc(), Item.id.desc())
        .limit(limit).all()
    )
    # A model can span colors; never strip an arbitrary trailing number because
    # product model codes (e.g. Boss 2001020) are part of its identity.
    map_: dict = {}
    for item, has_image in items:
        base = grade_model_name(item.name, item.size, item.color)
        if len(base) < 4:
            continue
        group_key = (base.casefold(), canonical(item.brand, 'brand') if item.brand else None,
                     canonical(item.category, 'category') if item.category else None,
                     (item.unit or '').casefold())
        if group_key not in map_:
            map_[group_key] = {'name': base, 'items': []}
        resp = catalog_response(item, has_image, include_images)
        resp.alert_level = _compute_alert_level(item)
        map_[group_key]['items'].append(resp)

    return [
        SuggestionResponse(name=v['name'], items=v['items'])
        for v in sorted(map_.values(), key=lambda x: len(x['items']), reverse=True)
        if len(v['items']) >= 2
    ][:25]


@router.get('/items/thumbnails')
def get_product_thumbnails(ids: List[uuid.UUID] = Query(..., min_length=1, max_length=12),
                           db: Session = Depends(get_db),
                           current_user: Usuario = Depends(get_current_active_user)):
    return product_thumbnails(db, list(dict.fromkeys(ids)))


@router.get("/items/{item_id}/thumbnail")
def get_product_thumbnail(item_id: str, db: Session = Depends(get_db),
                          current_user: Usuario = Depends(get_current_active_user)):
    return product_thumbnail(db, validate_uuid(item_id))


@router.get('/items/{item_id}/photos')
def get_item_photos(item_id: str, db: Session = Depends(get_db),
                    current_user: Usuario = Depends(get_current_active_user)):
    row = db.query(Item.additional_images).filter(
        Item.id == validate_uuid(item_id), Item.deleted_at.is_(None)).first()
    if row is None:
        raise HTTPException(404, 'Item not found')
    return {'additional_images': row.additional_images or []}


@router.get("/items/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    item_uuid = validate_uuid(item_id)
    item = db.query(Item).filter(Item.deleted_at.is_(None), Item.id == item_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    resp = ItemResponse.model_validate(item)
    resp.alert_level = _compute_alert_level(item)
    return resp


@router.put("/items/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: str,
    item_update: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    item_uuid = validate_uuid(item_id)
    original_group = db.query(Item.group_key).filter(Item.deleted_at.is_(None),
                                                    Item.id == item_uuid).scalar()
    lock_grade(db, original_group)
    db_item = db.query(Item).filter(Item.deleted_at.is_(None), Item.id == item_uuid).with_for_update().populate_existing().first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    if db_item.group_key != original_group:
        raise HTTPException(409, 'A grade do produto mudou. Atualize a listagem e tente novamente.')

    update_data = _normalize_item(item_update.dict(exclude_unset=True))
    if 'group_key' in update_data and update_data['group_key'] != db_item.group_key:
        raise HTTPException(409, 'Use Gerenciar grade para vincular ou remover o produto.')
    wanted = variant_identity(update_data.get('size', db_item.size),
                              update_data.get('color', db_item.color))
    if db_item.group_key and (wanted != variant_identity(db_item.size, db_item.color) or
                              (not db_item.is_active and update_data.get('is_active') is True)):
        peers = db.query(Item.size, Item.color).filter(
            Item.deleted_at.is_(None), Item.group_key == db_item.group_key,
            Item.id != db_item.id).all()
        if any(variant_identity(peer.size, peer.color) == wanted for peer in peers):
            raise HTTPException(409, 'A grade já contém esta combinação de tamanho e cor.')
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    resp = ItemResponse.model_validate(db_item)
    resp.alert_level = _compute_alert_level(db_item)
    return resp


@router.post("/items/group")
def group_items_batch(
    request: GroupItemsRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    lock_grade(db, request.group_key)
    items = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.id.in_(request.item_ids)).order_by(Item.id).with_for_update().all()
    if len(items) != len(request.item_ids):
        raise HTTPException(status_code=404, detail="Um dos produtos não foi encontrado.")
    if any(not item.is_active or item.group_key for item in items):
        raise HTTPException(status_code=409, detail="Seleção mudou: escolha somente produtos avulsos e ativos.")
    occupied = {variant_identity(row.size, row.color) for row in db.query(Item.size, Item.color).filter(
        Item.deleted_at.is_(None),
        Item.group_key == request.group_key).with_for_update().all()}
    for item in items:
        identity = variant_identity(item.size, item.color)
        if identity in occupied:
            raise HTTPException(409, 'A grade já contém esta combinação de tamanho e cor.')
        occupied.add(identity)
    for item in items:
        item.group_key = request.group_key
    db.commit()
    return {"message": f"Grouped {len(items)} items", "count": len(items)}


@router.post('/items/{item_id}/grade', response_model=GradeMembershipResponse)
def attach_item_to_grade(item_id: UUID, request: GradeAttachRequest,
                         db: Session = Depends(get_db),
                         current_user: Usuario = Depends(require_role(['ADMIN', 'GERENTE']))):
    """Attach one reviewed product to an existing grade; never create a product."""
    return attach_existing_grade(db, item_id, request.group_key, request.expected_group_key)


# Separate path prevents older servers from silently ignoring per-size quantities during a rolling deploy.
@router.post("/items/grade/quantities", response_model=GradeCreateResponse, status_code=201)
@router.post("/items/grade", response_model=GradeCreateResponse, status_code=201)
def create_grade(
    grade: GradeCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Create a full size grid (grade) — one item per size, all sharing the same group_key."""
    sizes = list(dict.fromkeys(s.strip().upper() for s in grade.sizes if s.strip()))
    if not sizes:
        raise HTTPException(status_code=400, detail="Informe ao menos um tamanho para criar a grade")

    # Normalize text fields
    norm_name = clean_product_name(grade.name)
    norm_color = canonical(grade.color, 'color') if grade.color else None
    norm_brand = canonical(grade.brand, 'brand') if grade.brand else None
    norm_category = canonical(grade.category, 'category') if grade.category else None

    # Auto-generate group_key from name + color
    group_key = (grade.group_key or "").strip()
    if not group_key:
        color_part = f" {norm_color}" if norm_color else ""
        group_key = f"{norm_name.strip()}{color_part}"
    if not group_key or len(group_key) > 100:
        raise HTTPException(422, 'O nome da grade deve ter entre 1 e 100 caracteres.')
    lock_grade(db, group_key)
    # The new-item modal submits one color at a time with the same group key.
    # Permit that matrix while rejecting a collision or an unrelated model.
    existing = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.group_key == group_key
    ).order_by(Item.id).with_for_update().all()
    if existing:
        from types import SimpleNamespace
        proposed = SimpleNamespace(name=norm_name, size=None, color=norm_color,
                                   brand=norm_brand, category=norm_category,
                                   unit=grade.unit or 'un')
        if any(not same_model(proposed, member) for member in existing):
            raise HTTPException(409, 'A grade já contém outro modelo. Escolha uma grade diferente.')
        occupied = {variant_identity(member.size, member.color) for member in existing}
        if any(variant_identity(size, norm_color) in occupied for size in sizes):
            raise HTTPException(409, 'A grade já contém esta combinação de tamanho e cor.')

    created_items: list[Item] = []
    for size in sizes:
        # Store the explicit business code for the variant: base barcode + size.
        item_barcode = f"{grade.base_barcode}{size}" if grade.base_barcode else None
        item_name = f"{norm_name.strip()} {size}"

        sku = _generate_sku()
        while db.query(Item).filter(Item.sku_internal == sku).first():
            sku = _generate_sku()

        db_item = Item(
            name=item_name,
            description=grade.description,
            category=norm_category,
            size=size,
            color=norm_color,
            brand=norm_brand,
            unit=grade.unit or "un",
            location=grade.location,
            barcode=item_barcode,
            sku_internal=sku,
            supplier_id=grade.supplier_id,
            cost_price=grade.cost_price or 0,
            sale_price=grade.sale_price or 0,
            currency=grade.currency or "PYG",
            cost_currency=grade.cost_currency or "BRL",
            sale_currency=grade.sale_currency or "USD",
            min_stock=grade.min_stock or 0,
            max_stock=grade.max_stock or 0,
            current_stock=0,
            image_data=grade.image_data,
            group_key=group_key,
            is_active=True,
            created_by=current_user.id,
        )
        db.add(db_item)
        created_items.append(db_item)

    # Persist variants and their initial movements together. A failed entry must not
    # leave an undisclosed, half-created grade that would be duplicated on retry.
    try:
        db.flush()
        if grade.additional_images:
            # Bind the gallery once, not once per size in a bulk INSERT. A large
            # grade must not multiply the Python/driver image buffers.
            db.query(Item).filter(Item.id.in_([row.id for row in created_items])).update(
                {Item.additional_images: grade.additional_images, Item.updated_at: Item.updated_at},
                synchronize_session=False)
        for item in created_items:
            quantity = grade.stock_by_size.get(item.size, grade.initial_stock or 0)
            if quantity > 0:
                create_movement(
                    db=db,
                    item_id=item.id,
                    movement_type="entry",
                    quantity=quantity,
                    reason="Estoque inicial — criação de grade",
                    created_by=current_user.id,
                    location=grade.stock_location or "loja",
                )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Erro ao criar grade — possível conflito de SKU")
    except Exception:
        db.rollback()
        raise

    for item in created_items:
        db.refresh(item)

    item_responses = []
    for item in created_items:
        resp = ItemResponse.model_validate(item)
        resp.alert_level = _compute_alert_level(item)
        item_responses.append(resp)

    return GradeCreateResponse(
        group_key=group_key,
        items=item_responses,
        total_created=len(item_responses),
    )


@router.post("/items/ungroup")
def ungroup_items(
    body: UngroupRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    lock_grade(db, body.group_key)
    items = db.query(Item).options(defer(Item.image_data, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.group_key == body.group_key).order_by(Item.id).with_for_update().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found with this group_key")
    for item in items:
        item.group_key = None
    db.commit()
    return {"message": f"Ungrouped {len(items)} items", "count": len(items)}


@router.delete("/items/{item_id}/group", response_model=GradeMembershipResponse, status_code=200)
def remove_item_from_group(
    item_id: str,
    expected_group_key: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Remove only this member, preserving its stock and operational history."""
    return detach_grade(db, validate_uuid(item_id), expected_group_key)


@router.patch("/items/batch", status_code=200)
@router.patch("/items/batch/quantities", status_code=200)
@router.patch("/items/batch/photos", status_code=200)
@router.patch("/items/batch/details", status_code=200)
def batch_edit_items(
    request: BatchEditRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Bulk edit shared fields (brand, category, image, prices) and per-item fields (name, color, barcode, prices, stock)"""
    # The legacy mass editor may still update grade membership. It must share
    # the same advisory locks as variant creation and the dedicated manager.
    grade_fields = 'group_key' in request.model_fields_set or any(
        'group_key' in entry.model_fields_set for entry in request.sizes or [])
    if grade_fields and current_user.role.value not in ('ADMIN', 'GERENTE'):
        raise HTTPException(403, 'Alterar grades exige perfil de gestão.')
    variant_fields = bool({'size', 'color', 'is_active'} & request.model_fields_set or any(
        {'size', 'color', 'is_active'} & entry.model_fields_set for entry in request.sizes or []))
    original_groups = {}
    if grade_fields or variant_fields:
        original_groups = dict(db.query(Item.id, Item.group_key).filter(
            Item.id.in_(request.item_ids), Item.deleted_at.is_(None)).all())
        destination_keys = {request.group_key} if request.group_key else set()
        destination_keys.update(entry.group_key for entry in request.sizes or [] if entry.group_key)
        for key in sorted({*original_groups.values(), *destination_keys} - {None, ''}):
            lock_grade(db, key)
    query = db.query(Item).options(defer(Item.image_data, raiseload=True))
    items = query.filter(Item.deleted_at.is_(None), Item.id.in_(request.item_ids)).order_by(Item.id).populate_existing().with_for_update().all()
    if len(items) != len(request.item_ids):
        raise HTTPException(status_code=409, detail="Um produto selecionado não está mais disponível. Reabra a edição para conferir a seleção.")
    if original_groups and any(original_groups.get(item.id) != item.group_key for item in items):
        raise HTTPException(409, 'Uma grade mudou durante a edição. Reabra a seleção para conferir.')

    adjustments = {entry.id: entry for entry in request.stock_adjustments or []}
    # Compare all locations under the row locks, before changing any metadata.
    # A stale browser must never overwrite a sale/transfer made after its preview.
    for item in items:
        adjustment = adjustments.get(item.id)
        if adjustment and (item.stock_loja, item.stock_deposito, item.current_stock) != (
            adjustment.expected_loja, adjustment.expected_deposito, adjustment.expected_total,
        ):
            raise HTTPException(status_code=409, detail="O estoque mudou desde a abertura da edição. Nenhuma alteração foi salva; reabra a edição para conferir os saldos atuais.")

    per_item_map = {str(s.id): s for s in (request.sizes or [])}
    fields = set(BatchProductFields.model_fields)
    clearable = {'description', 'brand', 'category', 'size', 'color', 'barcode', 'location', 'supplier_id', 'group_key'}
    def metadata(source):
        return {field: getattr(source, field) for field in source.model_fields_set & fields
                if getattr(source, field) is not None or field in clearable}
    shared = metadata(request)
    changes = {}
    for item in items:
        entry = per_item_map.get(str(item.id))
        if entry and entry.expected_updated_at is not None:
            def aware(value):
                return value if value.tzinfo else value.replace(tzinfo=settings.tz)
            if item.updated_at is None or aware(item.updated_at) != aware(entry.expected_updated_at):
                raise HTTPException(409, 'O cadastro mudou desde a abertura da edição. Nenhuma alteração foi salva; reabra para conferir.')
        values = _normalize_item({**shared, **(metadata(entry) if entry else {})})
        if 'group_key' in values and values['group_key'] != item.group_key and (
                not entry or entry.expected_updated_at is None):
            raise HTTPException(409, 'Reabra a edição para conferir o vínculo atual da grade.')
        if 'group_key' in values and values['group_key'] is not None and (
                not values['group_key'].strip() or len(values['group_key']) > 100):
            raise HTTPException(422, 'O nome da grade deve ter entre 1 e 100 caracteres.')
        if {'min_stock', 'max_stock'} & values.keys():
            minimum = values.get('min_stock', item.min_stock) or 0
            maximum = values.get('max_stock', item.max_stock) or 0
            if maximum and minimum > maximum:
                raise HTTPException(422, 'Mínimo não pode ser maior que máximo.')
        changes[item.id] = values
    # Keep the older mass editor safe too: it can still clear, create or change
    # a grade, but may not introduce two indistinguishable size/color variants.
    transfers = [(item, changes[item.id]['group_key']) for item in items
                 if 'group_key' in changes[item.id] and changes[item.id]['group_key'] != item.group_key]
    if any(target and not item.is_active for item, target in transfers):
        raise HTTPException(409, 'Ative o produto antes de vinculá-lo a uma grade.')
    def destination(item):
        return changes[item.id].get('group_key', item.group_key)
    affected = [(item, destination(item)) for item in items if destination(item) and (
        destination(item) != item.group_key or
        variant_identity(changes[item.id].get('size', item.size),
                         changes[item.id].get('color', item.color)) != variant_identity(item.size, item.color) or
        (not item.is_active and changes[item.id].get('is_active') is True))]
    targets = {target for _, target in affected}
    if targets:
        changed_ids = {item.id for item, _ in affected} | {item.id for item, _ in transfers}
        occupied = {}
        for row in db.query(Item.id, Item.group_key, Item.size, Item.color).filter(
                Item.deleted_at.is_(None),
                Item.group_key.in_(targets)).with_for_update().all():
            if row.id not in changed_ids:
                occupied.setdefault(row.group_key, set()).add(variant_identity(row.size, row.color))
        for item, target in affected:
            values = changes[item.id]
            identity = variant_identity(values.get('size', item.size), values.get('color', item.color))
            slot = occupied.setdefault(target, set())
            if identity in slot:
                raise HTTPException(409, 'A grade já contém esta combinação de tamanho e cor.')
            slot.add(identity)
    suppliers = {values['supplier_id'] for values in changes.values() if values.get('supplier_id')}
    if suppliers:
        existing_suppliers = {row[0] for row in db.query(Supplier.id).filter(Supplier.id.in_(suppliers)).all()}
        if suppliers != existing_suppliers:
            raise HTTPException(422, 'Fornecedor não encontrado.')
    # All metadata is validated before changing any product or recording a movement.
    for item in items:
        for field, value in changes[item.id].items():
            setattr(item, field, value)
        if request.image_data is not None:
            item.image_data = request.image_data

    # Metadata and stock changes share one transaction. A failed exit rolls back both.
    for item in items:
        entry = per_item_map.get(str(item.id))
        adjustment = adjustments.get(item.id)
        if adjustment:
            # Decrease first: moving counts between locations must not overflow
            # temporarily when the final total is within the column's limit.
            changes = [(loc, getattr(adjustment, f"stock_{loc}"), getattr(item, f"stock_{loc}"))
                       for loc in ("loja", "deposito")]
            try:
                for loc, quantity, previous in sorted(changes, key=lambda change: change[1] - change[2]):
                    if quantity != previous:
                        create_movement(
                            db=db, item_id=item.id, movement_type="adjustment", quantity=quantity,
                            reason=(adjustment.reason or request.stock_reason or "").strip() or "Conferência de estoque — edição em lote",
                            created_by=current_user.id, location=loc,
                        )
            except StockMovementError as error:
                db.rollback()
                raise HTTPException(error.status_code, str(error)) from None
            continue
        # Per-item delta takes precedence over shared delta
        if entry and entry.stock_delta is not None:
            delta = entry.stock_delta
            reason = (entry.stock_reason or request.stock_reason or "").strip() or "Ajuste de estoque — edição em lote"
        elif request.stock_delta is not None and request.stock_delta != 0:
            delta = request.stock_delta
            reason = (request.stock_reason or "").strip() or "Ajuste de estoque — edição em lote"
        else:
            continue
        if delta == 0:
            continue

        try:
            movement_type = "entry" if delta > 0 else "exit"
            create_movement(
                db=db,
                item_id=item.id,
                movement_type=movement_type,
                quantity=abs(delta),
                reason=reason,
                created_by=current_user.id,
                location="loja",
            )
        except StockMovementError as error:
            db.rollback()
            raise HTTPException(error.status_code, str(error)) from None
    if request.image_groups:
        # Flush metadata/stock before set-based photo writes. One bound image per
        # group avoids multiplying large driver buffers by the number of sizes.
        db.flush()
        from ...services.user_audit import record
        for group in request.image_groups:
            db.query(Item).filter(Item.id.in_(group.item_ids)).update({
                Item.image_data: group.image_data,
                Item.thumbnail_data: None,
                Item.thumbnail_ready: False,
            }, synchronize_session=False)
            if db.info.get('audit_enabled') and db.info.get('audit_actor'):
                for identity in group.item_ids:
                    record(db, 'update', 'inventory', entity='inventory_items', entity_id=str(identity),
                           changes={'image_data': {'changed': True}})
        # Keep preloaded identities coherent without loading their old photos.
        photo_ids = {identity for group in request.image_groups for identity in group.item_ids}
        for item in items:
            if item.id in photo_ids:
                db.expire(item, ['image_data', 'thumbnail_data', 'thumbnail_ready', 'updated_at'])
    db.commit()

    return {"message": f"Updated {len(items)} items", "count": len(items)}


@router.post("/items/transfer-bulk", status_code=200)
def bulk_transfer_items(
    request: BulkTransferRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Transfer stock between loja and depósito for multiple items at once."""
    if request.direction == "deposito_to_loja":
        loc_from, loc_to = "deposito", "loja"
    elif request.direction == "loja_to_deposito":
        loc_from, loc_to = "loja", "deposito"
    else:
        raise HTTPException(status_code=400, detail="Invalid direction. Use 'deposito_to_loja' or 'loja_to_deposito'")

    count = 0
    try:
        # Stable row-lock order and one transaction prevent partial transfers.
        for entry in sorted(request.items, key=lambda item: str(item.item_id)):
            create_movement(db=db, item_id=entry.item_id, movement_type="transfer",
                            quantity=entry.quantity, created_by=current_user.id,
                            reason=request.reason or f"Transferência {loc_from} → {loc_to}",
                            location_from=loc_from, location_to=loc_to)
            count += 1
        db.commit()
    except StockMovementError as error:
        db.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except ValueError as error:
        db.rollback()
        raise HTTPException(404, str(error)) from None
    return {"message": f"Transferred {count} items", "count": count}


@router.get('/items/{item_id}/history')
def get_product_history(item_id: str, section: Literal['movements', 'sales', 'counts', 'changes'] = 'movements',
                        page: int = Query(1, ge=1, le=20000), page_size: int = Query(20, ge=1, le=100),
                        db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
    return product_history(db, validate_uuid(item_id), current_user, section=section, page=page, page_size=page_size)


@router.post('/items/{item_id}/delete-from-catalog')
def remove_from_catalog(item_id: str, body: ItemDeletionConfirmation,
                        db: Session = Depends(get_db), owner: Usuario = Depends(require_owner)):
    result = delete_from_catalog(db, validate_uuid(item_id), owner, body)
    db.commit()
    return result


@router.get('/items/{item_id}/deletion-preview')
def preview_item_deletion(item_id: str, db: Session = Depends(get_db), owner: Usuario = Depends(require_owner)):
    return deletion_preview(db, validate_uuid(item_id), owner)


@router.delete('/items/{item_id}/permanent')
def permanently_delete(item_id: str, body: ItemDeletionConfirmation,
                       db: Session = Depends(get_db), owner: Usuario = Depends(require_owner)):
    result = permanently_delete_item(db, validate_uuid(item_id), owner, body)
    db.commit()
    return result


@router.delete("/items/{item_id}")
def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN"])),
):
    item_uuid = validate_uuid(item_id)
    db_item = db.query(Item).filter(Item.deleted_at.is_(None), Item.id == item_uuid).with_for_update().populate_existing().first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db_item.is_active = False
    db.commit()
    return {"message": "Item deactivated successfully"}


class QuickExitRequest(BaseModel):
    location: Optional[Literal["loja", "deposito"]] = "loja"

@router.post("/items/{item_id}/quick-exit")
def quick_exit(
    item_id: str,
    body: QuickExitRequest = Body(default_factory=QuickExitRequest),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    item_uuid = validate_uuid(item_id)
    location = body.location if body.location in ("loja", "deposito") else "loja"
    try:
        movement = create_movement(
            db=db,
            item_id=item_uuid,
            movement_type="exit",
            quantity=1,
            created_by=current_user.id,
            reason="Saída rápida",
            location=location,
        )
        db.commit()
    except StockMovementError as error:
        db.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "Quick exit registered", "new_stock": movement.quantity_after, "location": location}


# --- Movements ---------------------------------------------------------------

@router.post("/movements", response_model=MovementResponse, status_code=201)
def create_movement_endpoint(
    movement: MovementCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    try:
        mv = create_movement(
            db=db,
            item_id=movement.item_id,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            created_by=current_user.id,
            reason=movement.reason,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            unit_cost=movement.unit_cost,
            location=movement.location,
            location_from=movement.location_from,
            location_to=movement.location_to,
            notes=movement.notes,
        )
        db.commit()
        db.refresh(mv)
        return mv
    except StockMovementError as error:
        db.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/movements/batch", status_code=201)
def create_batch_movements(
    batch: BatchMovementCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    movements = []
    try:
        for item_data in sorted(batch.items, key=lambda item: str(item.item_id)):
            mv = create_movement(
                db=db,
                item_id=item_data.item_id,
                movement_type="entry",
                quantity=item_data.quantity,
                created_by=current_user.id,
                reason=batch.reason,
                unit_cost=item_data.unit_cost,
                notes=batch.notes,
            )
            movements.append(mv)
        db.commit()
    except StockMovementError as error:
        db.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": f"{len(movements)} movements created", "count": len(movements)}


@router.get("/movements", response_model=List[MovementResponse])
def list_movements(
    item_id: Optional[str] = Query(None),
    movement_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    query = db.query(StockMovement).options(joinedload(StockMovement.item).load_only(Item.name, Item.deleted_at))
    if item_id:
        item_uuid = validate_uuid(item_id, "item_id")
        query = query.filter(StockMovement.item_id == item_uuid)
    if movement_type:
        query = query.filter(StockMovement.movement_type == MovementType[movement_type])
    if date_from:
        query = query.filter(StockMovement.created_at >= date_from)
    if date_to:
        query = query.filter(StockMovement.created_at <= date_to)
    rows = query.order_by(StockMovement.created_at.desc()).offset(skip).limit(limit).all()
    return movement_read_responses(db, rows, current_user)


@router.get("/movements/item/{item_id}", response_model=List[MovementResponse])
def get_item_movements(
    item_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    item_uuid = validate_uuid(item_id)
    rows = (
        db.query(StockMovement)
        .options(joinedload(StockMovement.item).load_only(Item.name, Item.deleted_at))
        .filter(StockMovement.item_id == item_uuid)
        .order_by(StockMovement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return movement_read_responses(db, rows, current_user)


# --- Sessions ----------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    session: SessionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    db_session = InventorySession(**session.model_dump(), created_by=current_user.id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return _session_to_response(db_session)


@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    sessions = db.query(InventorySession).order_by(InventorySession.started_at.desc()).all()
    return [_session_to_response(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    session_uuid = validate_uuid(session_id)
    session = db.query(InventorySession).filter(InventorySession.id == session_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.put("/sessions/{session_id}/status")
def update_session_status(
    session_id: str,
    status_update: SessionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    session_uuid = validate_uuid(session_id)
    session = db.query(InventorySession).filter(InventorySession.id == session_uuid).with_for_update().populate_existing().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    target = SessionStatus[status_update.status]
    if session.status in (SessionStatus.applied, SessionStatus.cancelled):
        raise HTTPException(409, 'Sessões aplicadas ou canceladas não podem ser reabertas ou alteradas.')
    if target == SessionStatus.applied:
        raise HTTPException(409, 'Use a aplicação da contagem revisada para ajustar os saldos; o status não aplica estoque.')
    if session.count_location not in ('loja', 'deposito') and target != SessionStatus.cancelled:
        raise HTTPException(409, 'Contagem antiga sem local definido. Crie uma nova contagem indicando loja ou deposito; o histórico foi preservado.')
    transitions = {
        SessionStatus.open: {SessionStatus.counting, SessionStatus.cancelled},
        SessionStatus.counting: {SessionStatus.reviewing, SessionStatus.cancelled},
        SessionStatus.reviewing: {SessionStatus.counting, SessionStatus.cancelled},
    }
    if target != session.status and target not in transitions.get(session.status, set()):
        raise HTTPException(409, 'Transição de contagem inválida. Conte os produtos antes de enviar para revisão.')
    session.status = target
    session.finished_at = settings.now() if target in (SessionStatus.reviewing, SessionStatus.cancelled) else None
    db.commit()
    return {"message": "Status updated"}


@router.post("/sessions/{session_id}/scan", status_code=201)
def scan_item(
    session_id: str,
    scan: ScanItemCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    session_uuid = validate_uuid(session_id)
    session = db.query(InventorySession).filter(InventorySession.id == session_uuid).with_for_update().populate_existing().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.count_location not in ('loja', 'deposito'):
        raise HTTPException(409, 'Contagem antiga sem local definido. Crie uma nova contagem indicando loja ou deposito; o histórico foi preservado.')
    if session.status not in (SessionStatus.open, SessionStatus.counting):
        raise HTTPException(409, 'A sessão não está aberta para contagem. Sessões em revisão, aplicadas ou canceladas não recebem novas leituras.')

    item = db.query(Item).filter(Item.deleted_at.is_(None), Item.id == scan.item_id).with_for_update().populate_existing().first()
    if not item or not item.is_active:
        raise HTTPException(status_code=404, detail="Item not found")
    system_quantity = item.stock_loja if session.count_location == 'loja' else item.stock_deposito
    if system_quantity is None:
        raise HTTPException(409, 'O saldo deste local é desconhecido. Confira o cadastro antes de contar; nenhum valor foi presumido.')

    existing = (
        db.query(InventorySessionItem)
        .filter(
            InventorySessionItem.session_id == session_uuid,
            InventorySessionItem.item_id == scan.item_id,
        )
        .populate_existing().all()
    )
    if len(existing) > 1:
        raise HTTPException(409, 'Há contagens duplicadas deste produto na sessão. Crie uma nova contagem; o histórico foi preservado.')
    existing = existing[0] if existing else None
    if existing:
        existing.system_quantity = system_quantity
        existing.counted_quantity = scan.counted_quantity
        existing.scanned_at = settings.now()
        existing.counted_by = current_user.id
    else:
        session_item = InventorySessionItem(
            session_id=session_uuid,
            item_id=scan.item_id,
            system_quantity=system_quantity,
            counted_quantity=scan.counted_quantity,
            scanned_at=settings.now(),
            counted_by=current_user.id,
        )
        db.add(session_item)

    session.status = SessionStatus.counting
    db.commit()
    return {"message": "Item scanned successfully"}


@router.post("/sessions/{session_id}/apply")
def apply_session_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    session_uuid = validate_uuid(session_id)
    try:
        movements = apply_session(db=db, session_id=session_uuid, created_by=current_user.id)
    except StockMovementError as error:
        db.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": f"Session applied with {len(movements)} adjustments"}


def _session_to_response(session: InventorySession) -> SessionResponse:
    items = []
    for si in session.session_items:
        diff = None
        if si.counted_quantity is not None:
            diff = si.counted_quantity - si.system_quantity
        items.append(
            SessionItemResponse(
                id=si.id,
                session_id=si.session_id,
                item_id=si.item_id,
                system_quantity=si.system_quantity,
                counted_quantity=si.counted_quantity,
                difference=diff,
                scanned_at=si.scanned_at,
                counted_by=si.counted_by,
            )
        )
    return SessionResponse(
        id=session.id,
        name=session.name,
        count_location=session.count_location,
        status=session.status.value,
        location_filter=session.location_filter,
        category_filter=session.category_filter,
        notes=session.notes,
        started_at=session.started_at,
        finished_at=session.finished_at,
        applied_at=session.applied_at,
        created_by=session.created_by,
        approved_by=session.approved_by,
        session_items=items,
    )


# ─── Import: CSV ──────────────────────────────────────────────────────────────

@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Import inventory items from CSV.
    Columns (PT or EN accepted): name/nome, category/categoria, size/tamanho,
    color/cor, unit/unidade, barcode/codigo_barras, cost_price/custo,
    sale_price/preco_venda, currency/moeda, min_stock/estoque_minimo,
    max_stock/estoque_maximo, location/localizacao, initial_stock/estoque_inicial
    """
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except Exception:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    created, skipped, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or row.get("nome") or "").strip()
        if not name:
            skipped += 1
            continue
        try:
            sku = _generate_sku()
            while db.query(Item).filter(Item.sku_internal == sku).first():
                sku = _generate_sku()

            initial_stock = int(float(row.get("initial_stock") or row.get("estoque_inicial") or 0))
            if initial_stock < 0:
                raise ValueError("Estoque inicial não pode ser negativo.")
            unit_raw = (row.get("unit") or row.get("unidade") or "un").strip().lower()

            db_item = Item(
                name=name,
                description=(row.get("description") or row.get("descricao") or "").strip() or None,
                category=(row.get("category") or row.get("categoria") or "").strip() or None,
                size=(row.get("size") or row.get("tamanho") or "").strip() or None,
                color=(row.get("color") or row.get("cor") or "").strip() or None,
                unit=unit_raw or "un",
                location=(row.get("location") or row.get("localizacao") or "").strip() or None,
                barcode=(row.get("barcode") or row.get("codigo_barras") or "").strip() or None,
                sku_internal=sku,
                cost_price=float(str(row.get("cost_price") or row.get("custo") or 0).replace(",", ".")),
                sale_price=float(str(row.get("sale_price") or row.get("preco_venda") or 0).replace(",", ".")),
                currency=(row.get("currency") or row.get("moeda") or "USD").strip(),
                min_stock=int(float(row.get("min_stock") or row.get("estoque_minimo") or 0)),
                max_stock=int(float(row.get("max_stock") or row.get("estoque_maximo") or 0)),
                current_stock=initial_stock,
                stock_loja=initial_stock,
                stock_deposito=0,
                is_active=True,
                created_by=current_user.id,
            )
            db.add(db_item)
            db.flush()

            if initial_stock > 0:
                movement = StockMovement(
                    item_id=db_item.id,
                    movement_type=MovementType.entry,
                    quantity=initial_stock,
                    quantity_before=0,
                    quantity_after=initial_stock,
                    reason="Importação CSV",
                    created_by=current_user.id,
                )
                db.add(movement)

            created += 1
        except Exception as e:
            errors.append(f"Linha {i}: {str(e)}")
            skipped += 1

    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}


# ─── Import: NF-e XML ─────────────────────────────────────────────────────────

@router.post("/import/nfe")
async def import_nfe(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    currency: str = Form("BRL"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Import inventory items from Brazilian NF-e XML.

    xProd parsing: first 2 words = item name, remaining words = color field.
    """
    content = await file.read()
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"XML inválido: {str(e)}")

    # Detect namespace
    ns = ""
    tag = root.tag
    if tag.startswith("{"):
        ns = tag[1:tag.index("}")]

    def _find(node, path):
        if ns:
            return node.find("/".join(f"{{{ns}}}{p}" for p in path.split("/")))
        return node.find(path)

    def _findall(node, path):
        if ns:
            return node.findall("/".join(f"{{{ns}}}{p}" for p in path.split("/")))
        return node.findall(path)

    def _txt(node, tag_name, default=""):
        el = _find(node, tag_name)
        return el.text.strip() if el is not None and el.text else default

    def _parse_xprod(xprod: str):
        """Split xProd into (name, color). First 2 words = name, rest = color."""
        words = xprod.split()
        if len(words) <= 2:
            return xprod, None
        name = " ".join(words[:2])
        color = " ".join(words[2:]).title()
        return name, color

    infnfe = _find(root, "NFe/infNFe") or _find(root, "infNFe") or root
    dets = _findall(infnfe, "det")
    if not dets:
        dets = root.findall(f".//{{{ns}}}det" if ns else ".//det")

    if not dets:
        raise HTTPException(status_code=400, detail="Nenhum item encontrado no XML da NF-e")

    # Auto-map unit based on category
    category_unit = "par" if category and "cal" in category.lower() else "un"

    created, skipped, errors = 0, 0, []

    for det in dets:
        prod = _find(det, "prod")
        if prod is None:
            skipped += 1
            continue
        try:
            xprod_raw = _txt(prod, "xProd")
            if not xprod_raw:
                skipped += 1
                continue

            name, color = _parse_xprod(xprod_raw)

            barcode = _txt(prod, "cEAN")
            if barcode in ("SEM GTIN", "SEMGTIN", ""):
                barcode = None

            unit_raw = _txt(prod, "uCom", "").upper()
            if unit_raw in ("PAR", "PR"):
                unit = "par"
            else:
                unit = category_unit

            initial_stock = int(float(_txt(prod, "qCom", "0").replace(",", ".")))
            if initial_stock < 0:
                raise ValueError("Estoque inicial não pode ser negativo.")
            cost_price = float(_txt(prod, "vUnCom", "0").replace(",", "."))

            sku = _generate_sku()
            while db.query(Item).filter(Item.sku_internal == sku).first():
                sku = _generate_sku()

            db_item = Item(
                name=name,
                color=color,
                category=category or None,
                barcode=barcode,
                unit=unit,
                sku_internal=sku,
                cost_price=cost_price,
                sale_price=cost_price,
                currency=currency,
                current_stock=initial_stock,
                stock_loja=initial_stock,
                stock_deposito=0,
                is_active=True,
                created_by=current_user.id,
            )
            db.add(db_item)
            db.flush()

            if initial_stock > 0:
                movement = StockMovement(
                    item_id=db_item.id,
                    movement_type=MovementType.entry,
                    quantity=initial_stock,
                    quantity_before=0,
                    quantity_after=initial_stock,
                    reason="Importação NF-e",
                    unit_cost=cost_price if cost_price > 0 else None,
                    created_by=current_user.id,
                )
                db.add(movement)

            created += 1
        except Exception as e:
            errors.append(f"Item {det.get('nItem', '?')}: {str(e)}")
            skipped += 1

    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}
