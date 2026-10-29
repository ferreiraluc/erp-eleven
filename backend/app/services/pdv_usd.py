"""Frozen sale presentation rate; existing G$ ledgers remain authoritative."""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from ..models.exchange_rate import ExchangeRate, CurrencyPair


def current_rate(db, expected=None):
    rows=db.query(ExchangeRate.rate).filter(ExchangeRate.currency_pair==CurrencyPair.USD_TO_PYG,
        ExchangeRate.is_active.is_(True)).with_for_update(read=True).all()
    rate=Decimal(str(rows[0][0])) if len(rows)==1 else None
    if rate is not None and (not rate.is_finite() or not 0<rate<=1000000): rate=None
    if expected is not None and (rate is None or Decimal(str(expected)) != rate):
        raise HTTPException(409,'O câmbio mudou. Atualize as taxas, confira o total em dólares e confirme novamente.')
    return rate


def convert(value, rate):
    if rate is None or not Decimal(str(rate)).is_finite() or Decimal(str(rate))<=0:
        return None
    return (Decimal(str(value or 0))/Decimal(str(rate))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
