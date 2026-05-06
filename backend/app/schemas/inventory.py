from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import uuid


class SupplierBase(BaseModel):
    name: str
    contact: Optional[str] = None
    is_active: Optional[bool] = True


class SupplierCreate(SupplierBase):
    pass


class SupplierResponse(SupplierBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    unit: Optional[str] = "un"
    location: Optional[str] = None
    barcode: Optional[str] = None
    supplier_id: Optional[uuid.UUID] = None
    cost_price: Optional[Decimal] = Decimal("0")
    sale_price: Optional[Decimal] = Decimal("0")
    currency: Optional[str] = "PYG"
    cost_currency: Optional[str] = "BRL"
    sale_currency: Optional[str] = "USD"
    min_stock: Optional[int] = 0
    max_stock: Optional[int] = 0
    is_active: Optional[bool] = True
    image_data: Optional[str] = None
    brand: Optional[str] = None
    group_key: Optional[str] = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(ItemBase):
    name: Optional[str] = None


class ItemResponse(ItemBase):
    id: uuid.UUID
    sku_internal: str
    current_stock: int
    stock_loja: int = 0
    stock_deposito: int = 0
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    alert_level: Optional[str] = None
    image_data: Optional[str] = None

    class Config:
        from_attributes = True


class ItemListResponse(BaseModel):
    items: List[ItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class GroupItemsRequest(BaseModel):
    item_ids: List[uuid.UUID]
    group_key: str


class RenameGroupRequest(BaseModel):
    old_key: str
    new_key: str


class UngroupRequest(BaseModel):
    group_key: str


class BatchSizeEntry(BaseModel):
    id: uuid.UUID
    size: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None
    barcode: Optional[str] = None
    cost_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    stock_delta: Optional[int] = None    # positive=entry, negative=exit
    stock_reason: Optional[str] = None  # required if stock_delta != 0


class BatchEditRequest(BaseModel):
    item_ids: List[uuid.UUID]
    # Shared fields — only applied when not None
    brand: Optional[str] = None
    category: Optional[str] = None
    image_data: Optional[str] = None
    cost_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    currency: Optional[str] = None
    stock_delta: Optional[int] = None    # applied to all items without per-item override
    stock_reason: Optional[str] = None
    # Per-item fields (optional)
    sizes: Optional[List[BatchSizeEntry]] = None


class GroupResponse(BaseModel):
    group_key: str
    items: List[ItemResponse]
    total_stock: int


class SuggestionResponse(BaseModel):
    name: str
    items: List[ItemResponse]


class MovementBase(BaseModel):
    item_id: uuid.UUID
    movement_type: str
    quantity: int
    reason: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    location: Optional[str] = "loja"
    location_from: Optional[str] = None
    location_to: Optional[str] = None
    notes: Optional[str] = None


class MovementCreate(MovementBase):
    pass


class BatchMovementItem(BaseModel):
    item_id: uuid.UUID
    quantity: int
    unit_cost: Optional[Decimal] = None


class BatchMovementCreate(BaseModel):
    items: List[BatchMovementItem]
    reason: Optional[str] = None
    notes: Optional[str] = None


class MovementResponse(MovementBase):
    id: uuid.UUID
    quantity_before: int
    quantity_after: int
    created_at: datetime
    created_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


class SessionBase(BaseModel):
    name: str
    location_filter: Optional[str] = None
    category_filter: Optional[str] = None
    notes: Optional[str] = None


class SessionCreate(SessionBase):
    pass


class SessionStatusUpdate(BaseModel):
    status: str


class ScanItemCreate(BaseModel):
    item_id: uuid.UUID
    counted_quantity: int


class SessionItemResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    item_id: uuid.UUID
    system_quantity: int
    counted_quantity: Optional[int] = None
    difference: Optional[int] = None
    scanned_at: Optional[datetime] = None
    counted_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


class SessionResponse(SessionBase):
    id: uuid.UUID
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    approved_by: Optional[uuid.UUID] = None
    session_items: List[SessionItemResponse] = []

    class Config:
        from_attributes = True


class AlertSummary(BaseModel):
    low_stock_count: int
    out_of_stock_count: int
    overstocked_count: int
    total_active_items: int
    inactive_count: int = 0
    group_count: int = 0        # distinct groups
    grouped_items_count: int = 0  # items that belong to a group
    loja_count: int = 0          # active items with stock_loja > 0
    deposito_count: int = 0      # active items with stock_deposito > 0


class GradeCreateRequest(BaseModel):
    """Create a group of items (grade) all at once from a base product + list of sizes."""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    unit: Optional[str] = "un"
    location: Optional[str] = None
    base_barcode: Optional[str] = None   # barcode prefix; each item gets base_barcode+size
    supplier_id: Optional[uuid.UUID] = None
    cost_price: Optional[Decimal] = Decimal("0")
    sale_price: Optional[Decimal] = Decimal("0")
    currency: Optional[str] = "PYG"
    cost_currency: Optional[str] = "BRL"
    sale_currency: Optional[str] = "USD"
    min_stock: Optional[int] = 0
    max_stock: Optional[int] = 0
    image_data: Optional[str] = None
    group_key: Optional[str] = None      # auto-generated from name+color if None
    sizes: List[str]                     # e.g. ["P","M","G","GG"] or ["38","39","40"]
    initial_stock: Optional[int] = 0    # entry movement created for each item if > 0
    stock_location: Optional[str] = "loja"  # "loja" or "deposito"


class GradeCreateResponse(BaseModel):
    group_key: str
    items: List[ItemResponse]
    total_created: int


class BulkTransferItem(BaseModel):
    item_id: uuid.UUID
    quantity: int


class BulkTransferRequest(BaseModel):
    items: List[BulkTransferItem]
    direction: str   # "deposito_to_loja" | "loja_to_deposito"
    reason: Optional[str] = None
