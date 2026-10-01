"""Extract individual saved rows from the known Eleven worksheet layout.

Rows are observations, not new ERP sales. Two equal rows remain two observations;
only the already identified complete copy of the live tab is excluded upstream.
"""
from datetime import date, datetime, time
from hashlib import sha256
import json
import re

from .sales_bi_parser import CURRENCIES, normal, number, packed, seller_name


DAY_LABELS = {
    'seg': 'mon', 'segunda': 'mon', 'segunda feira': 'mon',
    'ter': 'tue', 'terca': 'tue', 'terca feira': 'tue',
    'qua': 'wed', 'quarta': 'wed', 'quarta feira': 'wed',
    'qui': 'thu', 'quinta': 'thu', 'quinta feira': 'thu',
    'sex': 'fri', 'sexta': 'fri', 'sexta feira': 'fri',
    'sab': 'sat', 'sabado': 'sat', 'dom': 'sun', 'domingo': 'sun',
    'sab/dom': 'weekend', 'sabado/domingo': 'weekend',
}


def text(value, limit=120):
    if not isinstance(value, str) or value.startswith('='):
        return None
    return ' '.join(value.split())[:limit] or None


def observed_date(value, year, month=None):
    """Only an explicit date is a date; weekday/weekly labels never become one."""
    if isinstance(value, datetime):
        return value.date().isoformat(), value.time().isoformat() if value.time() != time(0) else None
    if isinstance(value, date):
        return value.isoformat(), None
    if not isinstance(value, str):
        return None, None
    value = value.strip()
    for pattern in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            found = datetime.strptime(value, pattern)
            return found.date().isoformat(), found.time().isoformat()
        except ValueError:
            pass
    for pattern in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, pattern).date().isoformat(), None
        except ValueError:
            pass
    if re.fullmatch(r'\d{1,2}/\d{1,2}', value):
        try:
            day, observed_month = map(int, value.split('/'))
            if month and observed_month != month:
                return None, None
            return date(year, observed_month, day).isoformat(), None
        except ValueError:
            pass
    return None, None


def observed_time(value):
    if isinstance(value, datetime):
        return value.time().isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, str) and re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?', value.strip()):
        try:
            return time.fromisoformat(value.strip().zfill(5)).isoformat()
        except ValueError:
            pass
    return None


def extract_entries(candidates, weeks, *, year, month=None):
    """The caller provides only selected/non-mirrored tabs, with saved cell values."""
    result = []
    diagnostics = []
    week_by_sheet = {w['sheet']: w for w in weeks if w.get('sheet')}
    for sheet, data in candidates:
        rows = data['rows']
        week = week_by_sheet.get(sheet)
        # Optional fields require an explicit header. Unlabelled notes are never
        # interpreted as client names, timestamps or identifiers.
        headers = {}
        for r in range(data['total_row'], min(data['total_row'] + 6, len(rows))):
            if normal(rows[r][1]) == 'moeda' and normal(rows[r][3]) == 'vendedor':
                headers = {normal(v): c for c, v in enumerate(rows[r][:12]) if normal(v)}
                break
        date_col = next((headers[k] for k in ('data', 'data venda', 'data e hora', 'data/hora') if k in headers), 0)
        time_col = next((headers[k] for k in ('hora', 'horario') if k in headers), None)
        client_col = next((headers[k] for k in ('cliente', 'nome do cliente', 'nome cliente') if k in headers), None)
        net_known = any(k in headers for k in ('valor liquido', 'liquido')) or any(
            normal(row[1]) in CURRENCIES and number(row[5]) is not None for row in rows[data['total_row'] + 1:])
        day_group, group_date = None, None
        skipped = 0
        for row_number, row in enumerate(rows[data['total_row'] + 1:], data['total_row'] + 2):
            raw_day = normal(row[0]).replace('-feira', ' feira').rstrip('.')
            currency = CURRENCIES.get(normal(row[1]))
            date_value, clock = observed_date(row[date_col], year, month)
            if date_value and isinstance(row[date_col], datetime) and any(k in headers for k in ('data e hora', 'data/hora')):
                clock = row[date_col].time().isoformat()
            # Standalone date/day separators apply to subsequent rows. A time
            # never carries over: each intraday observation needs its own time.
            if not currency:
                if raw_day in DAY_LABELS:
                    day_group, group_date = DAY_LABELS[raw_day], None
                elif date_value:
                    group_date, day_group = date_value, None
                elif text(row[0]):
                    group_date, day_group = None, None
                continue
            gross, net = number(row[2]), number(row[5])
            name = seller_name(row[3]) if text(row[3]) else None
            if gross is None or name is None:
                skipped += 1
                continue
            if time_col is not None:
                clock = observed_time(row[time_col]) or clock
            if raw_day in DAY_LABELS:
                day_group, group_date = DAY_LABELS[raw_day], None
            effective_date = date_value or group_date
            # A standalone time without a calendar date is retained as missing
            # date, never assigned to sync time or to a guessed day of the week.
            if net is None and not net_known:
                net = gross
            customer = text(row[client_col]) if client_col is not None else None
            entry = {
                'sheet': sheet, 'row': row_number, 'source_cell': f'{sheet}!C{row_number}',
                'week_index': week['index'] if week else None,
                'week_label': week['label'] if week else None,
                'seller': name, 'currency': currency, 'gross': packed(gross), 'net': packed(net),
                'payment_method': text(row[4], 80), 'customer': customer,
                'date': effective_date, 'time': clock if effective_date else None,
                'day_group': day_group if not effective_date else None,
            }
            # A content fingerprint supports provenance/review, not deduplication
            # of equal genuine transactions or inferred customer associations.
            entry['fingerprint'] = sha256(json.dumps(entry, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            result.append(entry)
        if skipped:
            diagnostics.append({'sheet': sheet, 'skipped_rows': skipped})
    return {'version': 1, 'rows': result, 'diagnostics': diagnostics}
