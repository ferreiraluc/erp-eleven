"""Webhook signing keys stay encrypted at rest with the server's existing application key."""
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from ..config import settings
from ..models.address_book import FreightWebhook
from .superfrete import environment


def cipher():
    key = hashlib.sha256(('eleven:superfrete:webhook:' + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def signing_secret(db):
    if settings.SUPERFRETE_WEBHOOK_SECRET:return settings.SUPERFRETE_WEBHOOK_SECRET
    row = db.get(FreightWebhook,environment())
    if not row:return ''
    try:return cipher().decrypt(row.secret_encrypted.encode()).decode()
    except (InvalidToken,ValueError):return ''
