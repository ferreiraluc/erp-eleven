"""Readable ticket lookup derived from the immutable sale ID, without new IDs."""
import re
import uuid


def ticket_code(sale_id):
    return uuid.UUID(str(sale_id)).hex[:10].upper()


def ticket_range(value):
    code = value.strip().removeprefix('#').upper()
    if not re.fullmatch(r'[0-9A-F]{10}', code):
        return None
    lower = int(code, 16) << 88
    upper = lower + (1 << 88) - 1
    return uuid.UUID(int=lower), uuid.UUID(int=upper)
