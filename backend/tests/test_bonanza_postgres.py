"""Frozen USD metadata backfill never rewrites sale/payment amounts."""
from uuid import uuid4
import sqlalchemy as sa
from test_access_postgres import pg, upgrade


def test_historical_backfill_uses_evidence_and_never_todays_quote(pg):
    engine,schema=pg
    first,second,unknown=[uuid4() for _ in range(3)]
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE pdv_sales(id uuid PRIMARY KEY,created_at timestamp,total_gs numeric(15,2))')
        conn.exec_driver_sql('CREATE TABLE exchange_rates(id uuid PRIMARY KEY,currency_pair varchar(30),rate numeric(12,4),created_at timestamp)')
        conn.exec_driver_sql('CREATE TABLE pdv_payments(sale_id uuid,currency varchar(4),exchange_rate numeric(15,6),amount_gs numeric(15,2))')
        conn.execute(sa.text("INSERT INTO pdv_sales VALUES(:id,'2026-10-28',480000),(:second,'2026-10-01',12000),(:unknown,'2026-09-01',7000)"),{'id':first,'second':second,'unknown':unknown})
        conn.execute(sa.text("INSERT INTO exchange_rates VALUES(:id,'USD_TO_PYG',6000,'2026-10-27'),(:future,'USD_TO_PYG',7000,'2026-10-29')"),{'id':uuid4(),'future':uuid4()})
        conn.execute(sa.text("INSERT INTO pdv_payments VALUES(:id,'USD',6100,12000)"),{'id':second})
        upgrade(conn,'u3d4e5f6a7b8_usd_sales_bonanza.py')
        rates=dict(conn.execute(sa.text('SELECT id,usd_rate_gs FROM pdv_sales')).all())
        assert rates[first]==6000 and rates[second]==6100 and rates[unknown] is None
        assert conn.execute(sa.text('SELECT sum(total_gs) FROM pdv_sales')).scalar()==499000
        assert conn.execute(sa.text('SELECT amount_gs FROM pdv_payments')).scalar()==12000
        assert conn.execute(sa.text('SELECT count(*) FROM exchange_sync')).scalar()==0


def test_overlapping_workers_fetch_one_board(pg,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models.exchange_sync import ExchangeSync
    from app.models.exchange_rate import ExchangeRate
    from app.services import bonanza_rates
    from app.models.access import now
    from test_bonanza_usd import board
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[ExchangeSync.__table__,ExchangeRate.__table__])
    factory=sessionmaker(bind=isolated,autoflush=False)
    moment=now(); barrier=Barrier(2);calls=[]
    def fetch(): calls.append(1);return board(moment)
    try:
        with factory() as db: db.add(ExchangeSync(id='bonanza',enabled=True));db.commit()
        def run(_):
            with factory() as db:
                barrier.wait(timeout=5);result=bonanza_rates.sync(db,fetch,moment);db.commit();return result
        with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(run,range(2)))
        assert sum(bool(r['updated']) for r in results)==1 and len(calls)==1
        with factory() as db: assert db.query(ExchangeRate).filter_by(is_active=True).count()==2
    finally: isolated.dispose()


def test_summary_rounds_each_sale_half_up_in_postgresql(pg,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Usuario
    from app.models.usuario import UsuarioRole
    from app.models.pdv import PdvSale
    from app.config import settings
    from app.services.pdv_management import listing
    from decimal import Decimal
    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated)
    factory=sessionmaker(bind=isolated,autoflush=False)
    try:
        with factory() as db:
            user=Usuario(nome='Synthetic Lucas',email='lucas@eleven.com',role=UsuarioRole.ADMIN,senha_hash='unused');db.add(user)
            db.add_all([PdvSale(total_gs=90,subtotal_gs=90,usd_rate_gs=6000),PdvSale(total_gs=90,subtotal_gs=90,usd_rate_gs=6000)])
            db.commit()
            data=listing(db,user)
            assert Decimal(data['summary']['net_usd'])==Decimal('.04')
            assert all(Decimal(row['net_usd'])==Decimal('.02') for row in data['items'])
    finally: isolated.dispose()
