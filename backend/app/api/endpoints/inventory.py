from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import List, Optional
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
    BatchEditRequest, BatchSizeEntry, GradeCreateRequest, GradeCreateResponse,
    BulkTransferRequest,
)
from ...dependencies import get_current_active_user, require_role
from ...services.inventory_service import create_movement, apply_session, _compute_alert_level
from ..validators import validate_uuid
from datetime import datetime as dt

router = APIRouter()

# ── Text normalization ────────────────────────────────────────────────────────
def _title_case(value: Optional[str]) -> Optional[str]:
    """Normalize to Title Case: 'PRADA' → 'Prada', 'branco' → 'Branco'."""
    if not value:
        return value
    return ' '.join(word.capitalize() for word in value.strip().split())

def _normalize_item(data: dict) -> dict:
    """Apply Title Case to text fields before persisting."""
    for field in ('name', 'brand', 'color', 'category'):
        if field in data and data[field]:
            data[field] = _title_case(data[field])
    return data

# ── Size ordering ─────────────────────────────────────────────────────────────
_LETTER_SIZES = ["PP", "P", "M", "G", "GG", "XG", "XGG", "XXG", "XXXG", "U"]
_LETTER_SIZE_ORDER = {s: i for i, s in enumerate(_LETTER_SIZES)}

def _size_sort_key(size):
    """Returns a tuple for correct size ordering: numeric < letter < unknown < null."""
    if size is None:
        return (3, 0.0, "")
    s = size.strip().upper()
    if s in _LETTER_SIZE_ORDER:
        return (1, float(_LETTER_SIZE_ORDER[s]), s)
    try:
        return (0, float(s), s)
    except ValueError:
        return (2, 0.0, s)


def _generate_sku() -> str:
    date_part = dt.now().strftime("%Y%m%d")
    rand_part = uuid.uuid4().hex[:4].upper()
    return f"INV-{date_part}-{rand_part}"


def _item_to_response(item: Item) -> dict:
    data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    data["alert_level"] = _compute_alert_level(item)
    return data


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

@router.get("/items/distinct-values")
def get_distinct_values(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    brands = db.query(Item.brand).filter(Item.brand.isnot(None), Item.brand != '').distinct().all()
    categories = db.query(Item.category).filter(Item.category.isnot(None), Item.category != '').distinct().all()
    return {
        "brands": sorted([b[0] for b in brands]),
        "categories": sorted([c[0] for c in categories]),
    }


@router.get("/items", response_model=ItemListResponse)
def list_items(
    search: Optional[str] = Query(None),
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
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    query = db.query(Item)

    if search:
        for token in search.strip().split():
            like = f"%{token}%"
            query = query.filter(
                or_(
                    Item.name.ilike(like),
                    Item.sku_internal.ilike(like),
                    Item.barcode.ilike(like),
                    Item.category.ilike(like),
                    Item.brand.ilike(like),
                    Item.color.ilike(like),
                    Item.group_key.ilike(like),
                )
            )
    if category:
        query = query.filter(Item.category.ilike(f"%{category}%"))
    if brand:
        query = query.filter(Item.brand.ilike(f"%{brand}%"))
    if location:
        query = query.filter(Item.location.ilike(f"%{location}%"))
    if size:
        query = query.filter(Item.size == size)
    if color:
        query = query.filter(Item.color.ilike(f"%{color}%"))
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
    if item_status == "low_stock":
        query = query.filter(Item.is_active == True, Item.current_stock > 0, Item.current_stock < Item.min_stock)
    elif item_status == "out_of_stock":
        query = query.filter(Item.is_active == True, Item.current_stock <= 0)
    elif item_status == "overstocked":
        query = query.filter(Item.is_active == True, Item.max_stock > 0, Item.current_stock > Item.max_stock)
    elif item_status == "inactive":
        query = query.filter(Item.is_active == False)
    else:
        pass  # no filter, show all

    total = query.count()
    offset = (page - 1) * page_size
    if sort_by == "updated_at":
        items = query.order_by(Item.updated_at.desc()).offset(offset).limit(page_size).all()
    elif sort_by == "created_at":
        items = query.order_by(Item.created_at.desc()).offset(offset).limit(page_size).all()
    else:
        items = query.order_by(Item.name, Item.color, Item.size).offset(offset).limit(page_size).all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    item_responses = []
    for item in items:
        resp = ItemResponse.model_validate(item)
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
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    items = db.query(Item).filter(Item.barcode == code, Item.is_active == True).all()
    result = []
    for item in items:
        resp = ItemResponse.model_validate(item)
        resp.alert_level = _compute_alert_level(item)
        result.append(resp)
    return result


@router.get("/alerts/summary", response_model=AlertSummary)
def get_alerts_summary(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    from sqlalchemy import func as sqlfunc
    active_items = db.query(Item).filter(Item.is_active == True).all()
    low_stock = sum(1 for i in active_items if 0 < i.current_stock < i.min_stock)
    out_of_stock = sum(1 for i in active_items if i.current_stock <= 0)
    overstocked = sum(1 for i in active_items if i.max_stock > 0 and i.current_stock > i.max_stock)
    inactive_count = db.query(Item).filter(Item.is_active == False).count()
    grouped_items_count = sum(1 for i in active_items if i.group_key)
    group_count = db.query(Item.group_key).filter(
        Item.group_key.isnot(None), Item.is_active == True
    ).distinct().count()
    loja_count = sum(1 for i in active_items if (i.stock_loja or 0) > 0)
    deposito_count = sum(1 for i in active_items if (i.stock_deposito or 0) > 0)
    return AlertSummary(
        low_stock_count=low_stock,
        out_of_stock_count=out_of_stock,
        overstocked_count=overstocked,
        total_active_items=len(active_items),
        inactive_count=inactive_count,
        group_count=group_count,
        grouped_items_count=grouped_items_count,
        loja_count=loja_count,
        deposito_count=deposito_count,
    )


@router.get("/groups", response_model=List[GroupResponse])
def get_groups(
    search: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    item_status: Optional[str] = Query(None, alias="status"),
    location_stock: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Returns all groups with their items from DB, with optional filters.
    Filters are applied at the group level: a group is included if at least
    one of its items matches the filter criteria."""

    # Step 1: Find group_keys that pass extra filters (brand/category/status/location)
    # A group is included if ANY item matches — then ALL items of that group are shown.
    filter_keys: Optional[set] = None
    if brand or category or item_status or location_stock:
        kq = db.query(Item.group_key).filter(
            Item.group_key.isnot(None),
            Item.is_active == True,
        )
        if brand:
            kq = kq.filter(Item.brand.ilike(f"%{brand}%"))
        if category:
            kq = kq.filter(Item.category.ilike(f"%{category}%"))
        if item_status == "low_stock":
            kq = kq.filter(Item.current_stock > 0, Item.current_stock < Item.min_stock)
        elif item_status == "out_of_stock":
            kq = kq.filter(Item.current_stock <= 0)
        elif item_status == "overstocked":
            kq = kq.filter(Item.max_stock > 0, Item.current_stock > Item.max_stock)
        if location_stock == "loja":
            kq = kq.filter(Item.stock_loja > 0)
        elif location_stock == "deposito":
            kq = kq.filter(Item.stock_deposito > 0)
        filter_keys = {r[0] for r in kq.distinct().all()}
        if not filter_keys:
            return []

    # Step 2: Find group_keys that match search tokens
    search_keys: Optional[set] = None
    if search:
        tokens = [t for t in search.strip().split() if t]
        for token in tokens:
            like = f"%{token}%"
            rows = (
                db.query(Item.group_key)
                .filter(
                    Item.group_key.isnot(None),
                    Item.is_active == True,
                    or_(
                        Item.group_key.ilike(like),
                        Item.name.ilike(like),
                        Item.barcode.ilike(like),
                        Item.brand.ilike(like),
                        Item.category.ilike(like),
                        Item.sku_internal.ilike(like),
                        Item.color.ilike(like),
                    ),
                )
                .distinct()
                .all()
            )
            token_keys = {r[0] for r in rows}
            search_keys = token_keys if search_keys is None else search_keys & token_keys
        if not search_keys:
            return []

    # Step 3: Intersect filter_keys and search_keys
    if filter_keys is not None and search_keys is not None:
        matching_keys: Optional[list] = list(filter_keys & search_keys)
    elif filter_keys is not None:
        matching_keys = list(filter_keys)
    elif search_keys is not None:
        matching_keys = list(search_keys)
    else:
        matching_keys = None  # no filter → all groups

    if matching_keys is not None and not matching_keys:
        return []

    # Step 4: Load all items from matching groups
    item_query = db.query(Item).filter(Item.group_key.isnot(None), Item.is_active == True)
    if matching_keys is not None:
        item_query = item_query.filter(Item.group_key.in_(matching_keys))
    items = item_query.order_by(Item.group_key, Item.name).all()

    # Step 5: Build GroupResponse objects
    groups_dict: dict = {}
    for item in items:
        key = item.group_key
        if key not in groups_dict:
            groups_dict[key] = []
        resp = ItemResponse.model_validate(item)
        resp.alert_level = _compute_alert_level(item)
        groups_dict[key].append(resp)

    result = []
    for key, item_list in groups_dict.items():
        sorted_items = sorted(item_list, key=lambda i: _size_sort_key(i.size))
        total_stock = sum(i.current_stock for i in sorted_items)
        result.append(GroupResponse(group_key=key, items=sorted_items, total_stock=total_stock))
    return result


@router.patch("/groups", status_code=200)
def rename_group(
    body: RenameGroupRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Rename a group — updates group_key on all items in the group without touching item names"""
    old_key = body.old_key.strip()
    new_key = body.new_key.strip()
    if not new_key:
        raise HTTPException(status_code=400, detail="O nome do grupo não pode ser vazio")
    if new_key == old_key:
        return {"message": "Nenhuma alteração", "count": 0}
    items = db.query(Item).filter(Item.group_key == old_key).all()
    if not items:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    for item in items:
        item.group_key = new_key
    db.commit()
    return {"message": f"Grupo renomeado de '{old_key}' para '{new_key}'", "count": len(items)}


@router.get("/suggestions", response_model=List[SuggestionResponse])
def get_suggestions(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Returns grouping suggestions based on ALL ungrouped active items in DB"""
    items = (
        db.query(Item)
        .filter(Item.group_key == None, Item.is_active == True)
        .order_by(Item.name)
        .all()
    )
    # key = (base_name, normalized_color) so different colors stay as separate groups
    map_: dict = {}
    for item in items:
        base = re.sub(r'\s+(PP|P|M|G|GG|XG|XGG|XXG|XXX|XXXG|\d+)\s*$', '', item.name, flags=re.IGNORECASE).strip()
        if len(base) < 4:
            continue
        color_key = (item.color or '').strip().upper()
        # Suggestion name shown to user: base + color if color is in the separate field
        suggestion_name = f"{base} {item.color.strip()}".strip() if item.color and item.color.strip() else base
        group_key = (base, color_key)
        if group_key not in map_:
            map_[group_key] = {'name': suggestion_name, 'items': []}
        resp = ItemResponse.model_validate(item)
        resp.alert_level = _compute_alert_level(item)
        map_[group_key]['items'].append(resp)

    return [
        SuggestionResponse(name=v['name'], items=v['items'])
        for v in sorted(map_.values(), key=lambda x: len(x['items']), reverse=True)
        if len(v['items']) >= 2
    ]


@router.get("/items/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    item_uuid = validate_uuid(item_id)
    item = db.query(Item).filter(Item.id == item_uuid).first()
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
    db_item = db.query(Item).filter(Item.id == item_uuid).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = _normalize_item(item_update.dict(exclude_unset=True))
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
    items = db.query(Item).filter(Item.id.in_(request.item_ids)).all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")
    for item in items:
        item.group_key = request.group_key
    db.commit()
    return {"message": f"Grouped {len(items)} items", "count": len(items)}


@router.post("/items/grade", response_model=GradeCreateResponse, status_code=201)
def create_grade(
    grade: GradeCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    """Create a full size grid (grade) — one item per size, all sharing the same group_key."""
    sizes = [s.strip() for s in grade.sizes if s.strip()]
    if not sizes:
        raise HTTPException(status_code=400, detail="Informe ao menos um tamanho para criar a grade")

    # Normalize text fields
    norm_name     = _title_case(grade.name)     or grade.name
    norm_color    = _title_case(grade.color)    if grade.color else None
    norm_brand    = _title_case(grade.brand)    if grade.brand else None
    norm_category = _title_case(grade.category) if grade.category else None

    # Auto-generate group_key from name + color
    group_key = (grade.group_key or "").strip()
    if not group_key:
        color_part = f" {norm_color}" if norm_color else ""
        group_key = f"{norm_name.strip()}{color_part}"

    created_items: list[Item] = []
    for size in sizes:
        # Barcode: base_barcode + size (e.g. "7891234P" or "789123438")
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Erro ao criar grade — possível conflito de SKU")

    for item in created_items:
        db.refresh(item)

    # Create initial stock movements if requested
    if grade.initial_stock and grade.initial_stock > 0:
        stock_loc = grade.stock_location or "loja"
        for item in created_items:
            create_movement(
                db=db,
                item_id=item.id,
                movement_type="entry",
                quantity=grade.initial_stock,
                reason="Estoque inicial — criação de grade",
                created_by=current_user.id,
                location=stock_loc,
            )
        db.commit()
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
    current_user: Usuario = Depends(get_current_active_user),
):
    items = db.query(Item).filter(Item.group_key == body.group_key).all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found with this group_key")
    for item in items:
        item.group_key = None
    db.commit()
    return {"message": f"Ungrouped {len(items)} items", "count": len(items)}


@router.delete("/items/{item_id}/group", status_code=200)
def remove_item_from_group(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Remove a single item from its group (set group_key to None)"""
    item_uuid = validate_uuid(item_id)
    item = db.query(Item).filter(Item.id == item_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not item.group_key:
        raise HTTPException(status_code=400, detail="Item is not in any group")
    item.group_key = None
    db.commit()
    return {"message": "Item removed from group"}


@router.patch("/items/batch", status_code=200)
def batch_edit_items(
    request: BatchEditRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Bulk edit shared fields (brand, category, image, prices) and per-item fields (name, color, barcode, prices, stock)"""
    items = db.query(Item).filter(Item.id.in_(request.item_ids)).all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    # Validate stock reasons
    if request.stock_delta and request.stock_delta != 0 and not request.stock_reason:
        raise HTTPException(status_code=422, detail="Motivo é obrigatório para ajuste de estoque compartilhado")
    for entry in (request.sizes or []):
        if entry.stock_delta and entry.stock_delta != 0 and not entry.stock_reason:
            raise HTTPException(status_code=422, detail=f"Motivo é obrigatório para ajuste de estoque do item {entry.id}")

    per_item_map = {str(s.id): s for s in (request.sizes or [])}

    for item in items:
        # Shared fields
        if request.brand is not None:
            item.brand = request.brand
        if request.category is not None:
            item.category = request.category
        if request.image_data is not None:
            item.image_data = request.image_data
        if request.cost_price is not None:
            item.cost_price = request.cost_price
        if request.sale_price is not None:
            item.sale_price = request.sale_price
        if request.currency is not None:
            item.currency = request.currency
        # Per-item fields
        entry = per_item_map.get(str(item.id))
        if entry:
            if entry.size is not None:
                item.size = entry.size
            if entry.name is not None:
                item.name = entry.name
            if entry.color is not None:
                item.color = entry.color
            if entry.barcode is not None:
                item.barcode = entry.barcode
            if entry.cost_price is not None:
                item.cost_price = entry.cost_price
            if entry.sale_price is not None:
                item.sale_price = entry.sale_price

    db.commit()

    # Stock adjustments — run after main commit so item state is persisted
    has_stock_changes = False
    for item in items:
        entry = per_item_map.get(str(item.id))
        # Per-item delta takes precedence over shared delta
        if entry and entry.stock_delta is not None and entry.stock_delta != 0:
            delta = entry.stock_delta
            reason = entry.stock_reason or "Ajuste massivo"
        elif request.stock_delta is not None and request.stock_delta != 0:
            delta = request.stock_delta
            reason = request.stock_reason or "Ajuste massivo"
        else:
            continue

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
        has_stock_changes = True

    if has_stock_changes:
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
    for entry in request.items:
        if entry.quantity <= 0:
            continue
        try:
            create_movement(
                db=db,
                item_id=entry.item_id,
                movement_type="transfer",
                quantity=entry.quantity,
                created_by=current_user.id,
                reason=request.reason or f"Transferência {loc_from} → {loc_to}",
                location_from=loc_from,
                location_to=loc_to,
            )
            count += 1
        except ValueError:
            continue

    db.commit()
    return {"message": f"Transferred {count} items", "count": count}


@router.delete("/items/{item_id}")
def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN"])),
):
    item_uuid = validate_uuid(item_id)
    db_item = db.query(Item).filter(Item.id == item_uuid).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db_item.is_active = False
    db.commit()
    return {"message": "Item deactivated successfully"}


@router.post("/items/{item_id}/quick-exit")
def quick_exit(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    item_uuid = validate_uuid(item_id)
    try:
        movement = create_movement(
            db=db,
            item_id=item_uuid,
            movement_type="exit",
            quantity=1,
            created_by=current_user.id,
            reason="Saída rápida",
            location="loja",
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "Quick exit registered", "new_stock": movement.quantity_after}


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
        for item_data in batch.items:
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
    query = db.query(StockMovement)
    if item_id:
        item_uuid = validate_uuid(item_id, "item_id")
        query = query.filter(StockMovement.item_id == item_uuid)
    if movement_type:
        query = query.filter(StockMovement.movement_type == MovementType[movement_type])
    if date_from:
        query = query.filter(StockMovement.created_at >= date_from)
    if date_to:
        query = query.filter(StockMovement.created_at <= date_to)
    return query.order_by(StockMovement.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/movements/item/{item_id}", response_model=List[MovementResponse])
def get_item_movements(
    item_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    item_uuid = validate_uuid(item_id)
    return (
        db.query(StockMovement)
        .filter(StockMovement.item_id == item_uuid)
        .order_by(StockMovement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# --- Sessions ----------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    session: SessionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    db_session = InventorySession(**session.dict(), created_by=current_user.id)
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
    session = db.query(InventorySession).filter(InventorySession.id == session_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        session.status = SessionStatus[status_update.status]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status_update.status}")
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
    session = db.query(InventorySession).filter(InventorySession.id == session_uuid).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    item = db.query(Item).filter(Item.id == scan.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = (
        db.query(InventorySessionItem)
        .filter(
            InventorySessionItem.session_id == session_uuid,
            InventorySessionItem.item_id == scan.item_id,
        )
        .first()
    )

    if existing:
        existing.counted_quantity = scan.counted_quantity
        existing.scanned_at = settings.now()
        existing.counted_by = current_user.id
    else:
        session_item = InventorySessionItem(
            session_id=session_uuid,
            item_id=scan.item_id,
            system_quantity=item.current_stock,
            counted_quantity=scan.counted_quantity,
            scanned_at=settings.now(),
            counted_by=current_user.id,
        )
        db.add(session_item)

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
