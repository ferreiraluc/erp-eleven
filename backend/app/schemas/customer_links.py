from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .pedido import PedidoResponse
from .rastreamento import RastreamentoComPedido


class CustomerLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["pedido", "rastreamento"]
    target_id: UUID


class CustomerHistoryConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_token: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm: Literal[True]


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


class CustomerPurchasePayment(BaseModel):
    id: UUID
    method: str
    currency: str
    amount_original: Decimal
    exchange_rate: Decimal
    amount_gs: Decimal


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
    payments: list[CustomerPurchasePayment] = Field(default_factory=list)
    payment_difference_gs: Decimal = Decimal('0')
    change_gs: Decimal | None = None


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
