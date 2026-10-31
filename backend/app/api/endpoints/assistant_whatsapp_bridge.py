"""Administrator pairing/configuration and narrowly scoped pull-agent endpoints."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ...database import get_db
from ...dependencies import require_role
from ...models.assistant import AssistantDelivery, AssistantWhatsAppBridge, utcnow
from ...services import assistant_whatsapp_bridge as bridge

router = APIRouter()
admin = Depends(require_role(["ADMIN"]))


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BridgeConfigInput(StrictInput):
    enabled: bool = False
    name: str = Field(default="WhatsApp Eleven", min_length=1, max_length=100)
    allow_private: bool = True
    notify_tracking: bool = False
    group_mode: Literal["mention", "all_authorized"] = "mention"
    allowed_groups: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("allowed_groups")
    @classmethod
    def group_identifiers(cls, values):
        if any(not bridge.GROUP.fullmatch(value) for value in values):
            raise ValueError("Informe identificadores válidos de grupos WhatsApp")
        return list(dict.fromkeys(values))


class GroupInfo(StrictInput):
    id: str = Field(pattern=r"^[0-9]{5,20}(?:-[0-9]{1,20})?@g\.us$")
    name: str = Field(min_length=1, max_length=100)


class HeartbeatInput(StrictInput):
    state: Literal["starting", "qr", "connected", "reconnecting", "logged_out", "error"]
    account_phone: str | None = Field(default=None, pattern=r"^\+[1-9][0-9]{6,14}$")
    agent_version: str | None = Field(default=None, max_length=40, pattern=r"^[a-zA-Z0-9._-]+$")
    error_code: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_]+$")
    qr: str | None = Field(default=None, max_length=3000)
    groups: list[GroupInfo] | None = Field(default=None, max_length=100)


class AttachmentInput(StrictInput):
    mime_type: Literal["image/jpeg", "image/png", "application/pdf"]
    data_base64: str = Field(min_length=1, max_length=6990508)


class IncomingInput(StrictInput):
    message_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.:-]+$")
    conversation_id: str = Field(min_length=1, max_length=120)
    sender_id: str = Field(pattern=r"^whatsapp:\+[1-9][0-9]{6,14}$")
    text: str = Field(default="", max_length=6000)
    should_reply: bool = True
    timestamp: datetime
    attachment: AttachmentInput | None = None


class ClaimInput(StrictInput):
    claim_key: UUID


class AckInput(ClaimInput):
    status: Literal["accepted", "uncertain", "failed"]
    provider_id: str | None = Field(default=None, max_length=120, pattern=r"^[a-zA-Z0-9_.:-]+$")
    error_code: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_]+$")


def no_store(response):
    response.headers["Cache-Control"] = "no-store"


def record_change(db, action):
    if db.info.get("audit_actor"):
        from ...services.user_audit import record
        record(db, action, "assistente", entity="assistant_whatsapp_bridges", entity_id="primary")


def retire_claims(db, row, *, release_claimed=True):
    active = db.query(AssistantDelivery).filter_by(channel=bridge.CHANNEL, bridge_id=row.id).filter(
        AssistantDelivery.status.in_(("claimed", "sending"))).with_for_update().all()
    for delivery in active:
        if delivery.status == "claimed":
            if release_claimed:
                delivery.status, delivery.bridge_id, delivery.bridge_claim_key = "pending", None, None
                delivery.error_code = "claim_released_by_admin"
        else:
            delivery.status, delivery.error_code = "uncertain", "session_changed_during_send"


def authenticated(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    return bridge.authenticate(db, authorization)


@router.get("/config", dependencies=[admin])
def get_config(response: Response, db: Session = Depends(get_db)):
    no_store(response)
    return bridge.public_config(bridge.bridge_config(db))


@router.put("/config", dependencies=[admin])
def save_config(body: BridgeConfigInput, response: Response, db: Session = Depends(get_db)):
    no_store(response)
    row = db.query(AssistantWhatsAppBridge).filter_by(id="primary").with_for_update().first()
    if not row:
        row = AssistantWhatsAppBridge(id="primary")
        db.add(row)
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    row.updated_at = utcnow()
    record_change(db, "whatsapp_configured")
    db.commit()
    return bridge.public_config(row)


@router.post("/credential", dependencies=[admin])
def rotate_credential(response: Response, db: Session = Depends(get_db)):
    no_store(response)
    row = db.query(AssistantWhatsAppBridge).filter_by(id="primary").with_for_update().first()
    if not row:
        row = AssistantWhatsAppBridge(id="primary")
        db.add(row)
        db.flush()
    retire_claims(db, row)
    token = secrets.token_urlsafe(48)
    row.token_hash = hashlib.sha256(token.encode()).hexdigest()
    row.pairing_qr, row.pairing_expires_at = None, None
    row.pairing_qr_hash = None
    row.updated_at = utcnow()
    record_change(db, "whatsapp_credential_rotated")
    db.commit()
    return {"token": token}


@router.post("/session/reset", dependencies=[admin])
def reset_session(response: Response, db: Session = Depends(get_db)):
    no_store(response)
    row = db.query(AssistantWhatsAppBridge).filter_by(id="primary").with_for_update().first()
    if not row:
        raise HTTPException(409, "Configure a ponte antes de preparar um novo vínculo")
    retire_claims(db, row, release_claimed=False)
    row.session_generation += 1
    row.pairing_qr, row.pairing_qr_hash, row.pairing_expires_at = None, None, None
    row.account_phone, row.last_seen_at, row.error_code = None, None, None
    row.discovered_groups, row.state, row.updated_at = [], "starting", utcnow()
    record_change(db, "whatsapp_session_reset")
    db.commit()
    return bridge.public_config(row)


@router.get("/pairing", dependencies=[admin])
def pairing(response: Response, db: Session = Depends(get_db)):
    no_store(response)
    row = bridge.bridge_config(db)
    result = bridge.pairing_image(row)
    if row and row.pairing_qr and not result["qr_image"]:
        row.pairing_qr, row.pairing_expires_at = None, None
        db.commit()
    return result


@router.post("/heartbeat")
def heartbeat(body: HeartbeatInput, response: Response, current=Depends(authenticated), db: Session = Depends(get_db)):
    no_store(response)
    row = bridge.lock_bridge(db, current)
    row.state, row.last_seen_at, row.error_code = body.state, utcnow(), body.error_code
    if body.account_phone:
        row.account_phone = body.account_phone
    if body.agent_version:
        row.agent_version = body.agent_version
    if body.groups is not None:
        row.discovered_groups = [item.model_dump() for item in body.groups]
    qr_hash = hashlib.sha256(body.qr.encode()).hexdigest() if body.qr else None
    if body.state == "qr" and body.qr and qr_hash != row.pairing_qr_hash:
        row.pairing_qr, row.pairing_expires_at = body.qr, utcnow() + timedelta(seconds=60)
        row.pairing_qr_hash = qr_hash
    elif body.state != "qr" or row.pairing_expires_at and bridge.aware(row.pairing_expires_at) <= utcnow():
        row.pairing_qr, row.pairing_expires_at = None, None
        if body.state != "qr":
            row.pairing_qr_hash = None
    result = bridge.agent_config(db, row)
    db.commit()
    return result


@router.post("/incoming")
async def incoming(request: Request, response: Response, current=Depends(authenticated), db: Session = Depends(get_db)):
    no_store(response)
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Formato não suportado")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 7_100_000:
            raise HTTPException(413, "Mensagem excede o limite de tamanho")
    try:
        body = IncomingInput.model_validate_json(bytes(data))
    except ValidationError:
        # Validation details can contain the entire attachment. Never reflect it.
        raise HTTPException(422, "Mensagem da ponte inválida") from None
    def persist():
        result = bridge.ingest(db, bridge.lock_bridge(db, current), body)
        db.commit()
        return result
    result = await run_in_threadpool(persist)
    return {"status": result}


@router.post("/claim")
def claim(body: ClaimInput, response: Response, current=Depends(authenticated), db: Session = Depends(get_db)):
    no_store(response)
    row = bridge.lock_bridge(db, current)
    result = bridge.claim(db, row, body.claim_key)
    db.commit()
    return {"delivery": result}


@router.post("/deliveries/{delivery_id}/start")
def start(delivery_id: UUID, body: ClaimInput, response: Response, current=Depends(authenticated), db: Session = Depends(get_db)):
    no_store(response)
    row = bridge.lock_bridge(db, current)
    delivery = bridge.claimed_delivery(db, row, delivery_id, body.claim_key)
    result = bridge.start(db, row, delivery)
    db.commit()
    return result


@router.post("/deliveries/{delivery_id}/ack")
def acknowledge(delivery_id: UUID, body: AckInput, response: Response, current=Depends(authenticated), db: Session = Depends(get_db)):
    no_store(response)
    row = bridge.lock_bridge(db, current)
    delivery = bridge.claimed_delivery(db, row, delivery_id, body.claim_key)
    result = bridge.acknowledge(db, delivery, body)
    db.commit()
    return result
