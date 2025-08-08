"""
Validation helpers for API endpoints
"""
from fastapi import HTTPException
from uuid import UUID
from datetime import date


def validate_uuid(uuid_str: str, field_name: str = "ID") -> UUID:
    """Validate UUID string and return UUID object"""
    try:
        return UUID(uuid_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid {field_name} format. Must be a valid UUID."
        )


def validate_date(date_str: str, field_name: str = "date") -> date:
    """Validate and parse date string to prevent SQL injection"""
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid {field_name} format: {date_str}. Use YYYY-MM-DD"
        )