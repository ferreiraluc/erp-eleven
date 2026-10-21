"""Payment currency rules through real routes, only disposable sales and stock."""
from decimal import Decimal
import pytest
from test_pdv_unknown_stock import pdv_app, make_item, sale_payload, balances
from test_pdv_management import sold, edit_body, command
from app.models.pdv import PdvPayment, PdvSale, PdvFiadoMovement
from app.models.inventory import StockMovement
from app.services.pdv_payments import PAYMENT_CURRENCIES


def payload(method, currency, rate=1):
    return {'method': method, 'currency': currency, 'exchange_rate': rate,
            'amount_original': 100, 'amount_gs': 100 * rate}


@pytest.mark.parametrize('method,currency', PAYMENT_CURRENCIES.items())
def test_every_method_persists_its_unit_rate_and_original_amount(pdv_app, method, currency):
    factory, client, cid = pdv_app
    rate = 1 if currency == 'GS' else 1250 if currency == 'BRL' else 6500
    body = sale_payload([None], cid, avulso=True)
    body['items'][0]['unit_price_gs'] = 100 * rate
    body['payments'] = [payload(method, currency, rate)]
    response = client.post('/api/pdv/sales', json=body)
    assert response.status_code == 201, response.text
    payment = response.json()['payments'][0]
    assert all(payment[key] == value for key, value in body['payments'][0].items())
    detail = client.get('/api/pdv/management/' + response.json()['id']).json()
    correction = client.post('/api/pdv/management/' + detail['id'] + '/preview', json=command('edit', edit=edit_body(detail)))
    assert correction.status_code == 200, correction.text
    if method == 'fiado':
        with factory() as db:
            assert db.query(PdvFiadoMovement).one().valor_gs == 100


@pytest.mark.parametrize('payment', [
    payload('card_credit_py', 'USD', 6500), payload('card_debit_py', 'BRL', 1250),
    payload('qr_py', 'USD', 6500), payload('pix_personal', 'GS'),
    payload('pix_thais', 'USD', 6500), payload('maquina_thais', 'GS'),
    payload('mercadopago', 'GS'), payload('usdt', 'USD', 6500),
    payload('fiado', 'USD', 6500), payload('transfer_py', 'BRL', 1250),
    payload('cash_usd', 'BRL', 1250), payload('card', 'USD', 6500),
    payload('unknown', 'GS'), payload('cash_gs', 'GS', 2),
    payload('cash_brl', 'BRL', 0), payload('cash_brl', 'BRL', -1),
    {**payload('pix_thais', 'BRL', 1250), 'amount_gs': 1},
    {**payload('pix_thais', 'BRL', 1250), 'amount_original': 'NaN'},
    {**payload('pix_thais', 'BRL', 1250), 'exchange_rate': 'Infinity'},
    {**payload('cash_gs', 'GS'), 'amount_original': 100.001},
])
def test_invalid_currency_or_conversion_never_changes_stock_or_finance(pdv_app, payment):
    factory, client, cid = pdv_app
    with factory() as db:
        rid = make_item(db).id; db.commit()
    body = sale_payload([rid], cid); body['payments'] = [payment]
    response = client.post('/api/pdv/sales', json=body)
    assert response.status_code == 422, response.text
    with factory() as db:
        assert balances(db, rid) == (10, 6, 4)
        assert not db.query(PdvSale).count() and not db.query(PdvPayment).count()
        assert not db.query(StockMovement).count() and not db.query(PdvFiadoMovement).count()


def test_owner_cannot_bypass_currency_rule_or_duplicate_legacy_payment(pdv_app):
    factory, client, _ = pdv_app
    _, sid, data = sold(pdv_app, quantity=1)
    edit = edit_body(data)
    edit['payments'][0].update(method='pix_thais', currency='GS')
    assert client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit)).status_code == 422
    # Pre-existing generic card record is preserved, not reclassified as debit/credit.
    with factory() as db:
        db.query(PdvPayment).one().method = 'card'; db.commit()
    data = client.get('/api/pdv/management/' + sid).json()
    edit = edit_body(data)
    assert client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit)).status_code == 200
    edit['payments'][0]['reference'] = 'changed'
    assert client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit)).status_code == 422
    edit = edit_body(client.get('/api/pdv/management/' + sid).json())
    edit['items'][0]['unit_price_gs'] *= 2
    edit['payments'].append(dict(edit['payments'][0]))
    assert client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit)).status_code == 422


def test_mixed_payments_keep_independent_exchange_rates_and_fiado_requires_customer(pdv_app):
    _, client, cid = pdv_app
    body = sale_payload([None], cid, avulso=True)
    body['items'][0]['unit_price_gs'] = 175000
    body['payments'] = [payload('pix_thais', 'BRL', 1250), {**payload('cash_usd', 'USD', 5000), 'amount_original': 10, 'amount_gs': 50000}]
    assert client.post('/api/pdv/sales', json=body).status_code == 201
    body.pop('cliente_id'); body['payments'] = [payload('fiado', 'GS')]
    assert client.post('/api/pdv/sales', json=body).status_code == 422


@pytest.mark.parametrize('method,paid', [('pix_thais', 101), ('fiado', 101), ('cash_gs', 99)])
def test_checkout_rejects_non_cash_change_or_missing_payment_without_writes(pdv_app, method, paid):
    factory, client, cid = pdv_app
    with factory() as db:
        rid = make_item(db).id; db.commit()
    body = sale_payload([rid], cid)
    body['payments'] = [{'method': method, 'currency': 'BRL' if method == 'pix_thais' else 'GS',
                         'exchange_rate': 1, 'amount_original': paid, 'amount_gs': paid}]
    response = client.post('/api/pdv/sales', json=body)
    assert response.status_code == 422, response.text
    with factory() as db:
        assert balances(db, rid) == (10, 6, 4)
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == 0
        assert db.query(StockMovement).count() == db.query(PdvFiadoMovement).count() == 0


def test_cash_change_stays_explicit_and_a_rounded_product_closes_without_change(pdv_app):
    _, client, cid = pdv_app
    body = sale_payload([None], cid, avulso=True)
    body['payments'] = [{'method': 'cash_usd', 'currency': 'USD', 'exchange_rate': 6000,
                         'amount_original': 428.58, 'amount_gs': 2571480}]
    body['items'][0]['unit_price_gs'] = 2571450
    with_change = client.post('/api/pdv/sales', json=body)
    assert with_change.status_code == 201, with_change.text
    assert Decimal(str(with_change.json()['total_gs'])) == Decimal('2571450')
    assert Decimal(client.get('/api/pdv/management/' + with_change.json()['id']).json()['payment_difference_gs']) == 30
    body['items'][0]['unit_price_gs'] = 2571480
    aligned = client.post('/api/pdv/sales', json=body)
    assert aligned.status_code == 201, aligned.text
    assert Decimal(str(aligned.json()['total_gs'])) == Decimal(str(aligned.json()['payments'][0]['amount_gs']))
    assert Decimal(client.get('/api/pdv/management/' + aligned.json()['id']).json()['payment_difference_gs']) == 0


def test_mixed_payment_change_cannot_exceed_the_cash_part(pdv_app):
    factory, client, cid = pdv_app
    body = sale_payload([None], cid, avulso=True)
    body['payments'] = [
        {'method': 'pix_thais', 'currency': 'BRL', 'exchange_rate': 1, 'amount_original': 80, 'amount_gs': 80},
        {'method': 'cash_gs', 'currency': 'GS', 'exchange_rate': 1, 'amount_original': 30, 'amount_gs': 30},
    ]
    accepted = client.post('/api/pdv/sales', json=body)
    assert accepted.status_code == 201, accepted.text
    assert Decimal(client.get('/api/pdv/management/' + accepted.json()['id']).json()['payment_difference_gs']) == 10

    body['payments'][0].update(amount_original=120, amount_gs=120)
    body['payments'][1].update(amount_original=1, amount_gs=1)
    rejected = client.post('/api/pdv/sales', json=body)
    assert rejected.status_code == 422, rejected.text
    with factory() as db:
        assert db.query(PdvSale).count() == 1
