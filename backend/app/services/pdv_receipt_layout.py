"""One Spanish receipt presentation for preview, PDF download and Zebra jobs."""
import base64
import io
import math
from datetime import datetime
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether
from .pdv_ticket_identity import ticket_code

PAYMENTS = dict(cash_usd='Efectivo U$', cash_brl='Efectivo R$', cash_gs='Efectivo G$',
    cash_eur='Efectivo EUR', card_credit_py='Tarjeta de crédito PY', card_debit_py='Tarjeta de débito PY',
    qr_py='QR Máquina PY Débito', pix_personal='PIX (personal)', pix_thais='PIX (Thais)',
    maquina_thais='Máquina Thais', transfer_py='Transferencia PY', usdt='USDT',
    mercadopago='MercadoPago (enlace)', fiado='A cuenta (fiado)', cash='Efectivo',
    card='Tarjeta', pix='PIX', transfer='Transferencia', other='Otro')
STATES = dict(completed='Venta registrada', partially_refunded='Devolución parcial',
              refunded='Venta devuelta', cancelled='Venta anulada')


def number(value, decimals=2):
    return f'{Decimal(str(value or 0)):,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def money(value):
    return 'G$ ' + number(value, 0)


def barcode(sale_id):
    # Two dots per module at the Zebra's 203 dpi, including quiet zones; fits 50 mm media.
    return createBarcodeDrawing('Code128', value=ticket_code(sale_id), barWidth=72/203*2,
                                barHeight=12*mm, humanReadable=False, quiet=True, lquiet=72/203*20, rquiet=72/203*20)


def view(snapshot):
    from .pdv_usd import convert
    def money(value):
        usd = convert(value, snapshot.get('usd_rate_gs'))
        return 'US$ ' + (number(usd, 2) if usd is not None else '—')
    date = datetime.fromisoformat(snapshot['date'])
    if date.tzinfo:
        date = date.astimezone(ZoneInfo('America/Asuncion'))
    paid = sum(Decimal(p['total']) for p in snapshot['payments'])
    total = Decimal(snapshot['total'])
    card_fee = sum(Decimal(p.get('card_fee') or '0') for p in snapshot['payments'])
    state = snapshot.get('status', 'completed')
    return dict(
        title='ELEVEN', location='Shopping Paris - PY', email='contato@elevenparispy.com',
        code=ticket_code(snapshot['sale_id']), sale_id=snapshot['sale_id'], date=date.strftime('%d/%m/%Y %H:%M'),
        status=STATES.get(state, state), status_changed=state != 'completed', copy=bool(snapshot.get('copy')),
        items=[dict(name=i['name'], meta=' · '.join(str(v) for v in (i.get('size'), i.get('color')) if v),
                    calculation=f"{number(i['quantity'], 3).rstrip('0').rstrip(',')} × {money(i['unit'])}",
                    total=money(i['total']), discount=money(i['discount']) if Decimal(i.get('discount') or '0') > 0 else None,
                    returned=number(i.get('returned', 0), 3).rstrip('0').rstrip(',') if Decimal(i.get('returned') or '0') > 0 else None)
               for i in snapshot['items']],
        subtotal=money(snapshot['subtotal']), discount=money(snapshot['discount']) if Decimal(snapshot['discount']) > 0 else None,
        card_fee=money(card_fee) if card_fee else None, merchandise_total=money(total),
        total=money(total + card_fee), refunded=money(snapshot.get('refunded', 0)) if Decimal(snapshot.get('refunded') or '0') > 0 else None,
        payments=[dict(label=PAYMENTS.get(p['method'], 'Otro'), amount=f"{p['currency']} {number(p['amount'], 0 if p['currency'] in ('GS', 'PYG') else 2)}",
                       equivalent=money(Decimal(p['total']) + Decimal(p.get('card_fee') or '0')) if p['currency'] not in ('USD', 'USDT') else None) for p in snapshot['payments']],
        change=money(paid-total) if paid > total and state == 'completed' else None,
        seller=snapshot.get('seller') or 'No informado', customer=snapshot.get('customer') or 'Consumidor final',
        footer=['¡Gracias por su compra!', 'Conserve este comprobante para consultas.', '¡Esperamos su próxima visita!'],
        barcode='data:image/svg+xml;base64,' + base64.b64encode(barcode(snapshot['sale_id']).asString('svg').encode('utf-8')).decode('ascii'))


def render(snapshot):
    width, height = int(snapshot['width']), int(snapshot['height'])
    if not 50 <= width <= 104 or (height != 0 and not 50 <= height <= 400):
        raise ValueError('Formato de ticket inválido.')
    data = view(snapshot)
    output = io.BytesIO()
    doc = BaseDocTemplate(output, pagesize=(width*mm, (height or 991)*mm), leftMargin=3*mm, rightMargin=3*mm,
                            topMargin=7*mm, bottomMargin=7*mm, title='ELEVEN - Ticket de venta', author='ELEVEN')
    style = ParagraphStyle('ticket', fontName='Helvetica', fontSize=8, leading=10, spaceAfter=3, splitLongWords=True)
    strong = ParagraphStyle('strong', parent=style, fontName='Helvetica-Bold')
    small = ParagraphStyle('small', parent=style, fontSize=6.5, leading=8)
    center = ParagraphStyle('center', parent=style, alignment=1)
    logo = ParagraphStyle('logo', parent=center, fontName='Helvetica-Bold', fontSize=25, leading=28, spaceAfter=7)
    total_style = ParagraphStyle('total', parent=strong, fontSize=11, leading=14)
    story = []
    def paragraph(value, s=style):
        return Paragraph(escape(str(value)), s)
    def line(value, s=style):
        story.append(paragraph(value, s))
    def divider():
        story.extend([Spacer(1, 3), HRFlowable(width='100%', thickness=.5, color='#111111', dash=(2, 2)), Spacer(1, 5)])
    def pair(label, value, s=style):
        table = Table([[paragraph(label, s), paragraph(value, ParagraphStyle('value', parent=s, alignment=2))]],
                      colWidths=[doc.width*.53, doc.width*.47])
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0),
                                   ('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
        story.append(table)
    line(data['title'], logo)
    line(data['location'], center)
    line(data['email'], ParagraphStyle('email', parent=center, fontSize=7))
    line('Ticket: '+data['code']+' | '+data['date'], ParagraphStyle('identity', parent=center, fontSize=7))
    if data['copy']: line('COPIA', strong)
    if data['status_changed']: line(data['status'].upper(), strong)
    divider()
    for item in data['items']:
        line(item['name'], strong)
        if item['meta']: line(item['meta'], small)
        pair(item['calculation'], item['total'])
        if item['discount']: line('Descuento del artículo: '+item['discount'], small)
        if item['returned']: line('Cantidad devuelta: '+item['returned'], small)
        story.append(Spacer(1, 3))
    divider()
    totals_start = len(story)
    pair('Subtotal', data['subtotal'])
    if data['discount']: pair('Descuento', data['discount'])
    if data['card_fee']: pair('Recargo tarjeta (6%)', data['card_fee'])
    pair('TOTAL', data['total'], total_style)
    if data['refunded']: pair('Importe devuelto', data['refunded'])
    story[totals_start:] = [KeepTogether(story[totals_start:])]
    divider()
    line('PAGO', strong)
    for payment in data['payments']:
        pair(payment['label'], payment['amount'])
        if payment['equivalent']: pair('Equivalente', payment['equivalent'], small)
    if data['change']: pair('Cambio', data['change'])
    line('Vendedor: '+data['seller'])
    line('Cliente: '+data['customer'])
    divider()
    drawing = barcode(snapshot['sale_id'])
    drawing.hAlign = 'CENTER'
    # Keep the bars and their readable code together, never scale below two printer dots.
    story.append(KeepTogether([drawing, Spacer(1, 3), paragraph(data['code'], center)]))
    line('ID: '+data['sale_id'], small)
    divider()
    story.append(KeepTogether([paragraph(text, center) for text in data['footer']]))
    if height == 0:
        # Continuous media: measure the actual flowables, then draw exactly one page.
        # KeepTogether only affects the legacy fixed-label pagination below.
        flat = []
        for flowable in story:
            flat.extend(flowable._content if isinstance(flowable, KeepTogether) else [flowable])
        measure = Canvas(io.BytesIO())
        measured = []
        for flowable in flat:
            w, h = flowable.wrapOn(measure, doc.width, 100000)
            measured.append((flowable, w, h, flowable.getSpaceBefore(), flowable.getSpaceAfter()))
        height = max(50, math.ceil((sum(h+b+a for _, _, h, b, a in measured) + 8*mm) / mm))
        if height > 991:
            raise ValueError('O ticket excede 991 mm, o limite da Zebra ZD220 para um único comprovante. Reduza o conteúdo ou use outro formato de papel.')
        canvas = Canvas(output, pagesize=(width*mm, height*mm))
        canvas.setTitle('ELEVEN - Ticket de venta')
        canvas.setAuthor('ELEVEN')
        canvas.setViewerPreference('PrintScaling', 'None')
        y = height*mm - 4*mm
        for flowable, w, h, before, after in measured:
            y -= before + h
            flowable.drawOn(canvas, 3*mm, y, _sW=doc.width-w)
            y -= after
        canvas.showPage()
        canvas.save()
        return output.getvalue()
    def page(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 6)
        if document.page > 1:
            canvas.drawCentredString(width*mm/2, height*mm-4*mm, 'ELEVEN | Ticket '+data['code'])
        canvas.drawString(3*mm, 3*mm, 'Ticket '+data['code'])
        canvas.drawRightString((width-3)*mm, 3*mm, f'Pág. {document.page}')
        canvas.restoreState()
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='receipt', frames=[frame], onPage=page))
    doc.build(story)
    return output.getvalue()
