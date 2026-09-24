"""Signed provider webhooks and administrator-only configuration/inspection."""
import secrets
from urllib.parse import urlsplit
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import FormData
from twilio.request_validator import RequestValidator

from ...config import settings
from ...database import get_db
from ...dependencies import require_role
from ...models.assistant import AssistantIdentity, AssistantMessage, AssistantNote, AssistantDelivery, AssistantAction, utcnow
from ...models.usuario import Usuario
from ...services.assistant_channels import enqueue_incoming, telegram_message, twilio_message

router = APIRouter()
admin = Depends(require_role(["ADMIN"]))


async def bounded_body(request):
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 65536:
            raise HTTPException(413, "Webhook excede o limite de tamanho")
        yield chunk


@router.post("/webhooks/twilio")
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.ASSISTANT_ENABLED or not settings.ASSISTANT_WHATSAPP_ENABLED or not all((settings.TWILIO_AUTH_TOKEN, settings.TWILIO_WEBHOOK_URL,
                                                  settings.TWILIO_ACCOUNT_SID, settings.TWILIO_WHATSAPP_FROM)):
        raise HTTPException(503, "Canal não configurado ou pausado")
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        raise HTTPException(415, "Formato não suportado")
    # Parse all fields, including future Twilio fields and repeated values.
    from urllib.parse import parse_qsl
    body = b"".join([chunk async for chunk in bounded_body(request)])
    try:
        form = FormData(parse_qsl(body.decode("utf-8"), keep_blank_values=True, max_num_fields=200))
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Formulário inválido")
    public = urlsplit(settings.TWILIO_WEBHOOK_URL)
    valid = public.scheme == "https" and public.path == request.url.path and public.query == request.url.query
    valid = valid and RequestValidator(settings.TWILIO_AUTH_TOKEN).validate(
        settings.TWILIO_WEBHOOK_URL, form, request.headers.get("X-Twilio-Signature", ""))
    if not valid:
        raise HTTPException(403, "Assinatura inválida")
    enqueue_incoming(db, twilio_message(form))
    db.commit()
    return Response("<Response/>", media_type="application/xml")


@router.post("/webhooks/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.ASSISTANT_ENABLED or not settings.ASSISTANT_TELEGRAM_ENABLED or not settings.TELEGRAM_WEBHOOK_SECRET or not settings.TELEGRAM_GROUP_ID:
        raise HTTPException(503, "Canal não configurado ou pausado")
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(supplied, settings.TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(403, "Segredo inválido")
    import json
    body = b"".join([chunk async for chunk in bounded_body(request)])
    try:
        update = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "JSON inválido")
    if not isinstance(update, dict):
        raise HTTPException(400, "Update inválido")
    status = enqueue_incoming(db, telegram_message(update))
    db.commit()
    callback = update.get('callback_query')
    if isinstance(callback, dict):
        from ...services.assistant_channels import acknowledge_callback
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(acknowledge_callback, callback.get('id'), status)
    return {"ok": True}


class IdentityInput(BaseModel):
    channel: Literal["whatsapp", "telegram"]
    external_id: str = Field(min_length=1, max_length=100)
    user_id: UUID
    active: bool = True
    can_register: bool = False

    @model_validator(mode="after")
    def validate_external_id(self):
        import re
        pattern = r"whatsapp:\+[1-9][0-9]{6,14}" if self.channel == "whatsapp" else r"[1-9][0-9]{0,19}"
        if not re.fullmatch(pattern, self.external_id):
            raise ValueError("Use whatsapp:+DDINUMERO ou o ID numérico do usuário Telegram")
        return self


@router.get("/status", dependencies=[admin])
def assistant_status(db: Session = Depends(get_db)):
    def counts(model):
        return dict(db.query(model.status, func.count(model.id)).group_by(model.status).all())
    return {
        "enabled": settings.ASSISTANT_ENABLED, "model": settings.DEEPSEEK_MODEL,
        "telegram_enabled": settings.ASSISTANT_TELEGRAM_ENABLED,
        "whatsapp_enabled": settings.ASSISTANT_WHATSAPP_ENABLED,
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "twilio_configured": all((settings.TWILIO_AUTH_TOKEN, settings.TWILIO_ACCOUNT_SID, settings.TWILIO_WHATSAPP_FROM, settings.TWILIO_WEBHOOK_URL)),
        "telegram_configured": all((settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_WEBHOOK_SECRET, settings.TELEGRAM_GROUP_ID, settings.TELEGRAM_BOT_USERNAME)),
        "telegram_group_id": settings.TELEGRAM_GROUP_ID,
        "messages": counts(AssistantMessage), "deliveries": counts(AssistantDelivery),
        "notes": counts(AssistantNote), "actions": counts(AssistantAction), "daily_messages_per_user": settings.ASSISTANT_DAILY_MESSAGES,
    }


@router.get("/users", dependencies=[admin])
def assistant_users(db: Session = Depends(get_db)):
    return [{"id": str(u.id), "nome": u.nome, "role": u.role.value} for u in db.query(Usuario).filter(
        Usuario.ativo.is_(True), Usuario.role.in_(["ADMIN", "GERENTE", "VENDEDOR"])).order_by(Usuario.nome).all()]


@router.get("/identities", dependencies=[admin])
def list_identities(db: Session = Depends(get_db)):
    return [{"id": str(i.id), "channel": i.channel, "external_id": i.external_id,
             "user_id": str(i.user_id), "active": i.active, "can_register": i.can_register}
            for i in db.query(AssistantIdentity).order_by(AssistantIdentity.channel).all()]


@router.post("/identities", dependencies=[admin])
def save_identity(body: IdentityInput, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter_by(id=body.user_id, ativo=True).first()
    if not user or user.role.value not in ("ADMIN", "GERENTE", "VENDEDOR"):
        raise HTTPException(400, "Usuário não autorizado para o assistente")
    identity = db.query(AssistantIdentity).filter_by(channel=body.channel, external_id=body.external_id).first()
    if identity and identity.user_id != body.user_id:
        raise HTTPException(409, "Identidade já vinculada a outro usuário; não pode ser reatribuída")
    if not identity:
        identity = AssistantIdentity(**body.model_dump())
        db.add(identity)
    else:
        identity.active, identity.can_register = body.active, body.can_register
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Identidade já cadastrada; atualize a lista")
    return {"id": str(identity.id)}


@router.get("/notes", dependencies=[admin])
def list_notes(db: Session = Depends(get_db)):
    return [{"id": str(n.id), "kind": n.kind, "content": n.content, "status": n.status,
             "user_id": str(n.user_id), "created_at": n.created_at, "confirmed_at": n.confirmed_at}
            for n in db.query(AssistantNote).order_by(AssistantNote.created_at.desc()).limit(100).all()]


@router.get("/queue", dependencies=[admin])
def list_queue(db: Session = Depends(get_db)):
    # No message bodies/private transcripts in this administrative queue view.
    result = []
    for kind, model in (("message", AssistantMessage), ("delivery", AssistantDelivery)):
        for item in db.query(model).order_by(model.created_at.desc()).limit(50).all():
            result.append({"id": str(item.id), "kind": kind, "channel": item.channel, "status": item.status,
                           "attempts": item.attempts, "error_code": item.error_code, "created_at": item.created_at})
    return result


@router.get("/actions", dependencies=[admin])
def list_actions(db: Session = Depends(get_db)):
    return [{"id": str(a.id), "kind": a.kind, "status": a.status, "user_id": str(a.user_id),
             "vendedor": a.payload.get("vendedor_nome"), "data": a.payload.get("data"),
             "tipo": a.payload.get("tipo"), "periodo": a.payload.get("periodo"),
             "created_at": a.created_at, "executed_at": a.executed_at,
             "result_id": str(a.result_id) if a.result_id else None}
            for a in db.query(AssistantAction).order_by(AssistantAction.created_at.desc()).limit(100).all()]


@router.post("/messages/{message_id}/retry", dependencies=[admin])
def retry_message(message_id: UUID, db: Session = Depends(get_db)):
    message = db.query(AssistantMessage).filter_by(id=message_id).with_for_update().first()
    if not message or message.status != "failed":
        raise HTTPException(409, "Somente mensagens com falha podem ser reprocessadas")
    message.status, message.attempts, message.error_code = "pending", 0, None
    message.available_at = utcnow()
    db.commit()
    return {"status": "pending"}
