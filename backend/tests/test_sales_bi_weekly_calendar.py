"""Weekly settlements use synthetic saved rows; never modify the source XLSX."""
from copy import deepcopy

import pytest

from app.services.sales_bi import private_workbooks
from app.services.sales_bi_entries import build_entries
from test_sales_bi_entries import workbook, client


def entry(sheet, day, *, seller='Lucas', amount='100', recorded=None, row=12):
    return {'sheet': sheet, 'row': row, 'source_cell': f'{sheet}!C{row}',
            'week_index': None, 'week_label': None, 'seller': seller, 'currency': 'BRL',
            'gross': amount, 'net': amount, 'payment_method': 'Maq', 'customer': None,
            'date': recorded, 'time': None, 'day_group': day}


def weekly_book(key='weekly', *, year=2026, month=10, rows=None, kind='current'):
    source = workbook(key, kind)
    source.year, source.month = year, month
    source.snapshot['entries'] = {'rows': rows if rows is not None else [
        entry('semana1', 'thu'), entry('Planilha1', 'mon'),
        entry('Planilha1', 'tue', row=13), entry('Planilha1', 'wed', row=14),
        entry('Planilha1', 'weekend', row=15), entry('Planilha1', None, row=16)], 'diagnostics': []}
    source.snapshot['weeks'] = [{'index': 1, 'sheet': 'semana1', 'label': '01/10', 'sellers': {}}]
    return source


def test_october_live_tab_follows_closed_week_and_week_settlement_includes_periods():
    source = weekly_book()
    before = deepcopy(source.snapshot)
    result = build_entries([source], year=2026, month=10, date_from='2026-10-05', date_to='2026-10-11', payment_method='maquina')
    assert result['total'] == 5
    assert result['summary']['currencies'][0]['net'] == 500
    assert result['coverage']['inferred_dates'] == 3
    assert result['coverage']['period_included'] == 2
    assert result['coverage']['undated_excluded'] == result['coverage']['period_excluded'] == 0
    assert result['weeks'] == [
        {'start': '2026-10-05', 'end': '2026-10-11', 'settlement_date': '2026-10-12'},
        {'start': '2026-09-28', 'end': '2026-10-04', 'settlement_date': '2026-10-05'}]
    assert {r['date'] for r in result['items']} == {None, '2026-10-05', '2026-10-06', '2026-10-07'}
    assert result['hourly'] == []
    assert result['summary']['official_total_usd'] == 777
    assert source.snapshot == before


def test_saturday_sunday_never_becomes_an_arbitrary_day_or_partial_payment():
    source = weekly_book(rows=[entry('semana2', 'weekend')])
    daily = build_entries([source], day='2026-10-10')
    assert daily['total'] == 0 and daily['coverage']['period_excluded'] == 1
    weekend = build_entries([source], date_from='2026-10-10', date_to='2026-10-11')
    assert weekend['total'] == 1 and weekend['summary']['currencies'][0]['gross'] == 100
    assert weekend['items'][0]['date'] is None
    assert weekend['items'][0]['period_start'] == '2026-10-10'
    assert weekend['items'][0]['period_end'] == '2026-10-11'
    assert weekend['daily'] == []


@pytest.mark.parametrize('year,month,sheet,day,expected', [
    (2026, 10, 'semana1', 'thu', '2026-10-01'),
    (2026, 10, 'semana2', 'mon', '2026-10-05'),
    (2026, 9, 'semana1', 'mon', '2026-08-31'),
    (2026, 9, 'semana5', 'wed', '2026-09-30'),
    (2026, 2, 'semana1', 'sun', '2026-02-01'),
    (2026, 2, 'semana2', 'mon', '2026-02-02'),
    (2024, 2, 'semana5', 'thu', '2024-02-29'),
    (2027, 1, 'semana 1', 'mon', '2026-12-28'),
])
def test_calendar_uses_workbook_period_not_current_system_date(year, month, sheet, day, expected):
    result = build_entries([weekly_book(year=year, month=month, rows=[entry(sheet, day)])], day=expected)
    assert result['total'] == 1
    assert result['items'][0]['date'] == expected
    assert result['items'][0]['date_source'] == 'week_day'


def test_week_crossing_months_combines_saved_rows_and_ignores_live_archive_copy():
    september = weekly_book('sep', month=9, rows=[entry('semana5', 'mon')], kind='archive')
    ignored = weekly_book('copy', month=9, rows=[entry('semana5', 'mon', amount='9999')])
    october = weekly_book('oct', rows=[entry('semana1', 'thu', amount='200')])
    result = build_entries([september, ignored, october], year=2026, month=10,
                           date_from='2026-09-28', date_to='2026-10-04', payment_method='maquina', limit=1)
    assert result['total'] == 2 and len(result['items']) == 1
    assert result['summary']['currencies'][0]['gross'] == 300
    assert result['payments'][0]['currencies'][0]['net'] == 300
    assert result['summary']['official_total_usd'] == 777


def test_explicit_date_anchors_undated_weekdays_and_private_projection_is_consistent():
    source = weekly_book(rows=[entry('semana1', None, recorded='2026-10-13'),
                              entry('semana1', 'mon', seller='Junior', row=13)])
    before = deepcopy(source.snapshot)
    public = build_entries([source], seller='Junior', day='2026-10-12')
    private = build_entries(private_workbooks([source], 'Junior'), seller='Junior', day='2026-10-12', private=True)
    assert public['items'] == private['items']
    assert private['total'] == 1 and private['items'][0]['date'] == '2026-10-12'
    assert 'Lucas' not in str(private)
    assert source.snapshot == before
    recorded = build_entries([source], day='2026-10-13')['items'][0]
    assert recorded['date_source'] == 'recorded'


def test_multiple_real_weeks_in_one_tab_leave_undated_rows_unresolved():
    source = weekly_book(rows=[entry('semana1', None, recorded='2026-10-01'),
                              entry('semana1', None, recorded='2026-10-08', row=13),
                              entry('semana1', 'thu', row=14)])
    result = build_entries([source], day='2026-10-01')
    assert result['total'] == 1 and result['coverage']['undated_excluded'] == 1


def test_old_diagnostics_and_undated_rows_do_not_flood_current_week():
    old = weekly_book('old', year=2021, month=9, rows=[entry('unknown', None)], kind='archive')
    old.snapshot['entries']['diagnostics'] = [{'sheet': 'semana 2', 'skipped_rows': 1}]
    source = weekly_book()
    result = build_entries([old, source], date_from='2026-10-05', date_to='2026-10-11')
    assert result['coverage']['skipped_rows'] == result['coverage']['undated_excluded'] == 0
    assert result['coverage']['issues'] == []
    historical = build_entries([old, source], year=2021, month=9)
    assert historical['coverage']['skipped_rows'] == 1
    assert historical['coverage']['issues'] == [{'filename': old.filename, 'sheet': 'semana 2', 'skipped_rows': 1}]


def test_api_weekly_dates_keep_authenticated_seller_and_query_does_not_write(client):
    from app.database import get_db
    browser, user = client
    session = browser.app.dependency_overrides[get_db]()
    db = next(session)
    source = weekly_book(rows=[entry('semana1', 'thu', seller='Lucas', amount='999'),
                              entry('Planilha1', 'mon', seller='Junior', amount='120')])
    before = deepcopy(source.snapshot)
    try:
        db.add(source)
        db.commit()
        response = browser.get('/bi/entries?year=2026&month=10&seller=Lucas&payment_method=maquina&date_from=2026-10-05&date_to=2026-10-11')
        assert response.status_code == 200
        result = response.json()
        assert result['total'] == 1 and result['items'][0]['seller'] == 'Junior'
        assert result['items'][0]['date'] == '2026-10-05'
        assert result['summary']['currencies'][0]['net'] == 120
        assert '999' not in response.text and 'Lucas' not in response.text
        db.refresh(source)
        assert source.snapshot == before
    finally:
        session.close()
