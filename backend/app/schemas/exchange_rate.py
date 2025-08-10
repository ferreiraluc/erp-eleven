from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
import uuid
from ..models.exchange_rate import CurrencyPair

class ExchangeRateBase(BaseModel):
    currency_pair: CurrencyPair
    rate: Decimal = Field(..., gt=0, description="Taxa de câmbio (deve ser positiva)")
    source: Optional[str] = Field("Manual Entry", max_length=100)
    is_active: Optional[bool] = True
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('rate')
    def validate_rate(cls, v):
        if v <= 0:
            raise ValueError('Taxa de câmbio deve ser positiva')
        if v > 99999999:
            raise ValueError('Taxa de câmbio muito alta')
        return v

class ExchangeRateCreate(ExchangeRateBase):
    updated_by: Optional[str] = None

class ExchangeRateUpdate(BaseModel):
    rate: Decimal
    source: Optional[str] = None
    # rate_date: Optional[date] = None  # Temporarily disabled
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
    usd_to_pyg: Optional[Decimal] = Field(None, gt=0, le=99999999)
    usd_to_brl: Optional[Decimal] = Field(None, gt=0, le=99999999)
    eur_to_usd: Optional[Decimal] = Field(None, gt=0, le=99999999)
    eur_to_brl: Optional[Decimal] = Field(None, gt=0, le=99999999)
    source: Optional[str] = Field("Dashboard", max_length=100)
    notes: Optional[str] = Field(None, max_length=500)
    updated_by: str = Field(..., min_length=1, max_length=100)

class CurrentRatesResponse(BaseModel):
    """Response with current exchange rates for easy frontend consumption"""
    usd_to_pyg: Optional[Decimal] = None
    usd_to_brl: Optional[Decimal] = None
    eur_to_usd: Optional[Decimal] = None
    eur_to_brl: Optional[Decimal] = None
    last_updated: Optional[datetime] = None
    source: Optional[str] = None

class WeeklyAverageResponse(BaseModel):
    """Weekly average calculation response"""
    currency_pair: str
    week_start: date
    week_end: date
    average_rate: Decimal
    sample_count: int
    min_rate: Decimal
    max_rate: Decimal
    rates_details: List[ExchangeRateResponse] = []

class RateHistoryResponse(BaseModel):
    """Historical rates with weekly averages"""
    current_rates: CurrentRatesResponse
    weekly_averages: List[WeeklyAverageResponse] = []
    historical_rates: List[ExchangeRateResponse] = []
    total_records: int