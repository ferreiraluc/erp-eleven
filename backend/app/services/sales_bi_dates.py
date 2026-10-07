"""Resolve worksheet weekdays using Eleven's monthly, Monday-to-Sunday weeks.

This is a read-only projection: original dates, labels and snapshots stay intact.
semana1 contains the first day of the workbook month; the live tab follows the
last closed numbered tab. Explicit dates take precedence over that convention.
"""
from calendar import monthrange
from datetime import date, timedelta
import re

from .sales_bi_parser import normal

WEEKDAYS = dict(zip(('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'), range(7)))
LIVE_SHEETS = {'planilha1', 'plhanilha1', 'vendas'}


def monday(value):
    return value - timedelta(days=value.weekday())


def sheet_number(name):
    match = re.fullmatch(r'semana\s*(\d+)', normal(name))
    return int(match[1]) if match else None


def source_period(source):
    try:
        first = date(source.year, source.month, 1)
        last = date(source.year, source.month, monthrange(source.year, source.month)[1])
        return monday(first).isoformat(), (monday(last) + timedelta(days=6)).isoformat()
    except (TypeError, ValueError):
        return None, None


def overlaps(start, end, lower=None, upper=None):
    return bool(start and end and (not lower or end >= lower) and (not upper or start <= upper))


def sheet_calendar(source):
    if 'entry_calendar' in source.snapshot:
        return {name: date.fromisoformat(value) if value else None
                for name, value in source.snapshot['entry_calendar'].items()}
    rows = (source.snapshot.get('entries') or {}).get('rows', [])
    weeks = source.snapshot.get('weeks', [])
    names = {r.get('sheet') for r in rows} | {w.get('sheet') for w in weeks if w.get('sheet')}
    closed = [sheet_number(name) for name in names if sheet_number(name)]
    start, end = source_period(source)
    calendar = {}
    for name in names:
        # A real date is stronger evidence than a numbered tab. Multiple dated
        # weeks in one tab make undated rows ambiguous, so do not infer them.
        anchors = {monday(date.fromisoformat(r['date'])) for r in rows
                   if r.get('sheet') == name and r.get('date')}
        if anchors:
            calendar[name] = next(iter(anchors)) if len(anchors) == 1 else None
            continue
        index = sheet_number(name)
        if normal(name) in LIVE_SHEETS:
            index = max(closed, default=0) + 1
        if not start or not index or not 1 <= index <= 6:
            calendar[name] = None
            continue
        candidate = date.fromisoformat(start) + timedelta(weeks=index - 1)
        calendar[name] = candidate if candidate.isoformat() <= end else None
    return calendar


def resolve_date(entry, calendar):
    recorded = entry.get('date')
    anchor = monday(date.fromisoformat(recorded)) if recorded else calendar.get(entry.get('sheet'))
    fields = {'date': recorded, 'date_source': 'recorded' if recorded else 'unresolved',
              'period_start': recorded, 'period_end': recorded,
              'week_start': anchor.isoformat() if anchor else None,
              'week_end': (anchor + timedelta(days=6)).isoformat() if anchor else None}
    if recorded or not anchor:
        return fields
    group = entry.get('day_group')
    if group in WEEKDAYS:
        resolved = (anchor + timedelta(days=WEEKDAYS[group])).isoformat()
        fields.update(date=resolved, date_source='week_day', period_start=resolved, period_end=resolved)
    elif group == 'weekend':
        fields.update(date_source='week_period', period_start=(anchor + timedelta(days=5)).isoformat(),
                      period_end=(anchor + timedelta(days=6)).isoformat())
    elif not group:
        fields.update(date_source='week_period', period_start=fields['week_start'], period_end=fields['week_end'])
    return fields
