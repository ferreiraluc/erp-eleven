from sqlalchemy import Column, String, Boolean, DateTime, DECIMAL, Text, Enum, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from datetime import date
from ..database import Base

class CurrencyPair(enum.Enum):
    USD_TO_PYG = "USD_TO_PYG"  # US Dollar to Paraguayan Guarani
    USD_TO_BRL = "USD_TO_BRL"  # US Dollar to Brazilian Real
    EUR_TO_PYG = "EUR_TO_PYG"  # Euro to Paraguayan Guarani
    EUR_TO_BRL = "EUR_TO_BRL"  # Euro to Brazilian Real

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    currency_pair = Column(Enum(CurrencyPair), nullable=False)  # Removed unique constraint to allow historical rates
    rate = Column(DECIMAL(12,4), nullable=False)
    source = Column(String(100), default="Manual Entry")  # e.g., "Bonanza Cambios", "Admin Dashboard"
    is_active = Column(Boolean, default=True, index=True)  # Only one active rate per pair
    # rate_date = Column(Date, default=date.today, index=True)  # Will add after database migration
    notes = Column(Text)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    updated_by = Column(String(100))  # Who updated the rate
    
    def __repr__(self):
        return f"<ExchangeRate {self.currency_pair.value}: {self.rate}>"