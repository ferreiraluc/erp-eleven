from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Literal, Annotated
from datetime import datetime
from decimal import Decimal
import uuid
from .product_gallery import GalleryInput


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


class ItemCreate(ItemBase, GalleryInput):
    pass


class ItemUpdate(ItemBase, GalleryInput):
    name: Optional[str] = None


class ItemResponse(ItemBase):
    has_image: bool | None = None
    id: uuid.UUID
    sku_internal: str
    inventory_code: str | None = None
    current_stock: int | None
    stock_loja: int | None
    stock_deposito: int | None
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


class RelatedItem(BaseModel):
    item: ItemResponse
    relation: Literal['family', 'brand_category', 'brand', 'category']


class RelatedCursor(BaseModel):
    after_rank: int
    after_id: uuid.UUID


class RelatedItemsResponse(BaseModel):
    items: List[RelatedItem]
    next_cursor: RelatedCursor | None = None


class GroupItemsRequest(BaseModel):
    item_ids: List[uuid.UUID]
    group_key: str


class RenameGroupRequest(BaseModel):
    old_key: str
    new_key: str


class UngroupRequest(BaseModel):
    group_key: str


class BatchProductFields(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    size: Optional[str] = Field(default=None, max_length=50)
    color: Optional[str] = Field(default=None, max_length=50)
    barcode: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=20)
    location: Optional[str] = Field(default=None, max_length=100)
    supplier_id: Optional[uuid.UUID] = None
    group_key: Optional[str] = Field(default=None, max_length=100)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, le=Decimal('9999999999.99'))
    sale_price: Optional[Decimal] = Field(default=None, ge=0, le=Decimal('9999999999.99'))
    currency: Optional[Literal['PYG', 'USD', 'BRL', 'EUR']] = None
    cost_currency: Optional[Literal['PYG', 'USD', 'BRL', 'EUR']] = None
    sale_currency: Optional[Literal['PYG', 'USD', 'BRL', 'EUR']] = None
    min_stock: Optional[Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]] = None
    max_stock: Optional[Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]] = None
    is_active: Optional[bool] = None

    @field_validator('name', 'unit')
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError('Este campo não pode ficar vazio.')
        return value


class BatchSizeEntry(BatchProductFields):
    id: uuid.UUID
    expected_updated_at: Optional[datetime] = None
    stock_delta: Optional[int] = None    # positive=entry, negative=exit
    stock_reason: Optional[str] = None


StockCount = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]


class BatchStockAdjustment(BaseModel):
    id: uuid.UUID
    stock_loja: StockCount
    stock_deposito: StockCount
    expected_loja: StockCount
    expected_deposito: StockCount
    expected_total: StockCount
    reason: Optional[str] = None

    @model_validator(mode="after")
    def valid_total(self):
        if self.stock_loja + self.stock_deposito > 2_147_483_647:
            raise ValueError("O total resultante excede o limite permitido.")
        return self


class BatchPhotoAssignment(BaseModel):
    item_ids: List[uuid.UUID] = Field(min_length=1, max_length=2000)
    image_data: str = Field(max_length=340000)

    @field_validator('image_data')
    @classmethod
    def valid_photo(cls, value):
        # Same decoded format, dimensions and byte limits as the product gallery.
        GalleryInput(additional_images=[value])
        return value


class BatchEditRequest(BatchProductFields):
    item_ids: List[uuid.UUID]
    # Omitted metadata stays unchanged; explicit null clears optional text/FKs.
    image_data: Optional[str] = None
    image_groups: List[BatchPhotoAssignment] = Field(default_factory=list, max_length=20)
    stock_delta: Optional[int] = None    # applied to all items without per-item override
    stock_reason: Optional[str] = None
    # Per-item fields (optional)
    sizes: Optional[List[BatchSizeEntry]] = None
    stock_adjustments: Optional[List[BatchStockAdjustment]] = None

    @model_validator(mode="after")
    def validate_selection(self):
        selected = set(self.item_ids)
        if not selected or len(selected) != len(self.item_ids):
            raise ValueError("Selecione produtos distintos para editar.")
        for entries in (self.sizes or [], self.stock_adjustments or []):
            ids = [entry.id for entry in entries]
            if len(set(ids)) != len(ids) or not set(ids).issubset(selected):
                raise ValueError("Cada ajuste deve pertencer a um produto selecionado, sem duplicatas.")
        photo_ids = [identity for group in self.image_groups for identity in group.item_ids]
        if len(set(photo_ids)) != len(photo_ids) or not set(photo_ids).issubset(selected):
            raise ValueError("Cada foto deve pertencer a um produto selecionado, sem duplicatas.")
        if self.image_groups and self.image_data is not None:
            raise ValueError("Não combine a foto compartilhada com fotos por seleção.")
        if self.stock_adjustments and (self.stock_delta or any(entry.stock_delta for entry in self.sizes or [])):
            raise ValueError("Não combine quantidade final com entrada ou saída no mesmo pedido.")
        return self


class GroupResponse(BaseModel):
    group_key: str
    items: List[ItemResponse]
    total_stock: int | None
    matching_count: int


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
    movement_type: Literal['entry', 'exit', 'adjustment', 'transfer']
    quantity: int = Field(ge=0, le=2_147_483_647, strict=True)
    location: Optional[Literal['loja', 'deposito']] = "loja"
    location_from: Optional[Literal['loja', 'deposito']] = None
    location_to: Optional[Literal['loja', 'deposito']] = None


class BatchMovementItem(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(gt=0, le=2_147_483_647, strict=True)
    unit_cost: Optional[Decimal] = None


class BatchMovementCreate(BaseModel):
    items: List[BatchMovementItem]
    reason: Optional[str] = None
    notes: Optional[str] = None


class MovementResponse(MovementBase):
    item_name: Optional[str] = None
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
    count_location: Literal['loja', 'deposito']


class SessionStatusUpdate(BaseModel):
    status: Literal['open', 'counting', 'reviewing', 'applied', 'cancelled']


class ScanItemCreate(BaseModel):
    item_id: uuid.UUID
    counted_quantity: int = Field(ge=0, le=2_147_483_647, strict=True)


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
    count_location: Optional[Literal['loja', 'deposito']] = None
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
    unknown_stock_count: int = 0
    total_active_items: int
    inactive_count: int = 0
    group_count: int = 0        # distinct groups
    grouped_items_count: int = 0  # items that belong to a group
    loja_count: int = 0          # active items with stock_loja > 0
    deposito_count: int = 0      # active items with stock_deposito > 0


class GradeCreateRequest(GalleryInput):
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
    initial_stock: Optional[int] = Field(default=0, ge=0, le=2_147_483_647, strict=True)
    stock_by_size: dict[str, Annotated[int, Field(ge=0, le=2_147_483_647, strict=True)]] = Field(default_factory=dict)
    stock_location: Optional[Literal['loja', 'deposito']] = "loja"

    @model_validator(mode='after')
    def validate_stock_by_size(self):
        from ..services.inventory_taxonomy_v2 import canonical_size
        self.sizes = list(dict.fromkeys(canonical_size(size.strip().upper()) for size in self.sizes if size.strip()))
        sizes = set(self.sizes)
        normalized = {}
        for size, quantity in self.stock_by_size.items():
            key = canonical_size(size.strip().upper())
            if key not in sizes or key in normalized:
                raise ValueError('Quantidade deve corresponder a um tamanho selecionado, sem repetição.')
            normalized[key] = quantity
        self.stock_by_size = normalized
        return self


class GradeCreateResponse(BaseModel):
    group_key: str
    items: List[ItemResponse]
    total_created: int


class BulkTransferItem(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(gt=0, le=2_147_483_647, strict=True)


class BulkTransferRequest(BaseModel):
    items: List[BulkTransferItem]
    direction: str   # "deposito_to_loja" | "loja_to_deposito"
    reason: Optional[str] = None
