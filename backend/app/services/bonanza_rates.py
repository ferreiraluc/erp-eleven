"""Read the same public JSON feed as Bonanza's website, at most every six hours."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import requests
from sqlalchemy import text
from ..models.exchange_sync import ExchangeSync
from ..models.exchange_rate import ExchangeRate, CurrencyPair
from ..models.access import now

URL='https://www.bonanzacambios.com.py/api/board'
SOURCE='Bonanza · Jebai · Venta'


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def lock_rates(db):
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(711015)'))


def parse(data,moment):
    try:
        source_at=datetime.fromisoformat(data['actualizado'].replace('Z','+00:00'))
        if source_at.tzinfo is None or source_at>moment+timedelta(minutes=5) or source_at<moment-timedelta(days=7):
            raise ValueError('outdated')
        branches=[b for b in data['sucursales'] if b['cod']==2 and b['corto']=='JEBAI']
        if len(branches)!=1: raise ValueError('branch')
        branch=branches[0]
        def rate(rows,prefix,minimum,maximum):
            values=[r['venta'] for r in rows if r['prefix']==prefix]
            if len(values)!=1 or isinstance(values[0],bool): raise ValueError('pair')
            number=Decimal(str(values[0]))
            if not number.is_finite() or not minimum<=number<=maximum: raise ValueError('range')
            return number.quantize(Decimal('.0001'))
        return source_at, {CurrencyPair.USD_TO_PYG:rate(branch['cotizaciones'],'usa',1000,100000),
            CurrencyPair.USD_TO_BRL:rate(branch['arbitrajes'],'dore',Decimal('.1'),100)}
    except (KeyError,TypeError,ValueError,ArithmeticError,AttributeError):
        raise ValueError('invalid_or_outdated_board') from None


def fetch():
    try:
        with requests.get(URL,timeout=(5,15),stream=True,allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code!=200: raise ValueError('redirect')
            body=bytearray()
            for chunk in response.iter_content(16384):
                body.extend(chunk)
                if len(body)>262144: raise ValueError('large_board')
            import json
            return json.loads(body)
    except (requests.RequestException,ValueError):
        raise ValueError('provider_unavailable') from None


def sync(db,fetcher=None,moment=None,force=False):
    lock_rates(db)
    config=db.get(ExchangeSync,'bonanza',populate_existing=True)
    moment=moment or now()
    if not config or not config.enabled: return {'updated':False}
    if not force and config.last_attempt and utc(config.last_attempt)>moment-timedelta(hours=6):
        return {'updated':False}
    config.last_attempt=moment
    try:
        source_at,rates=parse((fetcher or fetch)(),moment)
        if config.source_at and source_at<utc(config.source_at): raise ValueError('older_board')
        for pair,value in rates.items():
            active=db.query(ExchangeRate).filter_by(currency_pair=pair,is_active=True).with_for_update().all()
            if len(active)==1 and active[0].rate==value:
                active[0].source=SOURCE
                continue
            for previous in active: previous.is_active=False
            db.flush()
            db.add(ExchangeRate(currency_pair=pair,rate=value,source=SOURCE,is_active=True,
                updated_by='Sistema · Bonanza',notes=f'JEBAI (2), venta; publicado {source_at.isoformat()}'))
        config.last_success=moment; config.source_at=source_at; config.last_error=None
        db.flush()
        return {'updated':True}
    except ValueError as exc:
        config.last_error=str(exc)[:40]
        db.flush()
        return {'updated':False,'error':config.last_error}


def run_due():
    from ..database import SessionLocal
    with SessionLocal() as db:
        result=sync(db); db.commit()
        return result
