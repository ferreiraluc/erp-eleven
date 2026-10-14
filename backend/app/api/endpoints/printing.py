"""Private printer API. Device credentials cannot query any other ERP data."""
import hashlib
import secrets
import io
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import timedelta
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Header, Response, UploadFile, File, Form
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ...database import get_db
from ...dependencies import require_role, require_owner, get_current_active_user
from ...models.printing import PrintDevice, PrintJob
from ...models.assistant import utcnow
from ...services.print_diagnostics import PrintDiagnostic, diagnostic_message

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
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('Informe um nome de impressora válido')
        return value


class ConnectInput(DeviceInput):
    profile: Literal['documents', 'tickets'] = 'documents'


class ReceiptDeviceInput(DeviceInput):
    paper_width_mm: int = Field(default=60, ge=50, le=104)
    paper_height_mm: int = Field(default=80, ge=50, le=400)
    auto_receipts: bool = False


@router.get('/receipt-device')
def receipt_device(user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    from ...services.pdv_receipts import printer_info
    device = db.query(PrintDevice).filter_by(purpose='tickets', active=True).order_by(
        PrintDevice.auto_receipts.desc(), PrintDevice.created_at).first()
    return {'device': printer_info(device)}


@router.put('/receipt-device')
def configure_receipt_device(body: ReceiptDeviceInput, response: Response, user=Depends(require_owner), db: Session = Depends(get_db)):
    from ...services.pdv_receipts import printer_info
    # One ticket station in this first version. Serialize configuration on the owner.
    from ...models.usuario import Usuario
    db.query(Usuario).filter_by(id=user.id).with_for_update().first()
    device = db.query(PrintDevice).filter_by(purpose='tickets', active=True).order_by(PrintDevice.created_at).with_for_update().first()
    token = None
    if not device:
        token = secrets.token_urlsafe(48)
        device = PrintDevice(purpose='tickets', token_hash=hashlib.sha256(token.encode()).hexdigest())
        db.add(device)
    if device.id and (device.paper_width_mm != body.paper_width_mm or device.paper_height_mm != body.paper_height_mm):
        if db.query(PrintJob.id).filter(PrintJob.device_id == device.id, PrintJob.status.in_(('pending', 'claimed'))).first():
            raise HTTPException(409, 'Aguarde a fila terminar antes de trocar o tamanho do papel.')
    for key, value in body.model_dump().items():
        setattr(device, key, value)
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'device': printer_info(device), 'token': token}


@router.post('/receipt-device/credential')
def rotate_receipt_credential(response: Response, confirm: bool = False, user=Depends(require_owner), db: Session = Depends(get_db)):
    if not confirm:
        raise HTTPException(422, 'Confirme a substituição da credencial e a atualização no Windows.')
    device = db.query(PrintDevice).filter_by(purpose='tickets', active=True).with_for_update().first()
    if not device:
        raise HTTPException(404, 'Configure primeiro a impressora de tickets.')
    if db.query(PrintJob.id).filter_by(device_id=device.id, status='claimed').first():
        raise HTTPException(409, 'Aguarde o trabalho em processamento antes de trocar a credencial.')
    token = secrets.token_urlsafe(48)
    device.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'token': token}


@router.get('/agent-package')
def agent_package(profile: Literal['documents', 'tickets'] = 'documents', user=Depends(administrator)):
    root = Path(__file__).resolve().parents[4] / 'tools' / 'eleven-print-agent'
    files = ('Instalar.cmd', 'Instalar.ps1', 'Configuracao.ps1', 'Agente.ps1', 'Impressao.ps1', 'LEIA-ME.txt')
    if not all((root / name).is_file() for name in files):
        raise HTTPException(503, 'Pacote do agente indisponível nesta instalação')
    data = io.BytesIO()
    with ZipFile(data, 'w', compression=ZIP_DEFLATED) as archive:
        for name in files:
            if name == 'Instalar.cmd' and profile == 'tickets':
                contents = (root / name).read_text().replace('"%~dp0Instalar.ps1"', '"%~dp0Instalar.ps1" -Profile tickets')
                archive.writestr('Eleven-Impressao/' + name, contents.replace('\n', '\r\n'))
            elif name == 'Instalar.ps1' and profile == 'tickets':
                # Preserve the profile even when opened via "Run with PowerShell".
                contents = (root / name).read_text().replace("$AgentProfile = 'documents'", "$AgentProfile = 'tickets'", 1)
                archive.writestr('Eleven-Impressao/' + name, contents.replace('\n', '\r\n'))
            else:
                archive.write(root / name, 'Eleven-Impressao/' + name)
    return Response(data.getvalue(), media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="Eleven-Impressao-Windows.zip"',
        'Cache-Control': 'no-store',
    })


@router.post('/agent/connect')
def connect(body: ConnectInput, device=Depends(printer), db: Session = Depends(get_db)):
    # The scoped credential may rename only its own device; IDs/jobs/tokens survive replacement.
    if body.profile != device.purpose:
        raise HTTPException(409, 'Credencial de outra finalidade. Use o instalador e a credencial exclusivos desta impressora.')
    device.name = body.name
    device.last_seen_at = utcnow()
    db.commit()
    data = {'id': str(device.id), 'name': device.name}
    if device.purpose == 'tickets':
        data.update(profile='tickets', paper_width_mm=device.paper_width_mm, paper_height_mm=device.paper_height_mm)
    return data


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
    device.auto_receipts = False
    db.commit()
    return {"active": False}


@router.post("/jobs")
async def enqueue(device_id: UUID = Form(...), request_key: UUID = Form(...),
                  file: UploadFile = File(...), user=Depends(administrator), db: Session = Depends(get_db)):
    # The per-device lock serializes enqueue requests and provides idempotency.
    device = db.query(PrintDevice).filter_by(id=device_id, active=True, purpose='documents').with_for_update().first()
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
             "diagnostic": j.diagnostic, "diagnostic_message": diagnostic_message(j),
             "created_at": j.created_at, "claimed_at": j.claimed_at, "finished_at": j.finished_at}
            for j in db.query(PrintJob).order_by(PrintJob.created_at.desc()).limit(100).all()]


@router.post("/agent/claim")
def claim(device=Depends(printer), db: Session = Depends(get_db)):
    from ...services.assistant_documents import cleanup_documents
    authenticated_hash = device.token_hash
    device = db.query(PrintDevice).filter_by(id=device.id, active=True).populate_existing().with_for_update().first()
    if not device or device.token_hash != authenticated_hash:
        raise HTTPException(401, 'Credencial substituída ou revogada.')
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
    from ...services.pdv_receipts import prepare_document
    try:
        prepare_document(job)
    except Exception:
        # A malformed historical snapshot must not block the device's entire queue.
        job.status, job.finished_at = 'failed', utcnow()
        job.diagnostic = {'code': 'document_generation_failed'}
        db.commit()
        return Response(status_code=204)
    job.status, job.claimed_at = "claimed", utcnow()
    result = {"id": str(job.id), "sha256": job.sha256}
    if job.source == 'pdv_receipt':
        result.update(profile='tickets', paper_width_mm=job.snapshot['width'], paper_height_mm=job.snapshot['height'])
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
    diagnostic: PrintDiagnostic | None = None


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
    job.diagnostic = body.diagnostic.model_dump() if body.diagnostic else None
    # Erase recipient data once the local agent no longer needs the document.
    job.pdf = b""
    if job.source=='bot_pdf_ephemeral':job.snapshot=None
    db.commit()
    return {"status": job.status}
