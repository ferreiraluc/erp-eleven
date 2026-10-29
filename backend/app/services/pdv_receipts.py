"""Immutable receipt snapshots and device-scoped delivery; no printer I/O here."""
import hashlib
import uuid
from datetime import timedelta

from fastapi import HTTPException
from ..models.assistant import utcnow
from ..models.printing import PrintDevice, PrintJob
from ..models.pdv import PdvSale
from .access_policy import sales_query
from .print_diagnostics import diagnostic_message


from .pdv_receipt_layout import render, view


def original_key(sale):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'eleven:pdv:receipt:{sale.id}:{sale.version}')


def printer_info(device):
    if not device:
        return None
    return dict(id=str(device.id), name=device.name, paper_width_mm=device.paper_width_mm,
                paper_height_mm=device.paper_height_mm, auto_receipts=device.auto_receipts,
                last_seen_at=device.last_seen_at, driver=device.driver)


def destination(db, *, lock=False):
    query = db.query(PrintDevice).filter_by(purpose='tickets', active=True, auto_receipts=True)
    if not lock:
        return query.first()
    # A cutover may change the old destination while this SELECT waits on its
    # lock. A fresh statement sees the committed replacement (READ COMMITTED).
    return query.with_for_update().first() or query.with_for_update().first()


def receipt_state(job):
    return dict(id=str(job.id), status=job.status, diagnostic_message=diagnostic_message(job)) if job else None


def latest_job(db, sale):
    original = db.query(PrintJob).filter_by(request_key=original_key(sale)).first()
    if not original:
        return None
    return db.query(PrintJob).filter((PrintJob.id == original.id) | (PrintJob.parent_id == original.id)).order_by(
        PrintJob.created_at.desc(), PrintJob.id.desc()).first()


def authorized_sale(db, sale_id, user):
    # Serialize with sale edits/returns so receipt totals and lines share one revision.
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
    snap = build_snapshot(sale, device, copy=copy_key is not None)
    job = PrintJob(device_id=device.id, user_id=user_id, request_key=copy_key or key,
                   source='pdv_receipt', parent_id=previous.id if previous else None,
                   snapshot=snap, pdf=b'', sha256='', expires_at=utcnow()+timedelta(hours=24))
    db.add(job)
    db.flush()
    return job


def build_snapshot(sale, device=None, *, copy=False):
    return dict(sale_id=str(sale.id), version=sale.version, date=sale.created_at.isoformat(),
                usd_rate_gs=str(sale.usd_rate_gs) if sale.usd_rate_gs else None,
                customer=sale.cliente_nome, seller=sale.vendedor.nome if sale.vendedor else None,
                width=device.paper_width_mm if device else 80, height=device.paper_height_mm if device else 0,
                status=sale.status, refunded=str(sale.refunded_gs or 0),
                subtotal=str(sale.subtotal_gs), discount=str(sale.desconto_gs), total=str(sale.total_gs),
                items=[dict(name=i.item_name, size=i.item_size, color=i.item_color,
                            quantity=str(i.quantity), unit=str(i.unit_price_gs),
                            discount=str(i.discount_gs), total=str(i.total_gs), returned=str(i.returned_quantity or 0)) for i in sale.items],
                payments=[dict(method=p.method, currency=p.currency, amount=str(p.amount_original),
                               total=str(p.amount_gs), card_fee=str(p.card_fee_gs or 0), card_fee_percent=str(p.card_fee_percent or 0)) for p in sale.payments], copy=copy)


def snapshot_for_view(db, sale):
    # Same immutable revision used by the printer, even after its temporary PDF is erased.
    original = db.query(PrintJob).filter_by(request_key=original_key(sale), source='pdv_receipt').first()
    device = destination(db) or db.query(PrintDevice).filter_by(purpose='tickets', active=True).order_by(PrintDevice.created_at).first()
    if original and original.snapshot:
        # Reflow the immutable financial data for today's media, without rewriting jobs.
        return dict(original.snapshot, usd_rate_gs=original.snapshot.get('usd_rate_gs') or (str(sale.usd_rate_gs) if sale.usd_rate_gs else None), width=device.paper_width_mm if device else 80,
                    height=device.paper_height_mm if device else 0)
    return build_snapshot(sale, device)


def prepare_document(job):
    if job.source == 'printer_test' and not job.pdf:
        from .receipt_printer_setup import test_document
        job.pdf = test_document(job.id)
        job.sha256 = hashlib.sha256(job.pdf).hexdigest()
    if job.source == 'pdv_receipt' and not job.pdf:
        job.pdf = render(job.snapshot)
        job.sha256 = hashlib.sha256(job.pdf).hexdigest()
