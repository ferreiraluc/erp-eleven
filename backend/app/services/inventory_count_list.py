"""A4 count sheets share the document queue and never change stock balances."""
import hashlib
import hmac
import io
import json
import re
from datetime import timedelta
from html import escape

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..models.assistant import utcnow
from ..models.inventory import Item
from ..models.printing import PrintDevice, PrintJob
from ..schemas.inventory_count_list import CountSnapshot, MAX_ITEMS
from .print_diagnostics import diagnostic_message
from .business_time import business_datetime

SOURCE = 'inventory_list'
MAX_PDF_BYTES = 5 * 1024 * 1024
PREVIEW_TTL = timedelta(hours=1)


def _json(snapshot):
    if isinstance(snapshot, CountSnapshot):
        snapshot = snapshot.model_dump(mode='json')
    return json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def signature(snapshot):
    return hmac.new(settings.SECRET_KEY.encode(), b'eleven:inventory-count-list:v1\0' + _json(snapshot), hashlib.sha256).hexdigest()


def verify(body, user_id, *, check_expiry=True):
    snapshot = body.snapshot
    if snapshot.user_id != user_id or not hmac.compare_digest(body.signature, signature(snapshot)):
        raise HTTPException(403, 'Esta prévia não pertence ao usuário ou foi alterada. Gere a lista novamente.')
    if check_expiry and (snapshot.created_at > utcnow() + timedelta(seconds=30)
                         or utcnow() - snapshot.created_at > PREVIEW_TTL):
        raise HTTPException(409, 'Esta prévia expirou. Gere a lista novamente para conferir os saldos atuais.')
    return snapshot.model_dump(mode='json')


def document_devices(db):
    return db.query(PrintDevice).filter_by(active=True, purpose='documents', driver='windows').order_by(
        PrintDevice.name, PrintDevice.id).all()


def device_view(device):
    return {'id': str(device.id), 'name': device.name,
            'last_seen_at': device.last_seen_at.isoformat() if device.last_seen_at else None}


def preview(db, user_id, item_ids):
    # Explicit projection prevents original photos, prices or relationships from
    # entering the report query, including for products outside the visible page.
    ids = list(dict.fromkeys(item_ids))
    if not ids or len(ids) > MAX_ITEMS:
        raise HTTPException(422, f'Selecione de 1 a {MAX_ITEMS} produtos por lista.')
    rows = db.query(Item.id, Item.inventory_code, Item.sku_internal, Item.name,
                    Item.color, Item.size, Item.location, Item.stock_loja, Item.stock_deposito).filter(
        Item.id.in_(ids), Item.deleted_at.is_(None)).all()
    if {row.id for row in rows} != set(ids):
        raise HTTPException(409, 'Um produto selecionado foi excluído ou não existe. Atualize a seleção; nenhuma lista parcial foi gerada.')
    by_id = {row.id: row for row in rows}
    items = [{'id': str(row.id), 'code': row.inventory_code or row.sku_internal,
              'name': row.name, 'color': row.color, 'size': row.size, 'location': row.location,
              'stock_loja': row.stock_loja, 'stock_deposito': row.stock_deposito} for row in (by_id[key] for key in ids)]
    totals = {'items': len(items)}
    for field, unknown in [('stock_loja', 'unknown_loja'), ('stock_deposito', 'unknown_deposito')]:
        totals[field] = sum(row[field] for row in items if row[field] is not None)
        totals[unknown] = sum(row[field] is None for row in items)
    try:
        snapshot = CountSnapshot.model_validate({'version': 1, 'user_id': user_id, 'created_at': utcnow(),
                                                 'items': items, 'totals': totals}).model_dump(mode='json')
    except ValidationError:
        raise HTTPException(409, 'Há um produto com dados inválidos na seleção. Confira seu cadastro antes de gerar a lista.') from None
    devices = document_devices(db)
    hp = [device for device in devices if re.search(r'\bhp\b|hewlett', device.name, re.I)]
    suggested = hp[0] if len(hp) == 1 else devices[0] if len(devices) == 1 else None
    return {'snapshot': snapshot, 'signature': signature(snapshot), 'devices': [device_view(d) for d in devices],
            'suggested_device_id': str(suggested.id) if suggested else None,
            'filename': 'eleven-conferencia-estoque.pdf'}


def render(snapshot):
    """Deterministic PDF from the approved snapshot, including after PDF cleanup."""
    snapshot = CountSnapshot.model_validate(snapshot)
    created = business_datetime(snapshot.created_at).strftime('%d/%m/%Y %H:%M')
    buffer = io.BytesIO()
    margin = 12 * mm
    body = ParagraphStyle('count-body', fontName='Helvetica', fontSize=8.2, leading=10.5, spaceAfter=0)
    small = ParagraphStyle('count-small', parent=body, fontSize=7.2, leading=9, textColor=colors.HexColor('#52525b'))
    center = ParagraphStyle('count-number', parent=body, alignment=TA_CENTER, fontSize=9)
    head = ParagraphStyle('count-head', parent=body, alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=7.5, leading=9)
    summary = ParagraphStyle('count-summary', parent=body, fontSize=8.3, leading=11)
    def safe(value):
        # Imported names may contain line breaks; wrap normal text instead of
        # creating a single row taller than the printable page.
        return escape(' '.join(str(value).split()))
    def paragraph(value, style=body):
        return Paragraph(safe(value), style)
    def stock(value):
        return paragraph('Não inf.' if value is None else str(value), small if value is None else center)
    def footer(c, document):
        c.saveState()
        c.setFont('Helvetica-Bold', 17)
        c.drawString(margin, A4[1] - 17 * mm, 'ELEVEN')
        c.setFont('Helvetica-Bold', 10)
        c.drawRightString(A4[0] - margin, A4[1] - 16 * mm, 'CONFERÊNCIA DE ESTOQUE')
        c.setFont('Helvetica', 8)
        c.drawString(margin, A4[1] - 23 * mm, f'Saldos registrados em {created} - {snapshot.totals.items} produtos')
        c.setStrokeColor(colors.HexColor('#a1a1aa'))
        c.line(margin, A4[1] - 26 * mm, A4[0] - margin, A4[1] - 26 * mm)
        c.setFont('Helvetica', 7)
        c.setFillColor(colors.HexColor('#52525b'))
        c.drawString(margin, 9 * mm, 'Conferência física: preencha as colunas em branco. Esta lista não altera o estoque.')
        c.drawRightString(A4[0] - margin, 9 * mm, f'Página {document.page}')
        c.restoreState()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=margin, rightMargin=margin,
                                 topMargin=29 * mm, bottomMargin=15 * mm, title='Eleven - Conferência de estoque',
                                 author='ERP Eleven', pageCompression=1, invariant=1)
    totals = snapshot.totals
    def total_text(label, count, unknown):
        return f'{label}: {count} unidades conhecidas' + (f' + {unknown} saldo(s) não informado(s)' if unknown else '')
    story = [paragraph(total_text('Loja', totals.stock_loja, totals.unknown_loja), summary),
             paragraph(total_text('Depósito', totals.stock_deposito, totals.unknown_deposito), summary),
             paragraph('Responsável: __________________________  Data da contagem: ____ / ____ / ______', small), Spacer(1, 4 * mm)]
    data = [[paragraph('#', head), paragraph('Código interno', head), paragraph('Produto / variante', head),
             paragraph('Saldo no sistema', head), '', paragraph('Contagem física', head), ''],
            ['', '', '', paragraph('Loja', head), paragraph('Depósito', head), paragraph('Loja', head), paragraph('Depósito', head)]]
    for index, item in enumerate(snapshot.items, 1):
        details = []
        if item.size: details.append('Tam.: ' + item.size)
        if item.color: details.append('Cor: ' + item.color)
        product = [paragraph(item.name)]
        if details: product.append(paragraph(' | '.join(details), small))
        if item.location: product.append(paragraph('Localização: ' + item.location, small))
        data.append([paragraph(index, small), paragraph(item.code, small), product,
                     stock(item.stock_loja), stock(item.stock_deposito), '', ''])
    columns = [7, 27, 76, 18, 20, 19, 19]
    table = LongTable(data, colWidths=[value * mm for value in columns], repeatRows=2, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (2, 0), (2, 1)),
        ('SPAN', (3, 0), (4, 0)), ('SPAN', (5, 0), (6, 0)),
        ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#e4e4e7')),
        ('BACKGROUND', (3, 2), (4, -1), colors.HexColor('#f4f4f5')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b8b8be')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 1), 4), ('BOTTOMPADDING', (0, 0), (-1, 1), 4),
        ('TOPPADDING', (0, 2), (-1, -1), 7), ('BOTTOMPADDING', (0, 2), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    content = buffer.getvalue()
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(422, 'A lista ultrapassou o limite de 5 MB da impressora. Divida a seleção em listas menores.')
    return content


def job_view(db, job):
    device = db.get(PrintDevice, job.device_id)
    return {'id': str(job.id), 'status': job.status, 'device_id': str(job.device_id),
            'device_name': device.name if device else 'Impressora A4', 'created_at': job.created_at.isoformat(),
            'diagnostic_message': diagnostic_message(job)}


def owned_job(db, user_id, job_id):
    job = db.query(PrintJob).filter_by(id=job_id, user_id=user_id, source=SOURCE).first()
    if not job:
        raise HTTPException(404, 'Lista de impressão não encontrada para este usuário.')
    return job


def enqueue(db, user, body):
    snapshot = verify(body, user.id, check_expiry=False)
    # Serialize the request before expiry/device checks. In particular, a retry
    # cannot declare the request unqueued while another tab is still rendering it.
    if db.get_bind().dialect.name == 'postgresql':
        lock = int.from_bytes(hashlib.sha256(b'inventory-count-list:' + body.request_key.bytes).digest()[:8], 'big', signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
    def previous_job():
        previous = db.query(PrintJob).filter_by(request_key=body.request_key).populate_existing().first()
        if previous and (previous.source != SOURCE or previous.user_id != user.id
                         or previous.device_id != body.device_id or _json(previous.snapshot) != _json(snapshot)):
            raise HTTPException(409, 'Identificador já utilizado para outra impressão. Recupere a solicitação original.')
        return previous
    previous = previous_job()
    if previous:
        return job_view(db, previous)
    try:
        verify(body, user.id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        raise HTTPException(409, {'code': 'inventory_count_preview_expired', 'message': exc.detail,
                                  'not_queued': True}) from None
    content = render(snapshot)
    device = db.query(PrintDevice).filter_by(id=body.device_id, active=True, purpose='documents', driver='windows').with_for_update().first()
    if not device:
        raise HTTPException(409, {'code': 'inventory_count_device_unavailable',
                                  'message': 'Selecione uma impressora A4 ativa. Tickets e etiquetas não recebem esta lista.',
                                  'not_queued': True})
    previous = previous_job()
    if previous:
        return job_view(db, previous)
    job = PrintJob(device_id=device.id, user_id=user.id, request_key=body.request_key,
                   source=SOURCE, snapshot=snapshot, pdf=content,
                   sha256=hashlib.sha256(content).hexdigest(), expires_at=utcnow() + timedelta(hours=24))
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = previous_job()
        if previous:
            return job_view(db, previous)
        raise HTTPException(409, 'A solicitação já está sendo processada. Recupere a mesma impressão.') from None
    return job_view(db, job)
