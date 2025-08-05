from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
import uuid
from ..models.exchange_rate import CurrencyPair

class ExchangeRateBase(BaseModel):
    currency_pair: CurrencyPair
    rate: Decimal
    source: Optional[str] = "Manual Entry"
    is_active: Optional[bool] = True
    notes: Optional[str] = None

class ExchangeRateCreate(ExchangeRateBase):
    updated_by: Optional[str] = None

class ExchangeRateUpdate(BaseModel):
    rate: Decimal
    source: Optional[str] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None

class ExchangeRateResponse(ExchangeRateBase):
    id: uuid.UUID
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QuickRateUpdate(BaseModel):
    """Simplified schema for quick rate updates from frontend"""
    usd_to_pyg: Optional[Decimal] = None
    usd_to_brl: Optional[Decimal] = None
    eur_to_pyg: Optional[Decimal] = None
    eur_to_brl: Optional[Decimal] = None
    updated_by: Optional[str] = "Frontend User"

class CurrentRatesResponse(BaseModel):
    """Response with current exchange rates for easy frontend consumption"""
    usd_to_pyg: Optional[Decimal] = None
    usd_to_brl: Optional[Decimal] = None
    eur_to_pyg: Optional[Decimal] = None
    eur_to_brl: Optional[Decimal] = None
    last_updated: Optional[datetime] = None
    source: Optional[str] = None