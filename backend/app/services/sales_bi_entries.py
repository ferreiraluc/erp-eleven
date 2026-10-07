"""Read-only, seller-scoped exploration of individual Excel observations."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256

from .sales_bi import choose_workbooks, money, total, value
from .sales_bi_parser import normal
from .sales_bi_dates import overlaps, resolve_date, sheet_calendar, source_period


PAYMENT_LABELS = {'maquina': 'Máquina', 'credito': 'Crédito', 'debito': 'Débito',
                  'thais': 'Thais', 'dinheiro': 'Dinheiro', 'pix': 'Pix'}
PAYMENT_ALIASES = {'cartao de credito': 'credito', 'cartao credito': 'credito',
                   'cartao de debito': 'debito', 'cartao debito': 'debito', 'maq': 'maquina'}


def payment_key(value):
    """Blank payment cells mean cash by the store's spreadsheet convention."""
    key = ' '.join(normal(value).split())
    return PAYMENT_ALIASES.get(key, key) if key else 'dinheiro'


def _currencies(entries):
    output = []
    for currency in sorted({r['currency'] for r in entries}):
        rows = [r for r in entries if r['currency'] == currency]
        output.append({'currency': currency, 'count': len(rows), 'gross': total(r['gross'] for r in rows),
                       'net': total(r['net'] for r in rows),
                       'net_available': sum(r['net'] is not None for r in rows)})
    return output


def build_entries(rows, *, year=None, month=None, seller=None, currency=None, day=None,
                  date_from=None, date_to=None, payment_method=None,
                  search=None, offset=0, limit=50, private=False):
    """The endpoint must enforce the authenticated seller before calling this.

    All aggregates use the very same filtered observations as the table. Neither
    equal amounts nor equal customer names establish a duplicate sale.
    """
    available = choose_workbooks(rows)
    # A weekly tab can cross a month/year boundary. An explicit sale date is
    # searched in every selected snapshot; workbook periods still own closing
    # totals and monthly reconciliation, never the day's observed amounts.
    selected = [r for r in available if (not year or r.year == year) and (not month or r.month == month)]
    date_filter = bool(day or date_from or date_to)
    observation_sources = available if date_filter else selected
    entries = []
    missing_sources = 0
    skipped = 0
    issues = []
    lower, upper = day or date_from, day or date_to
    relevant_sources = set()
    for source in observation_sources:
        period = source_period(source)
        relevant = not date_filter or overlaps(*period, lower, upper)
        if relevant:
            relevant_sources.add(source.id)
        details = source.snapshot.get('entries')
        if not details:
            missing_sources += int(relevant)
            continue
        calendar = sheet_calendar(source)
        source_entries = []
        for item in details.get('rows', []):
            if seller and item.get('seller') != seller:
                continue
            # An allowlist prevents future snapshot fields leaking formulas,
            # arbitrary notes or internal source URLs through this endpoint.
            fields = ('sheet', 'row', 'source_cell', 'week_index', 'week_label', 'seller',
                      'currency', 'gross', 'net', 'payment_method', 'customer', 'date', 'time', 'day_group')
            entry = {k: item.get(k) for k in fields}
            entry.update(resolve_date(entry, calendar))
            entry['payment_type'] = payment_key(entry['payment_method'])
            entry.update(id=sha256(f"{source.id}:{item['sheet']}:{item['row']}".encode()).hexdigest()[:32],
                         source_id=source.id, filename=source.filename, year=source.year, month=source.month,
                         synced_at=source.synced_at, stale=bool(source.error))
            entries.append(entry)
            source_entries.append(entry)
        # A dated row can belong to a workbook of another month. Include its
        # diagnostics when it actually overlaps, but not unrelated 2021 files.
        relevant = relevant or any(overlaps(r['period_start'], r['period_end'], lower, upper) for r in source_entries)
        if relevant:
            relevant_sources.add(source.id)
        if relevant and not private:
            for diagnostic in details.get('diagnostics', []):
                count = diagnostic.get('skipped_rows', 0)
                skipped += count
                if count:
                    issues.append({'filename': source.filename, 'sheet': diagnostic['sheet'], 'skipped_rows': count})
    available_dates = sorted({r['date'] for r in entries if r['date']}, reverse=True)
    available_sellers = sorted({r['seller'] for r in entries})
    available_currencies = sorted({r['currency'] for r in entries})
    methods = {}
    for entry in entries:
        key = entry['payment_type']
        methods.setdefault(key, PAYMENT_LABELS.get(key) or entry['payment_method'])
    matching = [r for r in entries if (not currency or r['currency'] == currency)
                and (not payment_method or r['payment_type'] == payment_key(payment_method))
                and (not search or normal(search) in normal(' '.join(str(r[k] or '') for k in ('customer', 'seller', 'payment_method', 'payment_type', 'source_cell'))))]
    undated_excluded = sum(not r['period_start'] and r['source_id'] in relevant_sources for r in matching) if date_filter else 0
    def in_range(row):
        return bool(row['period_start'] and (not lower or row['period_start'] >= lower)
                    and (not upper or row['period_end'] <= upper))
    period_excluded = sum(not r['date'] and overlaps(r['period_start'], r['period_end'], lower, upper)
                          and not in_range(r) for r in matching) if date_filter else 0
    scope = [r for r in matching if not date_filter or in_range(r)]
    scope.sort(key=lambda r: (r['date'] or f"{r['year']:04d}-{r['month']:02d}-00", r['time'] or '',
                              r['year'], r['month'], r['week_index'] or 0, r['sheet'], r['row']), reverse=True)
    dated = [r for r in scope if r['date']]
    timed = [r for r in dated if r['time']]
    daily = defaultdict(list)
    hourly = defaultdict(list)
    weekdays = defaultdict(list)
    payments = defaultdict(list)
    for entry in scope:
        payments[entry['payment_type']].append(entry)
    for entry in dated:
        daily[entry['date']].append(entry)
    # Hour-of-day across the selected dates; exact dates are included in table
    # and a day filter makes this a single-day intraday view.
    for entry in timed:
        hourly[int(entry['time'].split(':', 1)[0])].append(entry)
    for entry in scope:
        if entry.get('day_group'):
            weekdays[entry['day_group']].append(entry)
    reconciliation = []
    for source in selected:
        source_rows = [r for r in entries if r['source_id'] == source.id]
        names = [seller] if seller else list(source.snapshot.get('sellers', {}))
        for code in sorted({r['currency'] for r in source_rows}):
            observed = [r for r in source_rows if r['currency'] == code]
            parts = [source.snapshot.get('sellers', {}).get(name, {}).get('currencies', {}).get(code) for name in names]
            published = sum((Decimal(p) for p in parts), Decimal(0)) if parts and all(p is not None for p in parts) else None
            net_complete = all(r['net'] is not None for r in observed)
            net = sum((Decimal(r['net']) for r in observed), Decimal(0)) if net_complete else None
            reconciliation.append({'year': source.year, 'month': source.month, 'currency': code,
                                   'published': money(published), 'observed_net': money(net),
                                   'difference': money(net - published) if net is not None and published is not None else None})
    page = [{**r, 'gross': money(r['gross']), 'net': money(r['net'])} for r in scope[offset:offset + limit]]
    selected_ids = {r.id for r in selected}
    week_starts = sorted({r['week_start'] for r in entries if r['source_id'] in selected_ids and r['week_start']}, reverse=True)
    return {
        'items': page, 'total': len(scope), 'offset': offset, 'limit': limit,
        'sellers': available_sellers, 'currencies': available_currencies, 'dates': available_dates,
        'payment_methods': [{'value': key, 'label': methods[key]} for key in sorted(methods)],
        'weeks': [{'start': start, 'end': (date.fromisoformat(start) + timedelta(days=6)).isoformat(),
                   'settlement_date': (date.fromisoformat(start) + timedelta(days=7)).isoformat()} for start in week_starts],
        'payments': [{'payment_type': key, 'label': methods[key], 'count': len(group), 'currencies': _currencies(group)}
                     for key, group in sorted(payments.items())],
        'summary': {'count': len(scope), 'currencies': _currencies(scope), 'dated_count': len(dated),
                    'timed_count': len(timed), 'undated_count': len(scope) - len(dated),
                    'official_total_usd': total(value(r.snapshot, seller) for r in selected)},
        'daily': [{'date': key, 'count': len(group), 'currencies': _currencies(group)} for key, group in sorted(daily.items())],
        'hourly': [{'hour': key, 'count': len(group), 'currencies': _currencies(group)} for key, group in sorted(hourly.items())],
        'weekdays': [{'day': key, 'count': len(weekdays[key]), 'currencies': _currencies(weekdays[key])}
                     for key in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun', 'weekend') if key in weekdays],
        'reconciliation': reconciliation,
        'coverage': {'source_count': len(observation_sources), 'needs_sync': missing_sources > 0,
                     'sources_without_entries': missing_sources, 'skipped_rows': skipped if not private else None,
                     'undated_excluded': undated_excluded, 'period_excluded': period_excluded,
                     'inferred_dates': sum(r['date_source'] == 'week_day' for r in scope),
                     'period_included': sum(r['date_source'] == 'week_period' for r in scope),
                     'issues': issues},
    }
