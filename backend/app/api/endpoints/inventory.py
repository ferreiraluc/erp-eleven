from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime, date
import uuid
import io
import csv
import xml.etree.ElementTree as ET

from ...database import get_db
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
)
from ...dependencies import get_current_active_user, require_role
from ...services.inventory_service import create_movement, apply_session, _compute_alert_level
from ..validators import validate_uuid
from datetime import datetime as dt

router = APIRouter()


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

@router.get("/items", response_model=ItemListResponse)
def list_items(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    item_status: Optional[str] = Query(None, alias="status"),
    supplier_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    query = db.query(Item)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Item.name.ilike(like),
                Item.sku_internal.ilike(like),
                Item.barcode.ilike(like),
                Item.category.ilike(like),
            )
        )
    if category:
        query = query.filter(Item.category.ilike(f"%{category}%"))
    if location:
        query = query.filter(Item.location.ilike(f"%{location}%"))
    if size:
        query = query.filter(Item.size == size)
    if color:
        query = query.filter(Item.color.ilike(f"%{color}%"))
    if supplier_id:
        sup_uuid = validate_uuid(supplier_id, "supplier_id")
        query = query.filter(Item.supplier_id == sup_uuid)

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
    items = query.order_by(Item.name).offset(offset).limit(page_size).all()

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

    db_item = Item(**item.dict(), sku_internal=sku, created_by=current_user.id)
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
    active_items = db.query(Item).filter(Item.is_active == True).all()
    low_stock = sum(1 for i in active_items if 0 < i.current_stock < i.min_stock)
    out_of_stock = sum(1 for i in active_items if i.current_stock <= 0)
    overstocked = sum(1 for i in active_items if i.max_stock > 0 and i.current_stock > i.max_stock)
    return AlertSummary(
        low_stock_count=low_stock,
        out_of_stock_count=out_of_stock,
        overstocked_count=overstocked,
        total_active_items=len(active_items),
    )


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

    for field, value in item_update.dict(exclude_unset=True).items():
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


@router.post("/items/ungroup/{group_key_value}")
def ungroup_items(
    group_key_value: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"])),
):
    items = db.query(Item).filter(Item.group_key == group_key_value).all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found with this group_key")
    for item in items:
        item.group_key = None
    db.commit()
    return {"message": f"Ungrouped {len(items)} items", "count": len(items)}


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
        existing.scanned_at = datetime.utcnow()
        existing.counted_by = current_user.id
    else:
        session_item = InventorySessionItem(
            session_id=session_uuid,
            item_id=scan.item_id,
            system_quantity=item.current_stock,
            counted_quantity=scan.counted_quantity,
            scanned_at=datetime.utcnow(),
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
