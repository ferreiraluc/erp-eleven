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
