"""Private printer API. Device credentials cannot query any other ERP data."""
import hashlib
import secrets
from datetime import timedelta
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Header, Response, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ...database import get_db
from ...dependencies import require_role
from ...models.printing import PrintDevice, PrintJob
from ...models.assistant import utcnow

router = APIRouter()
administrator = require_role(["ADMIN"])


def printer(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or len(token) < 32:
        raise HTTPException(401, "Credencial da impressora necessária")
    device = db.query(PrintDevice).filter_by(
        token_hash=hashlib.sha256(token.encode()).hexdigest(), active=True).first()
    if not device:
        raise HTTPException(401, "Dispositivo não autorizado")
    return device


class DeviceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.post("/devices")
def create_device(body: DeviceInput, user=Depends(administrator), db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(48)
    device = PrintDevice(name=body.name, token_hash=hashlib.sha256(token.encode()).hexdigest())
    db.add(device)
    db.commit()
    return {"id": str(device.id), "name": device.name, "token": token}


@router.get("/devices")
def devices(user=Depends(administrator), db: Session = Depends(get_db)):
    return [{"id": str(d.id), "name": d.name, "active": d.active, "last_seen_at": d.last_seen_at}
            for d in db.query(PrintDevice).order_by(PrintDevice.created_at).all()]


@router.post("/devices/{device_id}/revoke")
def revoke(device_id: UUID, user=Depends(administrator), db: Session = Depends(get_db)):
    device = db.get(PrintDevice, device_id)
    if not device:
        raise HTTPException(404, "Dispositivo não encontrado")
    device.active = False
    db.commit()
    return {"active": False}


@router.post("/jobs")
async def enqueue(device_id: UUID = Form(...), request_key: UUID = Form(...),
                  file: UploadFile = File(...), user=Depends(administrator), db: Session = Depends(get_db)):
    # The per-device lock serializes enqueue requests and provides idempotency.
    device = db.query(PrintDevice).filter_by(id=device_id, active=True).with_for_update().first()
    if not device:
        raise HTTPException(404, "Impressora não cadastrada")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024 or not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Envie um PDF de até 5 MB")
    digest = hashlib.sha256(content).hexdigest()
    previous = db.query(PrintJob).filter_by(request_key=request_key).first()
    if previous:
        if previous.device_id != device_id or previous.user_id != user.id or previous.sha256 != digest:
            raise HTTPException(409, "Identificador já utilizado para outro trabalho")
        return {"id": str(previous.id), "status": previous.status}
    job = PrintJob(device_id=device_id, user_id=user.id, request_key=request_key,
                   pdf=content, sha256=digest, expires_at=utcnow() + timedelta(hours=24))
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Identificador já utilizado; consulte o trabalho original")
    return {"id": str(job.id), "status": job.status}


@router.get("/jobs")
def jobs(user=Depends(administrator), db: Session = Depends(get_db)):
    return [{"id": str(j.id), "device_id": str(j.device_id), "status": j.status,
             "created_at": j.created_at, "claimed_at": j.claimed_at, "finished_at": j.finished_at}
            for j in db.query(PrintJob).order_by(PrintJob.created_at.desc()).limit(100).all()]


@router.post("/agent/claim")
def claim(device=Depends(printer), db: Session = Depends(get_db)):
    from ...services.assistant_documents import cleanup_documents
    cleanup_documents(db)
    # Claim is permanent. Lost responses never cause a job to be dispatched again.
    device.last_seen_at = utcnow()
    db.query(PrintJob).filter(PrintJob.device_id == device.id, PrintJob.status == "pending",
                             PrintJob.expires_at <= utcnow()).update({"status": "expired", "pdf": b""})
    job = db.query(PrintJob).filter_by(device_id=device.id, status="pending").order_by(
        PrintJob.created_at, PrintJob.id).with_for_update(skip_locked=True).first()
    if not job:
        db.commit()
        return Response(status_code=204)
    job.status, job.claimed_at = "claimed", utcnow()
    result = {"id": str(job.id), "sha256": job.sha256}
    db.commit()
    return result


@router.get("/agent/jobs/{job_id}/pdf")
def document(job_id: UUID, device=Depends(printer), db: Session = Depends(get_db)):
    job = db.query(PrintJob).filter_by(id=job_id, device_id=device.id, status="claimed").first()
    if not job:
        raise HTTPException(404, "Trabalho indisponível")
    if job.source=='bot_pdf_ephemeral':
        from ...services.assistant_documents import ephemeral_pdf
        try:data=ephemeral_pdf(job)
        except ValueError as exc:raise HTTPException(410,str(exc)) from None
    else:data=job.pdf
    return Response(data, media_type="application/pdf", headers={"Cache-Control": "no-store"})


class ResultInput(BaseModel):
    status: Literal["submitted", "failed", "uncertain"]


@router.post("/agent/jobs/{job_id}/result")
def result(job_id: UUID, body: ResultInput, device=Depends(printer), db: Session = Depends(get_db)):
    job = db.query(PrintJob).filter_by(id=job_id, device_id=device.id).with_for_update().first()
    if not job:
        raise HTTPException(404, "Trabalho não encontrado")
    if job.status == body.status:
        return {"status": job.status}
    if job.status != "claimed":
        raise HTTPException(409, "Trabalho já finalizado")
    job.status, job.finished_at = body.status, utcnow()
    # Erase recipient data once the local agent no longer needs the document.
    job.pdf = b""
    if job.source=='bot_pdf_ephemeral':job.snapshot=None
    db.commit()
    return {"status": job.status}
