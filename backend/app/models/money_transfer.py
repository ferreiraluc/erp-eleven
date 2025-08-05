from sqlalchemy import Column, String, Boolean, DateTime, DECIMAL, Text, Enum, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..database import Base

class TransferStatus(enum.Enum):
    PENDING = "PENDING"           # Money sent to Thais, waiting for delivery
    DELIVERED = "DELIVERED"       # Money delivered to store
    CANCELLED = "CANCELLED"       # Transfer cancelled

class MoneyTransfer(Base):
    __tablename__ = "money_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Transfer details
    transfer_date = Column(Date, nullable=False, default=func.current_date())
    amount_sent = Column(DECIMAL(15,4), nullable=False)  # Amount sent to Thais
    thais_fee_percentage = Column(DECIMAL(5,2), default=2.0)  # Thais' fee percentage (default 2%)
    thais_fee_amount = Column(DECIMAL(15,4), nullable=False)  # Calculated fee amount
    net_amount = Column(DECIMAL(15,4), nullable=False)  # Amount after Thais' fee
    
    # Status tracking
    status = Column(Enum(TransferStatus), default=TransferStatus.PENDING)
    delivery_confirmed_at = Column(DateTime)
    delivery_confirmed_by = Column(String(100))
    
    # Additional info
    currency = Column(String(10), default="R$")  # Usually BRL
    transfer_method = Column(String(50))  # PIX, Transfer, etc.
    reference_number = Column(String(100))  # Bank reference or PIX ID
    notes = Column(Text)
    
    # Audit trail
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    created_by = Column(String(100))