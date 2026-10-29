"""Opt-in synchronization of the public Jebai/Venta exchange board."""
from sqlalchemy import Column, String, Boolean, DateTime
from ..database import Base


class ExchangeSync(Base):
    __tablename__ = 'exchange_sync'
    id = Column(String(16), primary_key=True, default='bonanza')
    enabled = Column(Boolean, nullable=False, default=False)
    last_attempt = Column(DateTime(timezone=True))
    last_success = Column(DateTime(timezone=True))
    source_at = Column(DateTime(timezone=True))
    last_error = Column(String(40))
