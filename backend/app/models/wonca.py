"""Monitoring configuration, owned subscriptions and durable signed deliveries."""
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON
from ..database import Base
from .access import now


class WoncaConfig(Base):
    __tablename__ = 'wonca_config'
    id = Column(String(16), primary_key=True, default='main')
    endpoint_id = Column(String(36), nullable=False)
    profile_id = Column(String(36), nullable=False)
    interval_hours = Column(Integer, nullable=False, default=2)
    monitor_days = Column(Integer, nullable=False, default=30)
    daytime_only = Column(Boolean, nullable=False, default=True)
    secret_encrypted = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)


class WoncaSubscription(Base):
    __tablename__ = 'wonca_subscriptions'
    code = Column(String(13), primary_key=True)
    remote_id = Column(String(36))
    endpoint_id = Column(String(36), nullable=False)
    profile_id = Column(String(36), nullable=False)
    state = Column(String(20), nullable=False, default='pending', index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    retry_at = Column(DateTime(timezone=True), nullable=False, default=now)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String(40))


class WoncaEvent(Base):
    __tablename__ = 'wonca_events'
    event_id = Column(String(36), primary_key=True)
    code = Column(String(13), nullable=False, index=True)
    body_hash = Column(String(64), nullable=False)
    checked_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON)
    status = Column(String(20), nullable=False, default='pending', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(String(40))
    received_at = Column(DateTime(timezone=True), nullable=False, default=now)
    processed_at = Column(DateTime(timezone=True))
