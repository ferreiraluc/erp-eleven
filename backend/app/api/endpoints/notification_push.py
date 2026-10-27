"""Authenticated device registration; no notification text or credentials in URLs."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_active_user
from ...models.usuario import Usuario
from ...services import notification_push as service

router = APIRouter(prefix="/api/notifications/push", tags=["notifications"])


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscribe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=1, max_length=4096)
    keys: PushKeys
    device_token: str = Field(min_length=32, max_length=128)
    device_name: str = Field(default="Navegador", max_length=100)


class PushUnsubscribe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str | None = Field(default=None, max_length=4096)
    device_token: str | None = Field(default=None, min_length=32, max_length=128)


@router.get("/config")
def config(user: Usuario = Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        public_key, _ = service.vapid_keys(db)
        db.commit()
        return {"available": True, "public_key": public_key}
    except ValueError:
        db.rollback()
        return {"available": False, "public_key": ""}


@router.post("/subscribe")
def subscribe(body: PushSubscribe, request: Request, user: Usuario = Depends(get_current_active_user), db: Session = Depends(get_db)):
    row = service.subscribe(db, user, request.state.auth_session_id, endpoint=body.endpoint,
                            p256dh=body.keys.p256dh, auth=body.keys.auth, device_token=body.device_token,
                            device_name=body.device_name)
    result = {"id": str(row.id), "user_id": str(row.user_id), "device_token": body.device_token, "active": True}
    db.commit()
    return result


@router.post("/unsubscribe")
def unsubscribe(body: PushUnsubscribe, request: Request, user: Usuario = Depends(get_current_active_user), db: Session = Depends(get_db)):
    count = service.unsubscribe(db, user.id, request.state.auth_session_id, endpoint=body.endpoint, device_token=body.device_token)
    db.commit()
    return {"disabled": count}
