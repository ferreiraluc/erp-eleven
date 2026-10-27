"""Read-only, bounded projections. No images, receipts, provider or AI requests."""
from collections import defaultdict
from datetime import timedelta
import time
from sqlalchemy import func, or_, text

from ..models.inventory import Item
from ..models.pdv import PdvSale, PdvSaleItem
from ..models.printing import PrintDevice, PrintJob
from ..models.sales_bi import SalesBIConfig
from ..models.cliente import Cliente
from ..models.address_book import SavedAddress
from ..models.notification import Notification, NotificationRecipient
from .address_identity import equivalent
from .customer_identity import full_name, name_key, phone_key
from .user_sessions import aware

MAX_FINDINGS = 100
LIMITS = {'inventory': 500, 'sales': 100, 'prints': 100, 'printers': 30, 'customers': 100, 'addresses': 100}
CHECKERS = ('inventory', 'sales', 'prints', 'printers', 'bi', 'workers', 'customers', 'addresses')


def _finding(output, key, entity, identity=None, severity='warning', related=None):
    output['counters'][key] = output['counters'].get(key, 0) + 1
    if len(output['findings']) < MAX_FINDINGS:
        entry = {'key': key, 'entity_type': entity, 'severity': severity}
        if identity is not None:
            entry['entity_id'] = str(identity)
        if related is not None:
            entry['related_id'] = str(related)
        output['findings'].append(entry)


def _rows(db, query, key, output):
    limit = LIMITS[key]
    rows = query.limit(limit + 1).all()
    output['coverage'][key] = {'checked': min(limit, len(rows)), 'complete': len(rows) <= limit, 'window': 'last_24_hours'}
    return rows[:limit]


def _inventory(db, moment, output, health):
    since = moment - timedelta(days=1)
    rows = _rows(db, db.query(Item.id, Item.brand, Item.category, Item.size, Item.color,
        Item.sale_price, Item.current_stock, Item.stock_loja, Item.stock_deposito, Item.min_stock, Item.max_stock)
        .filter(Item.deleted_at.is_(None), Item.is_active.is_(True), Item.updated_at >= since, Item.updated_at <= moment)
        .order_by(Item.updated_at, Item.id), 'inventory', output)
    for row in rows:
        if not (row.brand or '').strip() or not (row.category or '').strip() or not (row.sale_price or 0):
            _finding(output, 'inventory_missing_metadata', 'inventory', row.id, 'info')
        if row.current_stock != (row.stock_loja or 0) + (row.stock_deposito or 0):
            _finding(output, 'inventory_balance', 'inventory', row.id)
        if row.max_stock and (row.min_stock or 0) > row.max_stock:
            _finding(output, 'inventory_limits', 'inventory', row.id)


def _sales(db, moment, output, health):
    missing_reason = func.trim(func.coalesce(PdvSale.notas, '')) == ''
    has_unlinked = db.query(PdvSaleItem.id).filter(PdvSaleItem.sale_id == PdvSale.id,
        or_(PdvSaleItem.is_avulso.is_(True), PdvSaleItem.item_id.is_(None))).exists()
    rows = _rows(db, db.query(PdvSale.id, missing_reason.label('missing_reason'), has_unlinked.label('has_unlinked')).filter(
        PdvSale.created_at >= moment - timedelta(days=1), PdvSale.created_at <= moment,
        PdvSale.deleted_at.is_(None), PdvSale.status == 'completed')
        .order_by(PdvSale.created_at, PdvSale.id), 'sales', output)
    pending = {'sale-avulso:' + str(row.id) for row in rows if row.missing_reason and row.has_unlinked}
    # A response supplied through the notification is valid context without
    # rewriting the financial sale. Probe only the bounded candidate keys using
    # the unique dedupe index; never load private message or response text.
    resolved = {key for (key,) in db.query(Notification.dedupe_key).join(
        NotificationRecipient, NotificationRecipient.notification_id == Notification.id).filter(
        Notification.dedupe_key.in_(pending), Notification.cancelled_at.is_(None),
        NotificationRecipient.removed_at.is_(None), NotificationRecipient.acknowledged_at.is_not(None),
        func.trim(func.coalesce(NotificationRecipient.acknowledgement_note, '')) != '').all()} if pending else set()
    for row in rows:
        if row.missing_reason and row.has_unlinked and 'sale-avulso:' + str(row.id) not in resolved:
            _finding(output, 'sale_avulso_without_reason', 'pdv_sale', row.id)


def _prints(db, moment, output, health):
    rows = _rows(db, db.query(PrintJob.id, PrintJob.status, PrintJob.created_at, PrintJob.claimed_at).filter(
        PrintJob.created_at >= moment - timedelta(days=7), PrintJob.created_at <= moment,
        PrintJob.status.in_(('uncertain', 'failed', 'pending', 'claimed')))
        .order_by(PrintJob.status, PrintJob.created_at, PrintJob.id), 'prints', output)
    for row in rows:
        if row.status in ('uncertain', 'failed') and aware(row.created_at) >= moment - timedelta(days=1):
            _finding(output, 'print_' + row.status, 'print_job', row.id)
        elif row.status == 'pending' and aware(row.created_at) < moment - timedelta(minutes=10):
            _finding(output, 'print_stale', 'print_job', row.id)
        elif row.status == 'claimed' and aware(row.claimed_at or row.created_at) < moment - timedelta(minutes=5):
            _finding(output, 'print_stale', 'print_job', row.id)
    output['coverage']['prints']['window'] = 'active_jobs_last_7_days'


def _printers(db, moment, output, health):
    rows = _rows(db, db.query(PrintDevice.id, PrintDevice.last_seen_at).filter(PrintDevice.active.is_(True))
        .order_by(PrintDevice.id), 'printers', output)
    for row in rows:
        if row.last_seen_at and aware(row.last_seen_at) < moment - timedelta(minutes=15):
            _finding(output, 'printer_offline', 'print_device', row.id)
    output['coverage']['printers']['window'] = 'active_devices'


def _bi(db, moment, output, health):
    config = db.query(SalesBIConfig.enabled, SalesBIConfig.finished_at, SalesBIConfig.next_sync_at,
        SalesBIConfig.started_at, SalesBIConfig.lease_until, SalesBIConfig.last_error.is_not(None).label('has_error'))
    row = config.filter(SalesBIConfig.id == 1).one_or_none()
    output['coverage']['bi'] = {'checked': int(row is not None), 'complete': True, 'window': 'current_state'}
    if row and row.enabled and (row.has_error or not row.finished_at or aware(row.finished_at) < moment - timedelta(hours=30)
        or row.lease_until and aware(row.lease_until) < moment and row.started_at and (not row.finished_at or aware(row.started_at) > aware(row.finished_at))):
        _finding(output, 'bi_sync_problem', 'sales_bi')


def _workers(db, moment, output, health):
    allowed = {'assistant', 'freight_labels', 'sales_bi', 'notifications', 'tracking'}
    safe = {key: value for key, value in (health or {}).items() if key in allowed and value in ('online', 'offline', 'stalled', 'disabled')}
    output['coverage']['workers'] = {'checked': len(safe), 'complete': bool(safe), 'window': 'current_process'}
    for key, state in safe.items():
        if state in ('offline', 'stalled'):
            _finding(output, 'worker_problem', key)


def _customers(db, moment, output, health):
    # Exact stored phone/email identities are indexed. Do not call the maintenance
    # candidates()/find_customer() helpers that load thousands of complete rows.
    rows = _rows(db, db.query(Cliente.id, Cliente.nome, Cliente.telefone, Cliente.email)
        .filter(Cliente.merged_into_id.is_(None), Cliente.updated_at >= moment - timedelta(days=1), Cliente.updated_at <= moment)
        .order_by(Cliente.updated_at, Cliente.id), 'customers', output)
    # At most 20 indexed probes, with at most five references per probe.
    probes = 0
    found = set()
    for row in rows:
        if not full_name(row.nome):
            continue
        filters = []
        if row.telefone and phone_key(row.telefone): filters.append(Cliente.telefone == row.telefone)
        if row.email and '@' in row.email: filters.append(Cliente.email == row.email)
        if not filters:
            continue
        if probes >= 20:
            output['coverage']['customers']['complete'] = False
            break
        probes += 1
        matches = db.query(Cliente.id, Cliente.nome).filter(Cliente.merged_into_id.is_(None), Cliente.id != row.id,
                or_(*filters)).order_by(Cliente.id).limit(6).all()
        if len(matches) > 5:
            output['coverage']['customers']['complete'] = False
        for other in matches[:5]:
            pair = tuple(sorted((str(row.id), str(other.id))))
            if name_key(row.nome) == name_key(other.nome) and pair not in found:
                found.add(pair)
                _finding(output, 'customer_duplicate_candidate', 'customer', pair[0], 'info', pair[1])


def _addresses(db, moment, output, health):
    rows = _rows(db, db.query(SavedAddress.id, SavedAddress.data, SavedAddress.customer_link_review)
        .filter(SavedAddress.merged_into_id.is_(None), SavedAddress.updated_at >= moment - timedelta(days=1), SavedAddress.updated_at <= moment)
        .order_by(SavedAddress.updated_at, SavedAddress.id), 'addresses', output)
    groups = defaultdict(list)
    for row in rows:
        if row.customer_link_review:
            _finding(output, 'address_link_review', 'address', row.id, 'info')
        name = name_key(row.data.get('nome'))
        if not full_name(name):
            continue
        previous = groups[name]
        if len(previous) > 10:
            output['coverage']['addresses']['complete'] = False
        for other in previous[:10]:
            if equivalent(row.data, other.data):
                _finding(output, 'address_duplicate_candidate', 'address', row.id, 'info', other.id)
        previous.append(row)
    # This comparison intentionally covers only the changed cohort. A name alone
    # is never a duplicate finding; dedup_key already protects exact new addresses.
    output['coverage']['addresses']['comparison'] = 'changed_cohort_only'


FUNCTIONS = {'inventory': _inventory, 'sales': _sales, 'prints': _prints, 'printers': _printers,
             'bi': _bi, 'workers': _workers, 'customers': _customers, 'addresses': _addresses}


def collect(session_factory, moment, health=None):
    output = {'counters': {}, 'findings': [], 'coverage': {}}
    started = time.monotonic()
    for key in CHECKERS:
        if time.monotonic() - started > 15:
            output['coverage'][key] = {'checked': 0, 'complete': False, 'error': 'run_query_budget'}
            continue
        try:
            # One short read-only transaction per checker; a timeout does not
            # abort other checks or hold a pool connection during LLM calls.
            with session_factory() as db:
                if db.get_bind().dialect.name == 'postgresql':
                    db.execute(text('SET TRANSACTION READ ONLY'))
                    db.execute(text("SET LOCAL statement_timeout = '1000ms'"))
                    db.execute(text("SET LOCAL lock_timeout = '250ms'"))
                FUNCTIONS[key](db, moment, output, health)
                db.rollback()
        except Exception:
            output['coverage'][key] = {'checked': 0, 'complete': False, 'error': 'check_unavailable'}
    return output
