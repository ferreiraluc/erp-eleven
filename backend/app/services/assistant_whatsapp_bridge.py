"""Scoped, pull-only WhatsApp Web transport. No provider session reaches the ERP."""
import base64
import hashlib
import io
import re
import secrets
from datetime import timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from ..config import settings
from ..models.assistant import AssistantDelivery, AssistantIdentity, AssistantMessage, AssistantWhatsAppBridge, utcnow
from ..models.usuario import Usuario

CHANNEL = "whatsapp_web"
PHONE = re.compile(r"\+[1-9][0-9]{6,14}")
PRIVATE = re.compile(r"[1-9][0-9]{6,14}@s\.whatsapp\.net")
GROUP = re.compile(r"[0-9]{5,20}(?:-[0-9]{1,20})?@g\.us")


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def bridge_config(db):
    return db.get(AssistantWhatsAppBridge, "primary")


def bridge_enabled(db):
    row = bridge_config(db)
    return bool(settings.ASSISTANT_ENABLED and row and row.enabled)


def conversation_allowed(db, destination, sender_id=None):
    row = bridge_config(db)
    if not settings.ASSISTANT_ENABLED or not row or not row.enabled:
        return False
    if GROUP.fullmatch(destination or ""):
        return destination in row.allowed_groups
    if not row.allow_private or not PRIVATE.fullmatch(destination or ""):
        return False
    return sender_id is None or sender_id == "whatsapp:+" + destination.split("@")[0]


def channel_destination_allowed(db, channel, destination, sender_id=None):
    if channel == "telegram":
        return bool(settings.TELEGRAM_GROUP_ID and destination.split(":")[0] == settings.TELEGRAM_GROUP_ID)
    return channel == CHANNEL and conversation_allowed(db, destination, sender_id)


def authenticate(db, authorization):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not 32 <= len(token) <= 256:
        raise HTTPException(401, "Credencial da ponte inválida")
    row = bridge_config(db)
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not row or not row.token_hash or not secrets.compare_digest(digest, row.token_hash):
        raise HTTPException(401, "Credencial da ponte inválida")
    return row


def lock_bridge(db, authenticated):
    digest = authenticated.token_hash
    row = db.query(AssistantWhatsAppBridge).filter_by(id=authenticated.id).populate_existing().with_for_update().one()
    if row.token_hash != digest:
        raise HTTPException(401, "A credencial da ponte foi alterada")
    return row


def public_config(row):
    return {
        "enabled": bool(row and row.enabled), "name": row.name if row else "WhatsApp Eleven",
        "allow_private": row.allow_private if row else True,
        "notify_tracking": row.notify_tracking if row else False,
        "group_mode": row.group_mode if row else "mention",
        "allowed_groups": row.allowed_groups if row else [],
        "discovered_groups": row.discovered_groups if row else [],
        "state": row.state if row else "not_configured",
        "session_generation": row.session_generation if row else 0,
        "account_phone": row.account_phone if row else None,
        "agent_version": row.agent_version if row else None,
        "last_seen_at": row.last_seen_at if row else None,
        "error_code": row.error_code if row else None,
        "credential_configured": bool(row and row.token_hash),
    }


def agent_config(db, row):
    from .assistant_channels import authorized_identity
    identifiers = db.query(AssistantIdentity.external_id).filter_by(channel=CHANNEL, active=True).all()
    senders = [identifier for (identifier,) in identifiers if authorized_identity(db, CHANNEL, identifier)]
    return {
        "enabled": bool(settings.ASSISTANT_ENABLED and row.enabled),
        "allow_private": row.allow_private, "group_mode": row.group_mode,
        "allowed_groups": row.allowed_groups, "allowed_senders": senders,
        "session_generation": row.session_generation,
        "limits": {"text_chars": 6000, "media_bytes": 5 * 1024 * 1024, "max_message_age_seconds": 86400},
    }


def pairing_image(row):
    if not row or not row.pairing_qr or not row.pairing_expires_at or aware(row.pairing_expires_at) <= utcnow():
        return {"qr_image": None, "expires_at": None}
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from PIL import Image, ImageDraw
    qr = QrCodeWidget(row.pairing_qr, barLevel="M")
    qr.qr.make()
    modules = qr.qr.modules
    scale, border = 5, 4
    image = Image.new("RGB", ((len(modules) + border * 2) * scale,) * 2, "white")
    draw = ImageDraw.Draw(image)
    for y, line in enumerate(modules):
        for x, dark in enumerate(line):
            if dark:
                left, top = (x + border) * scale, (y + border) * scale
                draw.rectangle((left, top, left + scale - 1, top + scale - 1), fill="black")
    output = io.BytesIO()
    image.save(output, "PNG")
    return {"qr_image": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(),
            "expires_at": row.pairing_expires_at}


def ingest(db, bridge, body):
    from .assistant_channels import Incoming, authorized_identity, enqueue_incoming
    if not settings.ASSISTANT_ENABLED or not bridge.enabled:
        return "paused"
    if not conversation_allowed(db, body.conversation_id, body.sender_id):
        return "ignored"
    if GROUP.fullmatch(body.conversation_id) and bridge.group_mode == "mention" and not body.should_reply:
        return "ignored"
    now = utcnow()
    if body.timestamp.tzinfo is None or not now - timedelta(hours=24) <= body.timestamp <= now + timedelta(minutes=5):
        return "ignored"
    identity = authorized_identity(db, CHANNEL, body.sender_id)
    if not identity:
        return "ignored"
    # Lock before media ingestion and the quota check to make provider retries cheap.
    db.query(Usuario).filter_by(id=identity.user_id).with_for_update().first()
    external = hashlib.sha256((body.conversation_id + "\0" + body.message_id).encode()).hexdigest()
    if db.query(AssistantMessage.id).filter_by(channel=CHANNEL, external_id=external).first():
        return "duplicate"
    count = db.query(AssistantMessage).filter(AssistantMessage.user_id == identity.user_id,
        AssistantMessage.created_at >= now - timedelta(days=1)).count()
    if count >= settings.ASSISTANT_DAILY_MESSAGES:
        return "rate_limited"
    attachment = None
    if body.attachment:
        try:
            data = base64.b64decode(body.attachment.data_base64, validate=True)
        except (ValueError, TypeError):
            raise HTTPException(400, "Anexo inválido") from None
        if not data or len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "Envie um anexo de até 5 MB")
        from .assistant_whatsapp_media import ingest_media
        try:
            attachment = ingest_media(db, user_id=identity.user_id, conversation_id=body.conversation_id,
                message_external_id=external, content=data, mime_type=body.attachment.mime_type)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
    text = body.text.strip()
    if not text and attachment:
        text = ("[Imagem recebida: foto para conferência]" if attachment.get("kind") == "image"
                else "[Arquivo recebido: anexo para impressão]")
    if not text:
        return "ignored"
    return enqueue_incoming(db, Incoming(CHANNEL, external, body.conversation_id,
        body.sender_id, text, body.should_reply, attachment))


def _plain_controls(delivery):
    text = delivery.text
    rows = (delivery.reply_markup or {}).get("inline_keyboard", [])
    controls = []
    for row in rows:
        for item in row:
            data = item.get("callback_data", "")
            label = str(item.get("text", "Escolher"))[:64]
            # The transport removes /eleven; keep it in every displayed choice
            # so an ordinary message also addresses the bot in mention-only groups.
            if re.fullmatch(r"[acv]:[0-9a-f]{32}", data):
                controls.append(f"{label}: /eleven /acao {data}")
            elif re.fullmatch(r"q:[0-9a-f]{32}:[0-9]{1,3}", data):
                controls.append(f"{label}: /eleven /servico {data[2:]}")
            elif re.fullmatch(r"p:[0-9]{1,6}", data):
                controls.append(f"{label}: /eleven /previas {data[2:]}")
    return text + ("\n\nEnvie o comando da opção desejada:\n" + "\n".join(controls) if controls else "")


def _payload(delivery):
    return {
        "id": str(delivery.id), "claim_key": str(delivery.bridge_claim_key), "status": delivery.status,
        "destination": delivery.destination, "text": _plain_controls(delivery),
        "reply_markup": delivery.reply_markup, "document_url": None,
        "document_pdf_base64": base64.b64encode(delivery.document_pdf).decode() if delivery.document_pdf else None,
        "expires_at": delivery.expires_at, "provider_id": delivery.provider_id,
    }


def _reject(db, delivery):
    from .assistant_delivery_policy import delivery_rejection, cancel_pending_dependents
    reason = None
    if delivery.expires_at and aware(delivery.expires_at) <= utcnow():
        delivery.status, reason = "expired", "delivery_expired"
    elif delivery.depends_on_id:
        parent = db.get(AssistantDelivery, delivery.depends_on_id)
        if not parent or parent.status in ("cancelled", "expired", "failed"):
            delivery.status, reason = "cancelled", "delivery_dependency_unavailable"
    if not reason:
        reason = delivery_rejection(db, delivery)
        if reason:
            delivery.status = "cancelled"
    if reason:
        delivery.error_code = reason
        cancel_pending_dependents(db, delivery.id)
    return reason


def claim(db, bridge, claim_key):
    existing = db.query(AssistantDelivery).filter_by(bridge_claim_key=claim_key).with_for_update().first()
    if existing:
        if existing.channel != CHANNEL or existing.bridge_id != bridge.id:
            raise HTTPException(409, "Chave de retirada pertence a outra ponte")
        return _payload(existing)
    if not settings.ASSISTANT_ENABLED or not bridge.enabled or bridge.state != "connected":
        return None
    # A local journal must resolve its existing claim before pulling another reply.
    if db.query(AssistantDelivery.id).filter_by(channel=CHANNEL, bridge_id=bridge.id).filter(
            AssistantDelivery.status.in_(("claimed", "sending"))).first():
        return None
    previous = aliased(AssistantDelivery)
    ready_parent = db.query(previous.id).filter(previous.id == AssistantDelivery.depends_on_id,
        previous.status.in_(("accepted", "cancelled", "expired", "failed"))).exists()
    for _ in range(25):
        delivery = db.query(AssistantDelivery).filter(AssistantDelivery.channel == CHANNEL,
            AssistantDelivery.status == "pending", AssistantDelivery.available_at <= utcnow(),
            or_(AssistantDelivery.depends_on_id.is_(None), ready_parent)).order_by(
                AssistantDelivery.created_at, AssistantDelivery.id).with_for_update(skip_locked=True).first()
        if not delivery:
            return None
        if _reject(db, delivery):
            db.flush()
            continue
        if delivery.document_url:
            from .superfrete import safe_label, label_pdf
            if not safe_label(delivery.document_url):
                delivery.status, delivery.error_code = "failed", "invalid_document_url"
                db.flush()
                continue
            if not delivery.document_pdf:
                try:
                    delivery.document_pdf = label_pdf(delivery.document_url)
                except HTTPException:
                    delivery.error_code = "document_temporarily_unavailable"
                    delivery.attempts += 1
                    if delivery.attempts >= 3:
                        from .assistant_delivery_policy import cancel_pending_dependents
                        delivery.status = "failed"
                        cancel_pending_dependents(db, delivery.id)
                    delivery.available_at = utcnow() + timedelta(minutes=1)
                    db.flush()
                    continue
        delivery.bridge_id, delivery.bridge_claim_key = bridge.id, claim_key
        delivery.status, delivery.available_at = "claimed", utcnow()
        db.flush()
        return _payload(delivery)
    return None


def claimed_delivery(db, bridge, delivery_id, claim_key):
    row = db.query(AssistantDelivery).filter_by(id=delivery_id, channel=CHANNEL,
        bridge_id=bridge.id, bridge_claim_key=claim_key).with_for_update().first()
    if not row:
        raise HTTPException(409, "Retirada não corresponde à mensagem")
    return row


def start(db, bridge, row):
    if row.status != "claimed":
        return {"can_send": False, "status": row.status}
    if not settings.ASSISTANT_ENABLED or not bridge.enabled or bridge.state != "connected":
        return {"can_send": False, "status": row.status, "error_code": "channel_paused"}
    if _reject(db, row):
        return {"can_send": False, "status": row.status, "error_code": row.error_code}
    row.status, row.available_at = "sending", utcnow()
    row.attempts += 1
    return {"can_send": True, "status": row.status}


def acknowledge(db, row, body):
    from .assistant_delivery_policy import cancel_pending_dependents
    if row.status == "accepted":
        if body.status != "accepted" or body.provider_id != row.provider_id:
            raise HTTPException(409, "Resultado de envio já confirmado")
        return {"status": row.status}
    if row.status in ("cancelled", "expired", "failed"):
        return {"status": row.status}
    if row.status not in ("claimed", "sending", "uncertain"):
        raise HTTPException(409, "Envio não está em processamento")
    if body.status == "accepted" and row.status == "claimed":
        raise HTTPException(409, "Envio ainda não foi autorizado")
    if body.status == "accepted" and not body.provider_id:
        raise HTTPException(422, "Informe o identificador aceito pelo provedor")
    # An uncertain dispatch is not downgraded to a definite failure/retry.
    if row.status == "uncertain" and body.status == "failed":
        return {"status": row.status}
    row.status, row.provider_id = body.status, body.provider_id
    row.error_code = None if body.status == "accepted" else body.error_code or "agent_outcome_unknown"
    if row.status == "accepted":
        row.document_pdf = None
    elif row.status == "failed":
        cancel_pending_dependents(db, row.id)
    return {"status": row.status}
