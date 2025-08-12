"""
Utility functions for handling datetime with proper timezone support
"""
from datetime import datetime
from typing import Optional
from ..config import settings


def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime object is timezone-aware.
    If it's naive, assume it's in the configured timezone.
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Naive datetime - assume it's in our configured timezone
        return dt.replace(tzinfo=settings.tz)
    
    return dt


def now_in_timezone() -> datetime:
    """
    Get current datetime in the configured timezone
    """
    return settings.now()


def normalize_datetime_for_comparison(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize a datetime for comparison operations.
    Ensures timezone consistency.
    """
    return ensure_timezone_aware(dt)