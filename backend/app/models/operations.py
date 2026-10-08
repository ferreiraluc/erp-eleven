"""Small operational records, without credentials or request contents."""
from sqlalchemy import Column, String, Integer, DateTime
from ..database import Base


class LoginThrottle(Base):
    __tablename__ = 'login_throttles'
    bucket = Column(String(64), primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    attempts = Column(Integer, nullable=False)


class ScheduledRun(Base):
    __tablename__ = 'scheduled_runs'
    key = Column(String(80), primary_key=True)
    completed_at = Column(DateTime(timezone=True), nullable=False)
