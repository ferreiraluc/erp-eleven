"""Bounded temporary media, never URLs, paths, filenames or model context.

The bridge endpoint authenticates the instance, exact sender and destination
before calling ingestion. Reads additionally bind every reference to its ERP
author and conversation. Transactions own both the media and inbox insertion.
"""
import hashlib
import uuid
from datetime import timedelta

from sqlalchemy import func, text

from ..models.assistant import utcnow
from ..models.assistant_whatsapp_media import WhatsAppMedia

MAX_BYTES = 5 * 1024 * 1024
USER_BYTES = 25 * 1024 * 1024
GLOBAL_BYTES = 100 * 1024 * 1024
TTL = timedelta(hours=24)
_QUOTA_LOCK = 734927106


def cleanup_media(db):
    """Delete expired bytes even when the WhatsApp channel has been paused."""
    db.query(WhatsAppMedia).filter(WhatsAppMedia.expires_at <= utcnow()).delete(synchronize_session=False)


def _reference(row):
    return {
        "provider": "whatsapp_web", "media_id": str(row.id), "kind": row.kind,
        "mime_type": row.mime_type, "size": row.byte_size,
        "name": "PDF recebido" if row.kind == "document" else "Imagem recebida",
    }


def ingest_media(db, *, user_id, conversation_id, message_external_id, content, mime_type):
    """Store a verified attachment after the core authorizes its envelope."""
    if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
        raise ValueError("Envie uma foto JPG/PNG ou PDF de até 5 MB.")
    if (not isinstance(conversation_id, str) or not 1 <= len(conversation_id) <= 120
            or not isinstance(message_external_id, str) or not 1 <= len(message_external_id) <= 120):
        raise ValueError("Origem do anexo inválida.")
    if mime_type == "application/pdf":
        from .assistant_documents import validate_pdf
        validate_pdf(content)
        kind = "document"
    elif mime_type in ("image/jpeg", "image/png"):
        from .receipt_vision import validate_image
        content = validate_image(content)
        mime_type, kind = "image/jpeg", "image"
    else:
        raise ValueError("Envie o comprovante como JPG/PNG ou o documento como PDF.")
    digest = hashlib.sha256(content).hexdigest()
    # Serialize aggregate quotas across API processes; SQLite unit tests do not
    # substitute for the PostgreSQL concurrency check.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _QUOTA_LOCK})
    cleanup_media(db)
    old = db.query(WhatsAppMedia).filter_by(message_external_id=message_external_id).first()
    if old:
        if old.user_id != user_id or old.conversation_id != conversation_id or old.sha256 != digest:
            raise ValueError("O anexo recebido não corresponde à mensagem original.")
        return _reference(old)
    total, own = db.query(
        func.coalesce(func.sum(WhatsAppMedia.byte_size), 0),
        func.coalesce(func.sum(WhatsAppMedia.byte_size).filter(WhatsAppMedia.user_id == user_id), 0),
    ).one()
    if total + len(content) > GLOBAL_BYTES or own + len(content) > USER_BYTES:
        raise ValueError("Limite temporário de anexos atingido. Aguarde a expiração ou conclua os comprovantes pendentes.")
    row = WhatsAppMedia(user_id=user_id, conversation_id=conversation_id,
        message_external_id=message_external_id, kind=kind, mime_type=mime_type,
        byte_size=len(content), sha256=digest, data=content, expires_at=utcnow() + TTL)
    db.add(row)
    db.flush()
    return _reference(row)


def _owned_media(db, attachment, *, user_id, conversation_id):
    if not db or not isinstance(attachment, dict) or attachment.get("provider") != "whatsapp_web":
        raise ValueError("Anexo indisponível. Envie o arquivo novamente.")
    try:
        media_id = uuid.UUID(str(attachment.get("media_id", "")))
    except (TypeError, ValueError):
        raise ValueError("Anexo indisponível. Envie o arquivo novamente.") from None
    cleanup_media(db)
    row = db.query(WhatsAppMedia).filter(
        WhatsAppMedia.id == media_id, WhatsAppMedia.user_id == user_id,
        WhatsAppMedia.conversation_id == conversation_id, WhatsAppMedia.expires_at > utcnow(),
    ).first()
    if not row:
        raise ValueError("O anexo expirou ou não pertence a este usuário e conversa. Envie-o novamente.")
    return row


def read_media(db, attachment, *, user_id, conversation_id):
    row = _owned_media(db, attachment, user_id=user_id, conversation_id=conversation_id)
    if (not row.data or len(row.data) != row.byte_size or row.byte_size > MAX_BYTES
            or hashlib.sha256(row.data).hexdigest() != row.sha256):
        raise ValueError("O anexo não passou na verificação de integridade. Envie-o novamente.")
    return bytes(row.data)


def media_expires_at(db, attachment, *, user_id, conversation_id):
    return _owned_media(db, attachment, user_id=user_id, conversation_id=conversation_id).expires_at


def discard_media(db, attachment, *, user_id, conversation_id):
    """Receipt OCR no longer needs the image once its reviewable data exists."""
    row = _owned_media(db, attachment, user_id=user_id, conversation_id=conversation_id)
    db.delete(row)
    db.flush()
