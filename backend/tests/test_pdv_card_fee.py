"""Card terminal gross-up through real routes, with disposable merchandise/ledgers."""
from decimal import Decimal
import uuid
import pytest
from app.models.pdv import PdvSale, PdvPayment
from app.services.pdv_payments import validate_payment
from app.services.pdv_usd import notification_amount
from test_pdv_unknown_stock import pdv_app, sale_payload
from test_pdv_management import command, edit_body


def card(net=468000, method='card_credit_py'):
    gross = int((Decimal(str(net)) / Decimal('.94')).__ceil__())
    return dict(method=method, currency='GS', exchange_rate=1, amount_original=gross,
                amount_gs=net, card_fee_gs=float(Decimal(gross)-Decimal(str(net))), card_fee_percent=6)


@pytest.mark.parametrize('method', ['card_credit_py', 'card_debit_py'])
def test_full_and_split_card_charge_do_not_change_merchandise_or_create_change(pdv_app, method):
    factory, client, cid = pdv_app
    for split in (False, True):
        body = sale_payload([None], cid, avulso=True)
        body['items'][0]['unit_price_gs'] = 468000
        body['payments'] = [card(234000 if split else 468000, method)]
        if split:
            body['payments'].append(dict(method='cash_usd', currency='USD', exchange_rate=5850,
                                         amount_original=40, amount_gs=234000))
        result = client.post('/api/pdv/sales', json=body)
        assert result.status_code == 201, result.text
        sale = result.json()
        assert sale['total_gs'] == sale['items'][0]['unit_price_gs'] == 468000
        assert sum(p['amount_gs'] for p in sale['payments']) == 468000
        payment = sale['payments'][0]
        assert payment['amount_original'] == (248937 if split else 497873)
        assert payment['card_fee_gs'] == (14937 if split else 29873)
        detail = client.get(f"/api/pdv/management/{sale['id']}").json()
        assert Decimal(detail['payment_difference_gs']) == 0
        edit = edit_body(detail)
        preview = client.post(f"/api/pdv/management/{sale['id']}/preview", json=command('edit', edit=edit))
        assert preview.status_code == 200, preview.text
        assert Decimal(next(p for p in preview.json()['correction']['payments'] if p['method'] == method)['card_fee_gs']) == payment['card_fee_gs']
        cancel = client.post(f"/api/pdv/management/{sale['id']}/preview", json=command('cancel'))
        assert cancel.status_code == 200, cancel.text
        assert Decimal(cancel.json()['refund_gs']) == 468000
        assert any('acréscimo do cartão' in warning for warning in cancel.json()['warnings'])
    with factory() as db:
        assert db.query(PdvSale).count() == 2


@pytest.mark.parametrize('change', [
    {'card_fee_percent': 0}, {'card_fee_percent': 6.38}, {'card_fee_gs': 0},
    {'amount_original': 497872, 'card_fee_gs': 29872},
    {'amount_original': 497874, 'card_fee_gs': 29874},
    {'amount_original': 497873.50, 'card_fee_gs': 29873.50},
    {'amount_gs': 1, 'card_fee_gs': 497872},
    {'method': 'qr_py'}, {'method': 'cash_gs'}, {'exchange_rate': 1.06383},
])
def test_backend_rejects_tampered_card_charge_without_recording_sale(pdv_app, change):
    factory, client, cid = pdv_app
    body = sale_payload([None], cid, avulso=True)
    body['items'][0]['unit_price_gs'] = 468000
    body['payments'] = [{**card(), **change}]
    assert client.post('/api/pdv/sales', json=body).status_code == 422
    with factory() as db:
        assert db.query(PdvSale).count() == db.query(PdvPayment).count() == 0


def test_historical_card_payment_is_preserved_but_cannot_be_newly_assigned(pdv_app):
    factory, client, cid = pdv_app
    old = dict(method='card_credit_py', currency='GS', exchange_rate=1, amount_original=100, amount_gs=100)
    body = sale_payload([None], cid, avulso=True)
    result = client.post('/api/pdv/sales', json=body)
    sid = result.json()['id']
    with factory() as db:
        payment = db.query(PdvPayment).filter_by(sale_id=uuid.UUID(sid)).one()
        for key, value in old.items(): setattr(payment, key, value)
        db.commit()
    detail = client.get(f'/api/pdv/management/{sid}').json()
    edit = edit_body(detail); edit['notas'] = 'Preserve historical terminal amount'
    preview = client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit))
    assert preview.status_code == 200, preview.text
    edit['payments'].append(dict(edit['payments'][0]))
    edit['items'][0]['unit_price_gs'] = 200
    assert client.post(f'/api/pdv/management/{sid}/preview', json=command('edit', edit=edit)).status_code == 422
    body['payments'] = [old]
    assert client.post('/api/pdv/sales', json=body).status_code == 422


def test_manual_card_amount_is_net_of_six_percent():
    payment = validate_payment(card(188000))
    assert payment['amount_original'] == 200000
    assert payment['card_fee_gs'] == 12000
    assert notification_amount(4680000, 5850) == '800'
    assert notification_amount(4682925, 5850) == '800,50'
    assert notification_amount(4680000, None) == '—'
