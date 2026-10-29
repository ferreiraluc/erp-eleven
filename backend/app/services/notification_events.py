"""Forward-only operational events, committed with their business transaction.

Application sessions opt in explicitly. Capturing during flush and publishing
before the outer commit covers API, provider refreshes and agents without turning
historical reads or maintenance sessions into notification broadcasts.
"""
import uuid
import hashlib
import json
from urllib.parse import urlencode

from sqlalchemy import event, inspect, func
from sqlalchemy.orm import Session

from ..models.usuario import Usuario, UsuarioRole
from ..models.pdv import PdvSale, PdvSaleItem
from ..models.rastreamento import Rastreamento
from ..models.printing import PrintJob
from .pdv_ticket_identity import ticket_code

PENDING_KEY = 'notification_business_events'
RUNNING_KEY = 'notification_events_running'


def _value(value):
    return getattr(value, 'value', value)


@event.listens_for(Session, 'before_flush')
def capture_business_events(db, flush_context, instances):
    if not db.info.get('notification_events') or db.info.get(RUNNING_KEY):
        return
    pending = db.info.setdefault(PENDING_KEY, {})
    for row in list(db.new):
        if isinstance(row, PdvSale) and row.status == 'completed':
            pending.setdefault(('sale', id(row)), {'row': row})
    for row in list(db.dirty):
        state = inspect(row)
        if isinstance(row, Rastreamento):
            history = state.attrs.status.history
            events = state.attrs.historico_eventos.history
            old_events = events.deleted[0] if events.deleted else []
            latest = lambda values: values[0] if isinstance(values, list) and values else None
            event_changed = events.has_changes() and latest(old_events) != latest(row.historico_eventos)
            if (history.has_changes() and history.deleted) or (event_changed and old_events):
                pending.setdefault(('tracking', id(row)), {'row': row,
                    'before': _value(history.deleted[0]) if history.deleted else _value(row.status),
                    'event_changed': bool(event_changed)})
        elif isinstance(row, PrintJob) and row.source == 'pdv_receipt':
            history = state.attrs.status.history
            if history.has_changes() and row.status in {'failed', 'uncertain'}:
                pending.setdefault(('receipt', id(row)), {'row': row})


def _owners(db):
    return [identity for (identity,) in db.query(Usuario.id).filter(
        func.lower(Usuario.email) == 'lucas@eleven.com', Usuario.role == UsuarioRole.ADMIN,
        Usuario.ativo.is_(True)).all()]


def _sale_event(db, sale, owners, emit):
    if sale.deleted_at or sale.status != 'completed':
        return
    seller = db.get(Usuario, sale.vendedor_id) if sale.vendedor_id else None
    context = {'sale_code': ticket_code(sale.id), 'user_name': seller.nome if seller else 'Equipe Eleven'}
    path = '/vendas-pdv?' + urlencode({'sale_id': str(sale.id)})
    emit(db, 'sale_completed', context=context, user_ids=owners, action_path=path,
         dedupe_key=f'sale-completed:{sale.id}', entity_type='pdv_sale', entity_id=str(sale.id))
    has_unlinked = db.query(PdvSaleItem.id).filter(
        PdvSaleItem.sale_id == sale.id, PdvSaleItem.is_avulso.is_(True)).first() is not None
    if has_unlinked and not (sale.notas or '').strip():
        # Avulso is valid: ask for context, never fabricate stock loss or fraud.
        targets = [*owners, *([sale.vendedor_id] if sale.vendedor_id else [])]
        emit(db, 'sale_avulso_without_reason', context=context, user_ids=targets, action_path=path,
             dedupe_key=f'sale-avulso:{sale.id}', entity_type='pdv_sale', entity_id=str(sale.id))


def _tracking_event(db, row, before, owners, emit, event_changed=False):
    status = _value(row.status)
    if not row.ativo or (before == status and not event_changed):
        return
    from .notification_context import TRACKING_LABELS, tracking_recipient_name
    latest = row.historico_eventos[0] if row.historico_eventos else None
    stamp = hashlib.sha256(json.dumps([status, latest], sort_keys=True, default=str).encode()).hexdigest()[:24]
    label = latest.get('situacao') if before == status and isinstance(latest, dict) else None
    emit(db, 'tracking_status_changed', context={'tracking_code': row.codigo_rastreio, 'status': label or TRACKING_LABELS.get(status, status),
         'cliente_username': tracking_recipient_name(db, row)},
         user_ids=[*owners, *([row.created_by] if row.created_by else [])],
         action_path='/rastreamento?' + urlencode({'search': row.codigo_rastreio}),
         dedupe_key=f'tracking:{row.id}:{status}:{stamp}', entity_type='tracking', entity_id=str(row.id))


def _receipt_event(db, row, owners, emit):
    if row.status not in {'failed', 'uncertain'}:
        return
    try:
        sale_id = uuid.UUID((row.snapshot or {}).get('sale_id', ''))
    except (ValueError, TypeError, AttributeError):
        return
    sale = db.get(PdvSale, sale_id)
    if not sale or sale.deleted_at:
        return
    emit(db, 'sale_receipt_problem', context={'sale_code': ticket_code(sale_id),
         'status': 'Envio incerto' if row.status == 'uncertain' else 'Falha de envio'},
         user_ids=[*owners, *([sale.vendedor_id] if sale.vendedor_id else [])],
         action_path='/vendas-pdv?' + urlencode({'sale_id': str(sale_id)}),
         dedupe_key=f'receipt-problem:{row.id}:{row.status}', entity_type='pdv_sale', entity_id=str(sale_id))


@event.listens_for(Session, 'before_commit')
def publish_business_events(db):
    # Core idempotency uses savepoints, whose before_commit must not recurse.
    if not db.info.get('notification_events') or db.info.get(RUNNING_KEY) or db.in_nested_transaction():
        return
    db.flush()
    pending = db.info.pop(PENDING_KEY, {})
    if not pending:
        return
    db.info[RUNNING_KEY] = True
    try:
        from .notifications import emit_event
        owners = _owners(db)
        for (kind, _), entry in pending.items():
            row = entry['row']
            if row not in db or not inspect(row).persistent or row in db.deleted or inspect(row).deleted:
                continue
            if kind == 'sale':
                _sale_event(db, row, owners, emit_event)
            elif kind == 'tracking':
                _tracking_event(db, row, entry['before'], owners, emit_event, entry.get('event_changed', False))
            elif kind == 'receipt':
                _receipt_event(db, row, owners, emit_event)
        db.flush()
    finally:
        db.info.pop(RUNNING_KEY, None)


@event.listens_for(Session, 'after_transaction_end')
def clear_business_events(db, transaction):
    if transaction.parent is None:
        db.info.pop(PENDING_KEY, None)
        db.info.pop(RUNNING_KEY, None)
