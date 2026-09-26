"""Aggregations use each monthly snapshot exactly once, preferring the archive."""
from decimal import Decimal
from ..models.sales_bi import SalesBIConfig, SalesBIWorkbook
from ..models.assistant import utcnow


def money(value):
    return float(Decimal(value).quantize(Decimal('0.01'))) if value is not None else None


def total(values):
    items = [Decimal(v) for v in values if v is not None]
    return float(sum(items).quantize(Decimal('0.01'))) if items else None


def choose_workbooks(rows):
    selected = {}
    for row in rows:
        if not row.active or not row.snapshot:
            continue
        key = (row.year, row.month)
        old = selected.get(key)
        if old is None or (row.kind == 'archive', row.remote_version or '', row.id) > (old.kind == 'archive', old.remote_version or '', old.id):
            selected[key] = row
    return sorted(selected.values(), key=lambda r: (r.year, r.month))


def value(snapshot, seller=None):
    return snapshot.get('sellers', {}).get(seller, {}).get('total_usd') if seller else snapshot['total_usd']


def build_overview(rows, year=None, month=None, seller=None):
    selected = choose_workbooks(rows)
    years = sorted({r.year for r in selected}, reverse=True)
    sellers = sorted({name for r in selected for name in r.snapshot['sellers']})
    latest = max(((r.year, r.month) for r in selected), default=(None, None))
    scope = [r for r in selected if (not year or r.year == year) and (not month or r.month == month)]
    def metric(items):
        vals = [value(r.snapshot, seller) for r in items]
        return {'total_usd': total(vals), 'available_months': sum(v is not None for v in vals), 'source_months': len(items),
                'partial': any(r.kind == 'current' for r in items)}
    monthly = [{'year': r.year, 'month': r.month, 'total_usd': money(value(r.snapshot, seller)), 'partial': r.kind == 'current',
                'source_id': r.id, 'filename': r.filename, 'source_cell': r.snapshot['sellers'].get(seller, {}).get('source_cell') if seller else r.snapshot['source_cell'],
                'synced_at': r.synced_at, 'stale': bool(r.error), 'warnings': r.snapshot['warnings']} for r in selected]
    ranking = []
    for name in sellers:
        vals = [value(r.snapshot, name) for r in scope]
        if not any(v is not None for v in vals):
            continue
        ranking.append({'name': name, 'total_usd': total(vals), 'available_months': sum(v is not None for v in vals), 'source_months': len(scope)})
    ranking.sort(key=lambda x: (-x['total_usd'], x['name']))
    weeks = []
    for r in scope:
        for w in r.snapshot['weeks']:
            v = w['sellers'].get(seller) if seller else w['total_usd']
            if v is not None:
                weeks.append({'year': r.year, 'month': r.month, 'index': w['index'], 'label': w['label'], 'total_usd': money(v),
                              'partial': r.kind == 'current', 'source_id': r.id})
    weeks.sort(key=lambda x: (-x['total_usd'], x['year'], x['month'], x['index']))
    currencies = []
    for currency in ('USD', 'BRL', 'PYG', 'EUR'):
        vals = []
        for r in scope:
            names = [seller] if seller else list(r.snapshot['sellers'])
            parts = [r.snapshot['sellers'].get(n, {}).get('currencies', {}).get(currency) for n in names]
            if parts and all(p is not None for p in parts):
                vals.append(str(sum((Decimal(p) for p in parts), Decimal(0))))
        currencies.append({'currency': currency, 'value': total(vals), 'available_months': len(vals), 'source_months': len(scope)})
    comparison_month = month or latest[1]
    comparison = [m for m in monthly if m['month'] == comparison_month]
    previous = None
    for m in comparison:
        m['difference_usd'] = money(Decimal(str(m['total_usd'])) - Decimal(str(previous['total_usd']))) if previous and previous['total_usd'] is not None and m['total_usd'] is not None else None
        m['difference_percent'] = round(m['difference_usd'] / previous['total_usd'] * 100, 2) if previous and previous['total_usd'] not in (None, 0) and m['difference_usd'] is not None else None
        m['previous_year'] = previous['year'] if previous else None
        previous = m
    annual = [{'year': y, **metric([r for r in selected if r.year == y])} for y in years]
    return {'years': years, 'sellers': sellers, 'latest': {'year': latest[0], 'month': latest[1]}, 'selected': metric(scope),
            'months': monthly, 'annual': annual, 'ranking': ranking, 'weeks': weeks, 'currencies': currencies,
            'comparison_month': comparison_month, 'comparison': comparison,
            'coverage': {'months': len(selected), 'files': len(rows), 'warnings': sum(bool(r.snapshot['warnings']) for r in scope)}}


def sources_status(db):
    c = db.get(SalesBIConfig, 1)
    rows = db.query(SalesBIWorkbook).filter_by(active=True).order_by(SalesBIWorkbook.year.desc(), SalesBIWorkbook.month.desc()).all()
    used = {r.id for r in choose_workbooks(rows)}
    # DateTime in SQLite tests may be naive. Compare instants consistently.
    running = bool(c and c.lease_until and c.lease_until.replace(tzinfo=None) > utcnow().replace(tzinfo=None))
    return {'configured': bool(c), 'enabled': c.enabled if c else False, 'running': running,
            'requested_at': c.requested_at if c else None, 'started_at': c.started_at if c else None,
            'finished_at': c.finished_at if c else None, 'next_sync_at': c.next_sync_at if c else None,
            'error': c.last_error if c else None,
            'sources': [{'id': r.id, 'filename': r.filename, 'kind': r.kind, 'year': r.year, 'month': r.month,
                         'synced_at': r.synced_at, 'checked_at': r.checked_at, 'error': r.error, 'selected': r.id in used,
                         'has_data': bool(r.snapshot), 'warnings': r.snapshot.get('warnings', []) if r.snapshot else []} for r in rows]}
