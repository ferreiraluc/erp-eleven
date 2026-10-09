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
