"""Payment reports are read-only projections of synthetic worksheet snapshots."""
from copy import deepcopy

import pytest

from test_sales_bi_entries import client, workbook, detail_sheet
from test_sales_bi_day_boundary import boundary_book
from app.services.sales_bi_entries import build_entries, payment_key
from app.services.sales_bi_entry_parser import extract_entries


@pytest.mark.parametrize('raw,key', [(None, 'dinheiro'), ('', 'dinheiro'), ('   ', 'dinheiro'),
    ('Máquina', 'maquina'), ('MAQUINA', 'maquina'), (' máquina ', 'maquina'),
    ('Maq', 'maquina'), ('MAQ', 'maquina'), (' maq ', 'maquina'), ('Maq Pix', 'maq pix'),
    ('Crédito', 'credito'), ('Cartão de Crédito', 'credito'), ('Débito', 'debito'),
    ('Thaís', 'thais'), ('Dinheiro', 'dinheiro'), ('Pix Banco A', 'pix banco a')])
def test_payment_spelling_and_blank_cash_convention(raw, key):
    assert payment_key(raw) == key


def payment_book():
    source = workbook()
    base = source.snapshot['entries']['rows'][0]
    records = []
    for index, (method, amount, currency, day) in enumerate([
        ('Máquina', '4500', 'BRL', '2026-09-23'),
        ('Maq', '500', 'BRL', '2026-09-24'),
        ('Máquina', '30', 'USD', '2026-09-24'),
        ('Crédito', '100', 'BRL', '2026-09-24'),
        ('Débito', '200', 'BRL', '2026-09-25'),
        ('Thais', '300', 'BRL', '2026-09-25'),
        (None, '50', 'BRL', '2026-09-23'),
        ('', '70', 'BRL', None),
        ('Dinheiro', '20', 'BRL', '2026-09-24'),
    ]):
        records.append({**base, 'seller': 'Lucas', 'row': 13 + index, 'source_cell': f'semana1!C{13+index}',
                        'payment_method': method, 'gross': amount, 'net': amount if index != 1 else None,
                        'currency': currency, 'date': day})
    source.snapshot['entries']['rows'] = records
    return source


@pytest.mark.parametrize('method', ['máquina', 'maquina', 'Maq'])
def test_machine_filter_totals_all_rows_before_pagination_and_keeps_currencies_separate(method):
    source = payment_book(); before = deepcopy(source.snapshot)
    result = build_entries([source], payment_method=method, seller='Lucas', limit=1)
    assert result['total'] == 3 and len(result['items']) == 1
    assert result['summary']['currencies'] == [
        {'currency': 'BRL', 'count': 2, 'gross': 5000, 'net': 4500, 'net_available': 1},
        {'currency': 'USD', 'count': 1, 'gross': 30, 'net': 30, 'net_available': 1}]
    assert result['payments'][0]['payment_type'] == 'maquina' and result['payments'][0]['count'] == 3
    assert source.snapshot == before
    full = build_entries([source], seller='Lucas')
    assert result['summary']['official_total_usd'] == full['summary']['official_total_usd']
    assert result['reconciliation'] == full['reconciliation']
    assert {'credito', 'debito', 'maquina', 'thais', 'dinheiro'} == {p['value'] for p in full['payment_methods']}
    assert {'value': 'maquina', 'label': 'Máquina'} in full['payment_methods']
    assert any(r['payment_method'] == 'Maq' and r['payment_type'] == 'maquina' for r in full['items'])


def test_blank_and_explicit_cash_are_combined_without_modifying_originals():
    source = payment_book(); before = deepcopy(source.snapshot)
    result = build_entries([source], payment_method='Dinheiro')
    assert result['total'] == 3
    assert result['summary']['currencies'][0]['gross'] == 140
    assert all(r['payment_type'] == 'dinheiro' for r in result['items'])
    assert any(r['payment_method'] is None for r in result['items'])
    assert build_entries([source], search='dinheiro')['total'] == 3
    assert source.snapshot == before


def test_date_range_is_inclusive_filters_all_aggregates_and_reports_unknown_dates():
    source = payment_book()
    result = build_entries([source], date_from='2026-09-23', date_to='2026-09-24', payment_method='dinheiro')
    assert result['total'] == 2 and result['coverage']['undated_excluded'] == 1
    assert result['summary']['currencies'][0]['gross'] == 70
    assert sum(d['count'] for d in result['daily']) == sum(h['count'] for h in result['hourly']) == 2
    assert build_entries([source], date_from='2026-09-24', payment_method='maquina')['total'] == 2
    assert build_entries([source], date_to='2026-09-23', payment_method='maquina')['total'] == 1
    assert build_entries([source], payment_method='unknown')['total'] == 0


def test_range_crosses_workbook_years_and_deduplicates_current_archive_sources():
    older = boundary_book(year=2025, month=12, day='2026-01-01', key='older')
    duplicate = boundary_book(year=2025, month=12, day='2026-01-01', key='duplicate', kind='current')
    january = boundary_book(year=2026, month=1, day='2026-01-02', key='january')
    result = build_entries([older, duplicate, january], year=2026, month=1, seller='Junior',
                           date_from='2026-01-01', date_to='2026-01-02', payment_method='pix', limit=1)
    assert result['total'] == 2 and result['summary']['currencies'][0]['gross'] == 20
    assert result['coverage']['source_count'] == 2 and result['summary']['official_total_usd'] == 100


@pytest.mark.parametrize('method', ['Maquina', 'Maq'])
def test_parser_accepts_new_machine_type_and_keeps_blank_cells(method):
    data = detail_sheet()
    data['rows'][12][1:6] = ['R$', 4500, 'Lucas', method, 4400]
    data['rows'][13][4] = None
    records = extract_entries([('Planilha1', data)], [], year=2026, month=9)['rows']
    assert records[0]['payment_method'] == method and records[0]['gross'] == '4500'
    assert records[1]['payment_method'] is None


def test_api_machine_filter_recognizes_existing_maq_snapshots_with_seller_scope(client):
    from app.database import get_db
    browser, user = client
    session = browser.app.dependency_overrides[get_db]()
    db = next(session)
    try:
        source = payment_book()
        source.id = 'machine-payments'
        source.month = 10
        source.snapshot['entries']['rows'][1]['seller'] = 'Junior'
        db.add(source)
        db.commit()
    finally:
        session.close()
    response = browser.get('/bi/entries?month=10&seller=Lucas&payment_method=maquina')
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1
    assert body['items'][0]['payment_method'] == 'Maq'
    assert body['items'][0]['payment_type'] == 'maquina'
    assert body['items'][0]['seller'] == 'Junior'
    assert body['summary']['currencies'][0]['gross'] == 500
    assert body['payment_methods'] == [{'value': 'maquina', 'label': 'Máquina'}]
    user.sales_scope = 'all'
    assert browser.get('/bi/entries?month=10&payment_method=maquina').json()['total'] == 3


def test_api_payment_filter_cannot_leak_other_sellers_through_totals_or_options(client):
    browser, user = client
    response = browser.get('/bi/entries?seller=Lucas&payment_method=dinheiro&date_from=2026-09-01&date_to=2026-09-30')
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 0 and body['coverage']['undated_excluded'] == 1
    assert body['payments'] == [] and body['summary']['official_total_usd'] == 100
    assert 'Lucas' not in response.text and 'Sol' not in response.text and 'USD' not in response.text
    assert browser.get('/bi/entries?payment_method=dinheiro').json()['total'] == 1
    user.sales_scope = 'all'
    all_cash = browser.get('/bi/entries?payment_method=dinheiro').json()
    assert all_cash['total'] == 3 and all_cash['payments'][0]['count'] == 3


def test_api_date_range_reads_a_boundary_week_in_another_workbook_year(client):
    from app.database import get_db
    browser, _ = client
    session = browser.app.dependency_overrides[get_db]()
    db = next(session)
    try:
        db.add(boundary_book(year=2025, month=12, day='2026-01-01', key='boundary'))
        db.commit()
    finally:
        session.close()
    response = browser.get('/bi/entries?year=2026&month=1&date_from=2026-01-01&date_to=2026-01-02&payment_method=pix')
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1 and body['items'][0]['source_id'] == 'boundary'
    assert body['summary']['currencies'][0]['gross'] == 10
    assert body['summary']['official_total_usd'] is None


@pytest.mark.parametrize('query', [
    'date_from=2026-09-31', 'date_from=2026-10-01&date_to=2026-09-01',
    'day=2026-09-01&date_to=2026-09-30', 'payment_method=' + 'x' * 81,
])
def test_api_rejects_invalid_ranges_and_oversized_methods(client, query):
    browser, _ = client
    assert browser.get('/bi/entries?' + query).status_code == 422
