"""Immutable receipt snapshots and device-scoped delivery; no printer I/O here."""
import hashlib
import io
import uuid
from datetime import timedelta
from decimal import Decimal
from html import escape

from fastapi import HTTPException
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from ..models.assistant import utcnow
from ..models.printing import PrintDevice, PrintJob
from ..models.pdv import PdvSale
from .access_policy import sales_query
from .print_diagnostics import diagnostic_message


PAYMENTS = dict(cash_usd='Dinheiro U$', cash_brl='Dinheiro R$', cash_gs='Dinheiro G$',
                cash_eur='Dinheiro EUR', card_credit_py='Cartão Crédito PY',
                card_debit_py='Cartão Débito PY', qr_py='QR Máquina PY Débito',
                pix_personal='PIX (pessoal)', pix_thais='PIX (Thais)',
                maquina_thais='Máquina Thais', transfer_py='Transferência PY',
                usdt='USDT', mercadopago='MercadoPago (link)', fiado='Anotar (fiado)')


def original_key(sale):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'eleven:pdv:receipt:{sale.id}:{sale.version}')


def printer_info(device):
    if not device:
        return None
    return dict(id=str(device.id), name=device.name, paper_width_mm=device.paper_width_mm,
                paper_height_mm=device.paper_height_mm, auto_receipts=device.auto_receipts,
                last_seen_at=device.last_seen_at)


def destination(db, *, lock=False):
    query = db.query(PrintDevice).filter_by(purpose='tickets', active=True, auto_receipts=True)
    return (query.with_for_update() if lock else query).first()


def receipt_state(job):
    return dict(id=str(job.id), status=job.status, diagnostic_message=diagnostic_message(job)) if job else None


def latest_job(db, sale):
    original = db.query(PrintJob).filter_by(request_key=original_key(sale)).first()
    if not original:
        return None
    return db.query(PrintJob).filter((PrintJob.id == original.id) | (PrintJob.parent_id == original.id)).order_by(
        PrintJob.created_at.desc(), PrintJob.id.desc()).first()


def authorized_sale(db, sale_id, user):
    sale = sales_query(db.query(PdvSale), PdvSale, user, pdv=True).filter(
        PdvSale.id == sale_id, PdvSale.deleted_at.is_(None)).with_for_update().first()
    if not sale:
        raise HTTPException(404, 'Venda não encontrada.')
    return sale


def enqueue(db, sale, user_id, *, copy_key=None):
    # Caller holds the sale lock (or is creating it). Unique key also guards retries.
    key = original_key(sale)
    previous = db.query(PrintJob).filter_by(request_key=key).first()
    if copy_key is None and previous:
        return previous
    if sale.status != 'completed':
        raise HTTPException(409, 'Esta venda foi alterada por devolução ou estorno. Consulte seu histórico.')
    device = destination(db, lock=True)
    if not device:
        return None
    if copy_key is not None:
        existing = db.query(PrintJob).filter_by(request_key=copy_key).first()
        if existing:
            if existing.source != 'pdv_receipt' or existing.user_id != user_id or (existing.snapshot or {}).get('sale_id') != str(sale.id):
                raise HTTPException(409, 'Identificador já utilizado em outra solicitação.')
            return existing
        if previous and db.query(PrintJob.id).filter(
                (PrintJob.id == previous.id) | (PrintJob.parent_id == previous.id),
                PrintJob.status.in_(('pending', 'claimed'))).first():
            raise HTTPException(409, 'O ticket anterior ainda está na fila. Aguarde antes de pedir outra cópia.')
        if not previous:
            raise HTTPException(409, 'Envie primeiro o ticket original.')
    snap = dict(sale_id=str(sale.id), version=sale.version, date=sale.created_at.isoformat(),
                customer=sale.cliente_nome, seller=sale.vendedor.nome if sale.vendedor else None,
                width=device.paper_width_mm, height=device.paper_height_mm,
                subtotal=str(sale.subtotal_gs), discount=str(sale.desconto_gs), total=str(sale.total_gs),
                items=[dict(name=i.item_name, size=i.item_size, color=i.item_color,
                            quantity=str(i.quantity), unit=str(i.unit_price_gs),
                            discount=str(i.discount_gs), total=str(i.total_gs)) for i in sale.items],
                payments=[dict(method=p.method, currency=p.currency, amount=str(p.amount_original),
                               total=str(p.amount_gs)) for p in sale.payments], copy=copy_key is not None)
    job = PrintJob(device_id=device.id, user_id=user_id, request_key=copy_key or key,
                   source='pdv_receipt', parent_id=previous.id if previous else None,
                   snapshot=snap, pdf=b'', sha256='', expires_at=utcnow()+timedelta(hours=24))
    db.add(job)
    db.flush()
    return job


def number(value, decimals=2):
    value = Decimal(str(value or 0))
    return f'{value:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def render(snapshot):
    """Fixed media pages, no image rasterization, no clipping of long item names."""
    width, height = int(snapshot['width']), int(snapshot['height'])
    if not 50 <= width <= 104 or not 50 <= height <= 400:
        raise ValueError('Formato de ticket inválido.')
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=(width*mm, height*mm),
                            leftMargin=3*mm, rightMargin=3*mm, topMargin=12*mm, bottomMargin=9*mm,
                            title='ELEVEN - Comprovante de venda', author='Eleven')
    style = ParagraphStyle('ticket', fontName='Helvetica', fontSize=8, leading=10, spaceAfter=3,
                           splitLongWords=True)
    bold = ParagraphStyle('total', parent=style, fontName='Helvetica-Bold', fontSize=10, leading=12)
    story = []
    def line(value, strong=False):
        story.append(Paragraph(escape(str(value)), bold if strong else style))
    def divider():
        story.extend([Spacer(1, 2), HRFlowable(width='100%', thickness=.4), Spacer(1, 4)])
    line('Ciudad del Este, Paraguay')
    from datetime import datetime
    from zoneinfo import ZoneInfo
    date = datetime.fromisoformat(snapshot['date'])
    if date.tzinfo:
        date = date.astimezone(ZoneInfo('America/Asuncion'))
    line(date.strftime('%d/%m/%Y %H:%M'))
    if snapshot.get('customer'): line('Cliente: '+snapshot['customer'])
    if snapshot.get('seller'): line('Vendedor: '+snapshot['seller'])
    if snapshot.get('copy'): line('SEGUNDA VIA', True)
    divider()
    for item in snapshot['items']:
        line(item['name'])
        meta = ' / '.join(v for v in (item.get('size'), item.get('color')) if v)
        if meta: line(meta)
        line(f"{number(item['quantity'], 3).rstrip('0').rstrip(',')} x G$ {number(item['unit'], 0)} = G$ {number(item['total'], 0)}")
        if Decimal(item['discount'] or '0') > 0:
            line('Desconto do item: G$ '+number(item['discount'], 0))
    divider()
    line('Subtotal: G$ '+number(snapshot['subtotal'], 0))
    if Decimal(snapshot['discount']) > 0: line('Desconto: G$ '+number(snapshot['discount'], 0))
    line('TOTAL: G$ '+number(snapshot['total'], 0), True)
    divider()
    for payment in snapshot['payments']:
        line(PAYMENTS.get(payment['method'], payment['method']))
        line(f"{payment['currency']} {number(payment['amount'])}")
        if payment['currency'] not in ('GS','PYG'): line('Equivalente: G$ '+number(payment['total'], 0))
    change = sum(Decimal(p['total']) for p in snapshot['payments']) - Decimal(snapshot['total'])
    if change > 0: line('Troco: G$ '+number(change, 0))
    divider()
    line('Obrigado pela sua compra!')
    def page(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawCentredString(width*mm/2, height*mm-6*mm, 'ELEVEN')
        canvas.setFont('Helvetica', 6)
        canvas.drawString(3*mm, 4*mm, 'Venda #'+snapshot['sale_id'][-8:].upper())
        canvas.drawRightString((width-3)*mm, 4*mm, f'Pág. {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return output.getvalue()


def prepare_document(job):
    if job.source == 'pdv_receipt' and not job.pdf:
        job.pdf = render(job.snapshot)
        job.sha256 = hashlib.sha256(job.pdf).hexdigest()
