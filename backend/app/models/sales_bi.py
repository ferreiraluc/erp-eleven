"""Read model for externally maintained sales spreadsheets; no ERP sales writes."""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from ..database import Base
from .assistant import utcnow


class SalesBIConfig(Base):
    __tablename__ = 'sales_bi_config'
    id = Column(Integer, primary_key=True)
    current_url = Column(String(2500), nullable=False)
    archive_url = Column(String(2500), nullable=False)
    archive_root = Column(String(1000), nullable=False)
    current_year = Column(Integer)
    current_month = Column(Integer)
    enabled = Column(Boolean, nullable=False, default=True)
    requested_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    next_sync_at = Column(DateTime(timezone=True))
    lease_until = Column(DateTime(timezone=True))
    lease_token = Column(String(36))
    last_error = Column(String(500))


class SalesBIWorkbook(Base):
    __tablename__ = 'sales_bi_workbooks'
    id = Column(String(64), primary_key=True)
    kind = Column(String(16), nullable=False)
    filename = Column(String(300), nullable=False)
    year = Column(Integer)
    month = Column(Integer)
    remote_version = Column(String(200))
    content_hash = Column(String(64))
    parser_version = Column(Integer)
    snapshot = Column(JSON)
    checked_at = Column(DateTime(timezone=True))
    synced_at = Column(DateTime(timezone=True))
    error = Column(String(500))
    active = Column(Boolean, nullable=False, default=True)
