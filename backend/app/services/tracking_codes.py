"""Canonical code matching shared by manual, provider and receipt registrations."""
import hashlib

from sqlalchemy import func, text


def normalize_tracking_code(value: str) -> str:
    return "".join(value.split()).upper()


def tracking_code_expression(column):
    expression = column
    for character in (" ", "\t", "\r", "\n", "\u00a0"):
        expression = func.replace(expression, character, "")
    return func.upper(expression)


def lock_tracking_codes(db, codes):
    """Serialize registration across channels; the unique column remains the backstop."""
    if db.bind.dialect.name == "postgresql":
        for code in sorted({normalize_tracking_code(code) for code in codes}):
            key = int.from_bytes(hashlib.sha256(("tracking-code:" + code).encode()).digest()[:8], "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
