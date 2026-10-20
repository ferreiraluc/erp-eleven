"""Staged receipt-printer cutover. Never changes address/label devices."""
import hashlib
import io
import secrets
import uuid
from datetime import timedelta
from fastapi import HTTPException
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from ..models.assistant import utcnow
from ..models.printing import PrintDevice, PrintJob
from ..models.usuario import Usuario
from .pdv_receipts import printer_info, receipt_state

MAC_AGENT_VERSION = '2026.10.20.1'
MAC_AGENT_URL = (
    'https://github.com/ferreiraluc/erp-eleven/releases/download/'
    f'print-macos-{MAC_AGENT_VERSION}/Eleven-Tickets-macOS-{MAC_AGENT_VERSION}.zip'
)


def owner_lock(db, user):
    db.query(Usuario).filter_by(id=user.id).with_for_update().one()


def list_devices(db):
    devices = db.query(PrintDevice).filter_by(purpose='tickets', active=True).order_by(PrintDevice.created_at).all()
    result = []
    for device in devices:
        test = db.query(PrintJob).filter_by(device_id=device.id, source='printer_test').order_by(
            PrintJob.created_at.desc(), PrintJob.id.desc()).first()
        result.append(dict(printer_info(device), last_test=receipt_state(test)))
    return {'devices': result, 'mac_package_url': MAC_AGENT_URL, 'mac_agent_version': MAC_AGENT_VERSION}


def prepare_mac(db, user):
    owner_lock(db, user)
    device = db.query(PrintDevice).filter_by(purpose='tickets', active=True, driver='escpos_tcp').first()
    token = None
    if not device:
        token = secrets.token_urlsafe(48)
        device = PrintDevice(name='3nStar RPT006W · iMac', purpose='tickets', driver='escpos_tcp',
                             token_hash=hashlib.sha256(token.encode()).hexdigest(),
                             paper_width_mm=80, paper_height_mm=0, auto_receipts=False)
        db.add(device)
        db.commit()
    return {'device': printer_info(device), 'token': token}


def enqueue_test(db, user, device_id, request_key, confirm):
    if not confirm:
        raise HTTPException(422, 'Confirme a impressão de teste na 3nStar.')
    device = db.query(PrintDevice).filter_by(id=device_id, purpose='tickets', active=True,
                                           driver='escpos_tcp').with_for_update().first()
    if not device:
        raise HTTPException(404, 'Prepare primeiro a impressora macOS.')
    existing = db.query(PrintJob).filter_by(request_key=request_key).first()
    if existing:
        if existing.device_id != device.id or existing.source != 'printer_test' or existing.user_id != user.id:
            raise HTTPException(409, 'Identificador já utilizado.')
        return receipt_state(existing)
    if db.query(PrintJob.id).filter_by(device_id=device.id).filter(PrintJob.status.in_(('pending', 'claimed'))).first():
        raise HTTPException(409, 'Aguarde a fila antes de solicitar outro teste.')
    job = PrintJob(id=uuid.uuid4(), device_id=device.id, user_id=user.id, request_key=request_key,
                   source='printer_test', snapshot={'width': 80, 'height': 0}, pdf=b'', sha256='',
                   expires_at=utcnow()+timedelta(hours=24))
    db.add(job)
    db.commit()
    return receipt_state(job)


def activate(db, user, device_id, test_job_id, confirm):
    if not confirm:
        raise HTTPException(422, 'Confirme o destino e a conferência física do teste.')
    owner_lock(db, user)
    # Lock all ticket destinations so checkouts cannot add jobs to the former
    # station between the empty-queue check and the atomic routing change.
    devices = db.query(PrintDevice).filter_by(purpose='tickets', active=True).order_by(
        PrintDevice.id).with_for_update().all()
    device = next((d for d in devices if d.id == device_id), None)
    if not device:
        raise HTTPException(404, 'Impressora de tickets não encontrada.')
    if device.driver == 'escpos_tcp':
        test = db.query(PrintJob).filter_by(id=test_job_id, device_id=device.id,
                                           source='printer_test', status='submitted').first()
        if not test:
            raise HTTPException(409, 'Imprima e confira o teste da 3nStar antes de ativar.')
        seen = device.last_seen_at
        if seen and seen.tzinfo is None:
            seen = seen.replace(tzinfo=utcnow().tzinfo)
        if not seen or seen < utcnow()-timedelta(minutes=2):
            raise HTTPException(409, 'O agente macOS precisa estar conectado antes da ativação.')
    former = [d.id for d in devices if d.auto_receipts and d.id != device.id]
    if former and db.query(PrintJob.id).filter(
            PrintJob.device_id.in_(former), PrintJob.status.in_(('pending', 'claimed'))).first():
        raise HTTPException(409, 'A fila anterior ainda tem trabalhos. Conclua-os antes de trocar o destino.')
    for current in devices:
        current.auto_receipts = False
    db.flush()  # Release the existing partial unique index before enabling the replacement.
    device.auto_receipts = True
    db.commit()
    return {'device': printer_info(device)}


def test_document(job_id):
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(80*mm, 130*mm), pageCompression=1)
    pdf.setFont('Helvetica-Bold', 23)
    pdf.drawCentredString(40*mm, 116*mm, 'ELEVEN')
    pdf.setFont('Helvetica', 10)
    for y, line in zip((103, 96, 89, 79, 72, 65, 51, 24), (
        'PRUEBA DE IMPRESORA', '3nStar RPT006W - ESC/POS', 'Papel continuo: 80 mm',
        'Inicio, centro y final legibles.', 'Crédito · Débito · Ñ · áéíóú',
        'Sin valor de venta.', 'Confirme el papel en el ERP.', str(job_id).replace('-', '')[:10].upper(),
    )):
        pdf.drawCentredString(40*mm, y*mm, line)
    from .pdv_receipt_layout import barcode
    code = barcode(str(job_id))
    code.drawOn(pdf, (80*mm-code.width)/2, 32*mm)
    pdf.line(5*mm, 15*mm, 75*mm, 15*mm)
    pdf.showPage()
    pdf.save()
    return output.getvalue()
