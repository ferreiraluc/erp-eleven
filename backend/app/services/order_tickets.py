"""Bag identification receipts on the existing 80 mm ticket queue.

No sale, stock movement or payment is created here. Copies are explicit and
request-keyed, and a queued snapshot never changes after the order is edited.
"""
import hashlib
import io
import math
from datetime import timedelta
from decimal import Decimal
from html import escape

from fastapi import HTTPException
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Spacer, HRFlowable, Table, TableStyle

from ..models.assistant import utcnow
from ..models.printing import PrintJob
from . import order_reservations, pdv_receipts
from .business_time import business_datetime
from .pdv_receipt_layout import number

SOURCE = 'order_reservation'


def snapshot(db, order):
    data = order_reservations.detail(db, order)
    # Only the bag document's fields, not live availability or full payment history.
    return {key: data[key] for key in (
        'id', 'numero_pedido', 'commerce_status', 'commerce_version', 'cliente_nome',
        'vendedor_nome', 'reserved_at', 'delivered_at', 'refund_due_gs',
        'usd_rate_gs', 'total_gs', 'paid_gs', 'balance_gs', 'notas',
    )} | {'width': 80, 'height': 0, 'items': [
        {key: item[key] for key in ('item_name', 'item_sku', 'item_size', 'item_color', 'quantity',
                                   'returned_quantity', 'remaining_quantity', 'location')}
        for item in data['items']]}


def render(data):
    """A single measured page; never reverse or split the bag ticket."""
    output = io.BytesIO()
    width = 74 * mm
    normal = ParagraphStyle('normal', fontName='Helvetica', fontSize=9, leading=12, spaceAfter=4)
    strong = ParagraphStyle('strong', parent=normal, fontName='Helvetica-Bold')
    small = ParagraphStyle('small', parent=normal, fontSize=7, leading=9)
    center = ParagraphStyle('center', parent=normal, alignment=1)
    title = ParagraphStyle('title', parent=center, fontName='Helvetica-Bold', fontSize=24, leading=28)
    customer = ParagraphStyle('customer', parent=strong, fontSize=16, leading=19, spaceAfter=8)
    story = []
    def paragraph(text, style=normal):
        return Paragraph(escape(str(text)), style)
    def line(text, style=normal):
        story.append(paragraph(text, style))
    def divider():
        story.extend([Spacer(1, 4), HRFlowable(width='100%', thickness=.5, color='#111111'), Spacer(1, 6)])
    def money(value):
        return 'US$ ' + number(Decimal(str(value)) / Decimal(str(data['usd_rate_gs'])), 2)

    conditional = bool(data.get('delivered_at'))
    remaining_label = 'Conservadas' if data['commerce_status'] == 'completed' else 'Por resolver'
    caption = 'ENTREGA EN CONDICIONAL' if conditional else 'PEDIDO SEPARADO'
    line('ELEVEN', title)
    line(caption, ParagraphStyle('caption', parent=center, fontName='Helvetica-Bold', fontSize=11))
    line(data['numero_pedido'], center)
    divider()
    status_label = {'cancelled': 'RESERVA CANCELADA', 'completed': 'VENTA YA CONCLUIDA',
                    'conditional': 'PENDIENTE DE RESOLUCIÓN', 'returned': 'PIEZAS DEVUELTAS'}
    if data['commerce_status'] in status_label:
        line(status_label[data['commerce_status']], strong)
    line(data['cliente_nome'], customer)
    line('Vendedor: ' + (data['vendedor_nome'] or '-'))
    line('Separado: ' + business_datetime(data['reserved_at']).strftime('%d/%m/%Y %H:%M'))
    if conditional:
        line('Entregado: ' + business_datetime(data['delivered_at']).strftime('%d/%m/%Y %H:%M'))
    line('Revisión: ' + str(data['commerce_version']), small)
    divider()
    for item in data['items']:
        table = Table([[paragraph(f"{item['quantity']} x", strong), paragraph(item['item_name'], strong)]], colWidths=[10*mm, width-10*mm])
        table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                  ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        story.append(table)
        line(' · '.join(str(value) for value in (item.get('item_size'), item.get('item_color'), 'Tienda' if item['location'] == 'loja' else 'Depósito') if value), small)
        if item.get('item_sku'):
            line(item['item_sku'], small)
        if conditional:
            line(f"Devueltas: {item.get('returned_quantity', 0)} · {remaining_label}: {item.get('remaining_quantity', item['quantity'])}", small)
        story.append(Spacer(1, 4))
    divider()
    line('Piezas: ' + str(sum(item['quantity'] for item in data['items'])), strong)
    if conditional:
        line('Devueltas: ' + str(sum(item.get('returned_quantity', 0) for item in data['items'])))
        line(remaining_label + ': ' + str(sum(item.get('remaining_quantity', item['quantity']) for item in data['items'])))
    line('Total del pedido: ' + money(data['total_gs']), strong)
    line('Recibido: ' + money(data['paid_gs']))
    line('Saldo pendiente: ' + money(data['balance_gs']), strong)
    if Decimal(str(data.get('refund_due_gs', 0))) > 0:
        line('A devolver al cliente: ' + money(data['refund_due_gs']), strong)
    if data.get('notas'):
        divider()
        line(data['notas'], small)
    divider()
    line('Piezas entregadas para elegir. Registre las devoluciones antes de concluir la venta.' if conditional
         else 'Reservado hasta la conclusión o cancelación del pedido.', center)
    line('Comprobante de control. No confirma una venta ni un nuevo pago.', ParagraphStyle('footer', parent=center, fontSize=7, leading=9))
    code = qr.QrCodeWidget('https://elevenparispy.com/#/pedidos?pedido_id=' + data['id'])
    bounds = code.getBounds()
    size = 23*mm
    drawing = Drawing(size, size, transform=[size/(bounds[2]-bounds[0]), 0, 0, size/(bounds[3]-bounds[1]), 0, 0])
    drawing.add(code)
    drawing.hAlign = 'CENTER'
    story.extend([Spacer(1, 4), drawing])
    line('Abrir pedido en el ERP', ParagraphStyle('qrlabel', parent=center, fontSize=7))
    measure = Canvas(io.BytesIO())
    measured = [(flow, *flow.wrapOn(measure, width, 100000), flow.getSpaceBefore(), flow.getSpaceAfter()) for flow in story]
    height = max(80, math.ceil((sum(h+b+a for _, _, h, b, a in measured)+8*mm)/mm))
    if height > 991:
        raise ValueError('O pedido excede o comprimento de um ticket contínuo (991 mm). Reduza as observações ou separe em pedidos menores.')
    canvas = Canvas(output, pagesize=(80*mm, height*mm))
    canvas.setTitle('ELEVEN - ' + caption + ' ' + data['numero_pedido'])
    canvas.setAuthor('ELEVEN')
    canvas.setViewerPreference('PrintScaling', 'None')
    y = height*mm-4*mm
    for flow, w, h, before, after in measured:
        y -= before + h
        flow.drawOn(canvas, 3*mm, y, _sW=width-w)
        y -= after
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def latest_job(db, order):
    return db.query(PrintJob).filter(PrintJob.source == SOURCE,
        PrintJob.snapshot['id'].as_string() == str(order.id)).order_by(PrintJob.created_at.desc(), PrintJob.id.desc()).first()


def state(db, order):
    return {'job': pdv_receipts.receipt_state(latest_job(db, order)),
            'printer': pdv_receipts.printer_info(pdv_receipts.destination(db))}


def enqueue(db, order, body, user):
    # Parent order lock serializes copies. Global request-key uniqueness remains
    # the final fence against another kind of job reusing this identity.
    existing = db.query(PrintJob).filter_by(request_key=body.request_id).first()
    if existing:
        if (existing.source != SOURCE or existing.user_id != user.id or
                (existing.snapshot or {}).get('id') != str(order.id) or
                existing.snapshot.get('commerce_version') != body.expected_version):
            raise HTTPException(409, 'Confirmação já utilizada em outro trabalho.')
        return existing
    if order.commerce_status not in ('reserved', 'conditional'):
        raise HTTPException(409, 'O pedido não está mais separado ou em condicional. Consulte seu histórico.')
    if body.expected_version != order.commerce_version:
        raise HTTPException(409, 'O pedido mudou. Atualize os dados antes de imprimir.')
    device = pdv_receipts.destination(db, lock=True)
    if not device:
        raise HTTPException(409, 'Nenhuma impressora de tickets está ativa. Baixe o PDF ou confira as configurações.')
    if device.paper_width_mm != 80 or device.paper_height_mm != 0:
        raise HTTPException(409, 'O ticket de separação requer bobina contínua de 80 mm.')
    previous = latest_job(db, order)
    if db.query(PrintJob.id).filter(PrintJob.source == SOURCE,
            PrintJob.snapshot['id'].as_string() == str(order.id), PrintJob.status.in_(('pending', 'claimed'))).first():
        raise HTTPException(409, 'Há um ticket deste pedido na fila. Confira o estado antes de pedir outra cópia.')
    data = snapshot(db, order)
    try:
        pdf = render(data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    job = PrintJob(device_id=device.id, user_id=user.id, request_key=body.request_id,
                   source=SOURCE, parent_id=previous.id if previous else None,
                   snapshot=data, pdf=pdf, sha256=hashlib.sha256(pdf).hexdigest(), expires_at=utcnow()+timedelta(hours=24))
    db.add(job)
    db.flush()
    return job
