"""Payment units are business rules, independent of the sale's G$ ledger."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from fastapi import HTTPException

PAYMENT_CURRENCIES = {
    'cash_usd': 'USD', 'cash_brl': 'BRL', 'cash_gs': 'GS', 'cash_eur': 'EUR',
    'card_credit_py': 'GS', 'card_debit_py': 'GS', 'qr_py': 'GS',
    'pix_personal': 'BRL', 'pix_thais': 'BRL', 'maquina_thais': 'BRL',
    'transfer_py': 'GS', 'usdt': 'USDT', 'mercadopago': 'BRL', 'fiado': 'GS',
}
CURRENCIES = {'GS', 'PYG', 'USD', 'BRL', 'EUR', 'USDT'}
CARD_METHODS = {'card_credit_py', 'card_debit_py'}
CARD_NET_FACTOR = Decimal('.94')


def validate_payment(payment, *, preserve_legacy=False):
    """Legacy records may be kept unchanged by owner edits, never newly assigned."""
    data = dict(payment)
    currency = data['currency']
    expected = PAYMENT_CURRENCIES.get(data['method'])
    if currency not in CURRENCIES:
        raise HTTPException(422, 'Moeda de pagamento inválida.')
    if not preserve_legacy and (not expected or ('GS' if currency == 'PYG' else currency) != expected):
        raise HTTPException(422, f'Selecione um método de pagamento atual e sua moeda obrigatória: {expected or "método não disponível"}.')
    try:
        amount, rate, converted = (Decimal(str(data[k])) for k in ('amount_original', 'exchange_rate', 'amount_gs'))
        fee = Decimal(str(data.get('card_fee_gs', 0)))
        percent = Decimal(str(data.get('card_fee_percent', 0)))
        if not all(v.is_finite() for v in (amount, rate, converted, fee, percent)):
            raise ValueError()
        if not 0 <= amount <= Decimal('9999999999999.99') or not 0 <= converted <= Decimal('9999999999999.99'):
            raise ValueError()
        if amount != amount.quantize(Decimal('.01')) or converted != converted.quantize(Decimal('.01')):
            raise ValueError()
        rate = rate.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
        if not 0 < rate <= Decimal('999999999'):
            raise ValueError()
        if currency in ('GS', 'PYG') and rate != 1:
            raise ValueError()
        if data['method'] in CARD_METHODS and not (preserve_legacy and percent == fee == 0):
            # amount_original is the terminal charge; amount_gs settles goods only.
            # Ceiling a whole guarani recovers the full 6%, with < G$1 rounding.
            if percent != 6 or currency not in ('GS', 'PYG') or amount != amount.to_integral_value():
                raise ValueError()
            if amount != (converted / CARD_NET_FACTOR).to_integral_value(rounding=ROUND_CEILING):
                raise ValueError()
            if fee != amount - converted or fee < 0:
                raise ValueError()
        elif fee != 0 or percent != 0 or abs((amount * rate).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) - converted) > 1:
            raise ValueError()
    except (ValueError, ArithmeticError):
        raise HTTPException(422, 'Confira o valor, a moeda e o câmbio do pagamento.') from None
    data.update(amount_original=amount, exchange_rate=rate, amount_gs=converted,
                card_fee_gs=fee, card_fee_percent=percent)
    return data


def unchanged_payment(payment, original):
    # Compare every submitted field; one old row cannot authorize a different payment.
    for key, value in payment.items():
        previous = getattr(original, key)
        if key in ('amount_original', 'exchange_rate', 'amount_gs', 'card_fee_gs', 'card_fee_percent'):
            if Decimal(str(value)) != Decimal(str(previous or 0)):
                return False
        elif str(value or '') != str(previous or ''):
            return False
    return True
