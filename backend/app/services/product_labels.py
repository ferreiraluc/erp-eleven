"""60 × 30 mm internal labels. Snapshots, bounded batches and no stock writes."""
import hashlib
import json
import re
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import load_only

from ..models.assistant import utcnow
from ..models.inventory import Item
from ..models.printing import PrintDevice, PrintJob
from .print_diagnostics import diagnostic_message
from .receipt_printer_setup import owner_lock

PURPOSE = 'product_labels'
MAX_ITEMS = 500
MAX_LABELS = 2000
MAX_COPIES = 100
CODE = re.compile(r'^INV-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$')
FIELDS = (Item.id, Item.name, Item.inventory_code, Item.color, Item.size,
          Item.group_key, Item.stock_loja, Item.stock_deposito, Item.current_stock,
          Item.sale_price, Item.sale_currency, Item.barcode)


def items_query(db):
    return db.query(Item).options(load_only(*FIELDS, raiseload=True)).filter(
        Item.deleted_at.is_(None), Item.is_active.is_(True))


def item_view(item):
    view = {field.key: getattr(item, field.key) for field in FIELDS}
    view['sale_price'] = str(Decimal(item.sale_price or 0).quantize(Decimal('0.01')))
    view['sale_currency'] = (item.sale_currency or 'USD').upper()
    return view


def device_view(device):
    if not device:
        return None
    return dict(id=str(device.id), name=device.name, last_seen_at=device.last_seen_at,
                paper_width_mm=60, paper_height_mm=30)


def destination(db, lock=False):
    query = db.query(PrintDevice).filter_by(purpose=PURPOSE, active=True, driver='windows')
    return (query.with_for_update() if lock else query).first()


def configure(db, user, confirm, rotate=False):
    if not confirm:
        raise HTTPException(422, 'Confirme o uso exclusivo da Zebra para etiquetas de produtos.')
    owner_lock(db, user)
    # Same order as receipt cutover; never leave a sale pointing at relabelled media.
    devices = db.query(PrintDevice).filter(PrintDevice.active.is_(True)).order_by(
        PrintDevice.id).with_for_update().all()
    device = next((d for d in devices if d.purpose == PURPOSE), None)
    token = None
    if not device:
        zebras = [d for d in devices if d.purpose == 'tickets' and d.driver == 'windows'
                  and re.search(r'zebra|zdesigner|zd220', d.name, re.I)]
        if len(zebras) > 1:
            raise HTTPException(409, 'Há mais de uma Zebra de tickets. Revise os destinos antes da migração.')
        if zebras:
            if not any(d.purpose == 'tickets' and d.driver == 'escpos_tcp' and d.auto_receipts for d in devices):
                raise HTTPException(409, 'Ative a 3nStar para tickets antes de reservar a Zebra para etiquetas.')
            device = zebras[0]
            if db.query(PrintJob.id).filter(PrintJob.device_id == device.id,
                    PrintJob.status.in_(('pending', 'claimed'))).first():
                raise HTTPException(409, 'A Zebra ainda tem tickets pendentes. Conclua a fila antes de trocar o papel.')
        else:
            device = PrintDevice(name='Zebra ZD220 · Etiquetas', driver='windows')
            db.add(device)
        device.purpose, device.auto_receipts = PURPOSE, False
        device.paper_width_mm, device.paper_height_mm = 60, 30
        rotate = True  # Revoke the old ticket agent, preserving device/job history.
    if rotate:
        if device.id and db.query(PrintJob.id).filter_by(device_id=device.id, status='claimed').first():
            raise HTTPException(409, 'Aguarde o trabalho em processamento antes de substituir a credencial.')
        token = secrets.token_urlsafe(48)
        device.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    return dict(device=device_view(device), token=token)


def clean(value):
    return ' '.join(str(value or '').split())


def wrapped(text, height, lines):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    remaining, output = clean(text), []
    # Reserve whitespace before the QR; wide letters cannot overflow into it.
    while remaining and len(output) < lines:
        count = 1
        while count <= len(remaining) and stringWidth(remaining[:count], 'Helvetica', height)*1.12 <= 278:
            count += 1
        count = max(1, count-1)
        if count < len(remaining):
            space = remaining.rfind(' ', 0, count+1)
            if space > count//2:
                count = space
        part, remaining = remaining[:count].rstrip(), remaining[count:].lstrip()
        if len(output) == lines-1 and remaining:
            while part and stringWidth(part+'...', 'Helvetica', height)*1.12 > 278:
                part = part[:-1]
            part += '...'
        output.append(part)
    return output or ['']


def layout(snapshot):
    name = wrapped(snapshot['name'], 22, 3)
    color = wrapped(snapshot.get('color'), 20, 1)[0]
    size = wrapped(snapshot.get('size'), 24, 1)[0]
    return [(16, 12, 30, 'ELEVEN'), *[(16, 54 + i * 25, 22, line) for i, line in enumerate(name)],
            (16, 143, 24, size), (16, 174, 20, color), (16, 208, 22, snapshot['code'])]


def _compact_text(value, max_width, heights=(16, 14, 12)):
    """Fit the ZebraDesigner single-line fields without changing product data."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    label = clean(value).upper() or '-'
    for height in heights:
        if stringWidth(label, 'Helvetica', height) * 1.12 <= max_width:
            return label, height
    clipped = label
    while clipped and stringWidth(clipped + '...', 'Helvetica', heights[-1]) * 1.12 > max_width:
        clipped = clipped[:-1]
    return clipped.rstrip() + '...', heights[-1]


def _price_parts(snapshot):
    amount = Decimal(str(snapshot.get('sale_price') or '0'))
    if amount <= 0:
        return '', '-'
    symbol = {'USD': 'U$', 'BRL': 'R$', 'PYG': 'G$', 'EUR': '€'}.get(
        str(snapshot.get('sale_currency') or 'USD').upper(),
        str(snapshot.get('sale_currency') or 'USD').upper(),
    )
    digits = f'{amount:,.2f}'.replace(',', '#').replace('.', ',').replace('#', '.')
    if digits.endswith(',00'):
        digits = digits[:-3]
    return symbol, digits


def layout_v2(snapshot):
    """ZebraDesigner PADRAO: 60 × 30 mm at 203 dpi, with live ERP fields."""
    name, name_height = _compact_text(snapshot.get('name'), 292)
    size, size_height = _compact_text(snapshot.get('size'), 292)
    color, color_height = _compact_text(snapshot.get('color'), 292)
    symbol, amount = _price_parts(snapshot)
    # Coordinates follow the supplied design. Font widths approximate Arial/Bahnschrift
    # using the ZD220 resident font; the browser preview uses the same positions.
    fields = [
        (159, 6, 36, 26, 'ELEVEN'),
        (28, 60, name_height, round(name_height * .8), name),
        (28, 79, size_height, round(size_height * .8), size),
        (28, 105, color_height, round(color_height * .8), color),
        (28, 126, 16, 13, snapshot['code']),
    ]
    if symbol:
        fields.append((28, 192, 22, 17, symbol))
    fields.append((28 + (34 if len(symbol) > 1 else 15 if symbol else 0), 188, 27, 19, amount))
    barcode = clean(snapshot.get('barcode'))
    if barcode:
        barcode, barcode_height = _compact_text(barcode, 145, (14, 12, 10))
        fields.append((324, 202, barcode_height, 10, barcode))
    return fields


def render_zpl(snapshot):
    code, copies = snapshot['code'], snapshot['copies']
    if not CODE.fullmatch(code) or type(copies) is not int or not 1 <= copies <= MAX_COPIES:
        raise ValueError('Invalid label snapshot')
    if snapshot.get('layout_version') == 3:
        from .product_label_artwork import zpl
        return zpl(snapshot, _price_parts(snapshot))
    if snapshot.get('layout_version') == 2:
        parts = ['^XA^CI28^MNY^MMT^PW480^LL240^LH0,0^LS0^LT0^PON']
        for x, y, height, width, value in layout_v2(snapshot):
            encoded = ''.join(f'_{byte:02X}' for byte in value.encode('utf-8'))
            parts.append(f'^FO{x},{y}^A0N,{height},{width}^FH_^FD{encoded}^FS')
        parts.append(f'^FO343,57^BQN,2,5^FDMA,{code}^FS')
        parts.append(f'^PQ{copies},0,1,N^XZ')
        return '\n'.join(parts).encode('ascii')
    # Every text byte is ^FH-escaped, including ^, ~, underscores and UTF-8.
    # No product field can inject ZPL or change a printer setting.
    parts = ['^XA^CI28^MNY^MMT^PW480^LL240^LH0,0^LS0^LT0^PON']
    for x, y, height, text in layout(snapshot):
        encoded = ''.join(f'_{byte:02X}' for byte in text.encode('utf-8'))
        parts.append(f'^FO{x},{y}^A0N,{height},{height}^FH_^FD{encoded}^FS')
    # Version 1 QR: 21 modules × 5 dots. Reserve 4 modules of whitespace on all sides.
    parts.append(f'^FO340,65^BQN,2,5^FDMA,{code}^FS')
    parts.append(f'^PQ{copies},0,1,N^XZ')
    return '\n'.join(parts).encode('ascii')


def preview_png(item):
    from .product_label_artwork import preview_png as artwork_preview_png
    snap = snapshot(item, 1)
    return artwork_preview_png(snap, _price_parts(snap))


def snapshot(item, copies):
    if not CODE.fullmatch(item.inventory_code or ''):
        raise HTTPException(409, f'O produto {item.name} ainda não possui código interno válido. Atualize o cadastro.')
    return dict(item_id=str(item.id), name=item.name, code=item.inventory_code,
                size=item.size, color=item.color, barcode=item.barcode,
                sale_price=str(Decimal(item.sale_price or 0).quantize(Decimal('0.01'))),
                sale_currency=(item.sale_currency or 'USD').upper(),
                layout_version=3, copies=copies, width=60, height=30)


def job_view(job):
    snap = job.snapshot or {}
    return dict(id=str(job.id), status=job.status, name=snap.get('name'), code=snap.get('code'),
                size=snap.get('size'), color=snap.get('color'), copies=snap.get('copies'),
                diagnostic_message=diagnostic_message(job), created_at=job.created_at)


def batch_view(db, root):
    jobs = db.query(PrintJob).filter(PrintJob.source == PURPOSE,
        or_(PrintJob.id == root.id, PrintJob.parent_id == root.id)).order_by(PrintJob.created_at, PrintJob.id).all()
    # Request order is preserved explicitly, regardless of UUID/order timing.
    jobs.sort(key=lambda j: (j.snapshot or {}).get('position', 0))
    return dict(id=str(root.id), request_key=str(root.request_key), total=sum(j.snapshot['copies'] for j in jobs),
                jobs=[job_view(job) for job in jobs])


def enqueue(db, user, body):
    if not body.confirm:
        raise HTTPException(422, 'Confira os produtos e confirme a impressão das etiquetas.')
    if len({row.item_id for row in body.items}) != len(body.items):
        raise HTTPException(422, 'Há produtos repetidos na seleção. Ajuste a quantidade na mesma linha.')
    if sum(row.copies for row in body.items) > MAX_LABELS:
        raise HTTPException(422, f'Envie até {MAX_LABELS} etiquetas por confirmação.')
    fingerprint = hashlib.sha256(json.dumps([row.model_dump(mode='json') for row in body.items],
                                          sort_keys=True).encode()).hexdigest()
    device = destination(db, lock=True)
    if not device:
        raise HTTPException(409, 'Configure primeiro a Zebra em Etiquetas de produtos.')
    previous = db.query(PrintJob).filter_by(request_key=body.request_key).first()
    if previous:
        if (previous.source != PURPOSE or previous.user_id != user.id or
                (previous.snapshot or {}).get('fingerprint') != fingerprint):
            raise HTTPException(409, 'Esta confirmação já foi usada com outros produtos ou quantidades.')
        return batch_view(db, previous)
    ids = [row.item_id for row in body.items]
    # Consistent lock order protects the snapshot against edits/deletion during confirmation.
    products = {item.id: item for item in items_query(db).filter(Item.id.in_(ids)).order_by(Item.id).with_for_update().all()}
    if len(products) != len(ids):
        raise HTTPException(409, 'Um produto foi excluído ou desativado. Atualize a seleção.')
    batch_id = uuid.uuid4()
    start = utcnow()
    for position, row in enumerate(body.items):
        snap = snapshot(products[row.item_id], row.copies)
        if (row.code != snap['code'] or row.name != snap['name'] or row.color != snap['color'] or
                row.size != snap['size'] or
                (row.sale_price is not None and row.sale_price != Decimal(snap['sale_price'])) or
                (row.sale_currency is not None and row.sale_currency.upper() != snap['sale_currency'])):
            raise HTTPException(409, 'Um produto mudou durante a conferência. Atualize a seleção antes de imprimir.')
        snap.update(position=position, fingerprint=fingerprint if position == 0 else None)
        payload = render_zpl(snap)
        job = PrintJob(id=batch_id if position == 0 else uuid.uuid4(),
            device_id=device.id, user_id=user.id, source=PURPOSE,
            request_key=body.request_key if position == 0 else uuid.uuid5(body.request_key, str(row.item_id)),
            parent_id=batch_id if position else None, snapshot=snap, pdf=b'',
            sha256=hashlib.sha256(payload).hexdigest(), status='pending',
            created_at=start + timedelta(microseconds=position), expires_at=start + timedelta(days=30))
        db.add(job)
        if position == 0:
            root = job
            db.flush()  # parent FK, also ensures transaction rolls back as one batch
    db.commit()
    return batch_view(db, root)
