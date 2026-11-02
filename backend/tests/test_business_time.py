"""Brasília display + UTC storage, with explicit calendar and provider semantics."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.database import engine_options
from app.services.business_time import BUSINESS_TZ, business_datetime, stored_day_start, stored_instant
from app.services.pdv_receipt_layout import view


def dialect(name):
    return SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name=name)))


def test_storage_and_display_never_double_shift_an_aware_timestamp():
    naive = datetime(2026, 11, 2, 18, 15)
    aware = naive.replace(tzinfo=timezone.utc)
    assert stored_instant(naive, dialect('postgresql')) == aware
    assert stored_instant(aware, dialect('postgresql')) is aware
    assert business_datetime(naive).isoformat() == '2026-11-02T15:15:00-03:00'
    assert business_datetime('2026-11-02T15:15:00-03:00').isoformat() == '2026-11-02T15:15:00-03:00'
    assert business_datetime('2026-11-02 15:15:00', naive='business').isoformat() == '2026-11-02T15:15:00-03:00'
    # SQLite removes the offset from settings.now() instead of converting the instant.
    local = datetime(2026, 11, 2, 15, 15)
    assert stored_instant(local, dialect('sqlite')) == aware


def test_business_day_is_converted_to_legacy_storage_boundaries():
    assert stored_day_start(date(2026, 11, 2), dialect('postgresql')) == datetime(2026, 11, 2, 3)
    assert stored_day_start(date(2026, 11, 3), dialect('postgresql')) == datetime(2026, 11, 3, 3)
    assert stored_day_start(date(2026, 11, 2), dialect('sqlite')) == datetime(2026, 11, 2)
    assert '-c timezone=UTC' in engine_options('postgresql://localhost/isolated')['connect_args']['options']


@pytest.mark.parametrize('stamp', ['2026-11-02T18:15:00', '2026-11-02T18:15:00+00:00', '2026-11-02T15:15:00-03:00'])
def test_ticket_preview_and_pdf_share_brasilia_time_without_rewriting_snapshot(stamp):
    snapshot = {'sale_id':'00000000-0000-0000-0000-000000000001', 'date':stamp, 'items':[], 'payments':[],
                'subtotal':'0', 'discount':'0', 'total':'0', 'usd_rate_gs':'6000'}
    assert view(snapshot)['date'] == '02/11/2026 15:15'
    assert snapshot['date'] == stamp
