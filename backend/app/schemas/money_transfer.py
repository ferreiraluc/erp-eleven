from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid
from ..models.money_transfer import TransferStatus

class MoneyTransferBase(BaseModel):
    transfer_date: Optional[date] = None
    amount_sent: Decimal
    thais_fee_percentage: Optional[Decimal] = Decimal("2.0")
    currency: Optional[str] = "R$"
    transfer_method: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class MoneyTransferCreate(MoneyTransferBase):
    created_by: Optional[str] = None

class MoneyTransferUpdate(BaseModel):
    amount_sent: Optional[Decimal] = None
    thais_fee_percentage: Optional[Decimal] = None
    transfer_method: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class DeliveryConfirmation(BaseModel):
    confirmed_by: str
    notes: Optional[str] = None

class MoneyTransferResponse(MoneyTransferBase):
    id: uuid.UUID
    thais_fee_amount: Decimal
    net_amount: Decimal
    status: TransferStatus
    delivery_confirmed_at: Optional[datetime] = None
    delivery_confirmed_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

class TransferSummary(BaseModel):
    """Summary for dashboard/overview"""
    total_pending: int
    total_delivered: int
    pending_amount: Decimal
    delivered_amount: Decimal
    total_fees_paid: Decimal
    last_transfer_date: Optional[date] = None