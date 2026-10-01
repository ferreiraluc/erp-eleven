"""Read-only inventory health: findings are evidence for review, not corrections."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Issue = Literal['stock_mismatch', 'negative_stock', 'missing_stock', 'duplicate_barcode']
IssueFilter = Literal['all', 'stock_mismatch', 'negative_stock', 'missing_stock', 'duplicate_barcode']


class DiagnosticCounts(BaseModel):
    stock_mismatch: int
    negative_stock: int
    missing_stock: int
    duplicate_barcode: int
    duplicate_barcode_groups: int


class DiagnosticItem(BaseModel):
    id: UUID
    name: str
    sku_internal: str
    barcode: str | None
    normalized_barcode: str
    brand: str | None
    size: str | None
    color: str | None
    current_stock: int | None
    stock_loja: int | None
    stock_deposito: int | None
    expected_stock: int | None
    delta: int | None
    issues: list[Issue]
    duplicate_count: int


class InventoryDiagnostics(BaseModel):
    checked_at: datetime
    total_active_items: int
    affected_items: int
    counts: DiagnosticCounts
    total_items: int
    page: int
    page_size: int
    items: list[DiagnosticItem]
