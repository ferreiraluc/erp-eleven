"""Daily quality reports contain references and counts, never operational writes."""
import uuid
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base
from .access import now


class QualityConfig(Base):
    __tablename__ = 'quality_config'
    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    ai_enabled = Column(Boolean, nullable=False, default=True)
    local_time = Column(String(5), nullable=False, default='08:30')
    first_run_on = Column(Date, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    ai_reserved_on = Column(Date)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class QualityRun(Base):
    __tablename__ = 'quality_runs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), unique=True)
    requested_by = Column(UUID(as_uuid=True), ForeignKey('usuarios.id'))
    run_day = Column(Date, nullable=False)
    kind = Column(String(20), nullable=False, default='daily')
    status = Column(String(20), nullable=False, default='running')
    lease_token = Column(String(36))
    lease_until = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    started_at = Column(DateTime(timezone=True), nullable=False, default=now)
    finished_at = Column(DateTime(timezone=True))
    counters = Column(JSON, nullable=False, default=dict)
    coverage = Column(JSON, nullable=False, default=dict)
    findings = Column(JSON, nullable=False, default=list)
    summary = Column(Text)
    ai_summary = Column(Text)
    ai_attempted = Column(Boolean, nullable=False, default=False)
    ai_status = Column(String(30), nullable=False, default='not_requested')
    provider = Column(String(40))
    provider_calls = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    error_category = Column(String(100))
    __table_args__ = (Index('uq_quality_run_daily', 'run_day', 'kind', unique=True,
                           postgresql_where=text("kind = 'daily'"), sqlite_where=text("kind = 'daily'")),
                     Index('ix_quality_runs_created', 'created_at', 'id'))
