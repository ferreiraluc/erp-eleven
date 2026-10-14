from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .pedido import PedidoResponse
from .rastreamento import RastreamentoComPedido


class CustomerLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["pedido", "rastreamento"]
    target_id: UUID


class CustomerLogisticsResponse(BaseModel):
    order_total: int
    shipment_total: int
    in_transit: int
    delivered: int
    orders: list[PedidoResponse]
    shipments: list[RastreamentoComPedido]


class CustomerPurchaseLine(BaseModel):
    id: UUID
    name: str
    quantity: Decimal
    returned_quantity: Decimal


class CustomerPurchase(BaseModel):
    id: UUID
    created_at: datetime
    account_id: UUID
    account_name: str
    customer_name: str | None
    seller: str | None
    status: str
    total_gs: Decimal
    refunded_gs: Decimal
    net_gs: Decimal
    lines: list[CustomerPurchaseLine]


class CustomerPurchaseSummary(BaseModel):
    net_gs: Decimal
    refunded_gs: Decimal
    cancelled: int


class CustomerPurchasesResponse(BaseModel):
    page: int
    page_size: int
    total: int
    own_sales_only: bool
    summary: CustomerPurchaseSummary
    items: list[CustomerPurchase]
