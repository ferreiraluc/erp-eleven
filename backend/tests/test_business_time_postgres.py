"""Actual PostgreSQL storage and business-day queries in disposable schemas."""
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from test_access_postgres import pg
from test_pdv_stock_postgres import pdv_pg
from app.database import engine_options
from app.models.pdv import PdvSale
from app.services.business_time import BUSINESS_TZ, business_datetime, stored_day_start, stored_instant
from app.services.pdv_receipts import build_snapshot


def test_connection_stores_legacy_and_aware_instants_in_utc_without_data_rewrites(pg):
    engine, schema = pg
    options = engine_options(str(engine.url))
    options['connect_args']['options'] += f' -c search_path={schema}'
    isolated = sa.create_engine(engine.url, **options)
    local = datetime(2026, 11, 2, 15, 15, tzinfo=BUSINESS_TZ)
    try:
        with isolated.begin() as connection:
            assert connection.exec_driver_sql('SHOW timezone').scalar() == 'UTC'
            connection.exec_driver_sql('CREATE TABLE time_contract (legacy timestamp, event timestamptz)')
            connection.execute(sa.text('INSERT INTO time_contract VALUES (:instant,:instant)'), {'instant':local})
        with Session(isolated) as db:
            legacy, event = db.execute(sa.text('SELECT legacy,event FROM time_contract')).one()
            assert legacy == datetime(2026, 11, 2, 18, 15)
            assert event == local
            assert business_datetime(stored_instant(legacy, db)) == local
            assert business_datetime(event) == local
            assert db.execute(sa.text('SELECT legacy FROM time_contract')).scalar() == legacy
    finally:
        isolated.dispose()


def test_sale_filters_use_brasilia_midnight_and_receipt_matches_sale_time(pdv_pg):
    factory, client, _, _, _ = pdv_pg
    moments = [(2, 59, 59), (3, 0, 0), (18, 15, 0)]
    with factory() as db:
        # Existing fixture connections inherit the developer's server timezone;
        # production connections explicitly use engine_options(...), tested above.
        db.execute(sa.text("SET TIME ZONE 'UTC'"))
        sales = [PdvSale(cliente_nome=f'Time fixture {hour}', created_at=datetime(2026,11,2,hour,minute,second,tzinfo=timezone.utc)) for hour,minute,second in moments]
        excluded_next = PdvSale(cliente_nome='Next day',created_at=datetime(2026,11,3,3,tzinfo=timezone.utc))
        db.add_all(sales+[excluded_next]); db.commit()
        ids=[str(row.id) for row in sales]
        snapshot = build_snapshot(sales[-1], db=db)
        assert business_datetime(snapshot['date']).isoformat() == '2026-11-02T15:15:00-03:00'
    result=client.get('/api/pdv/management',params={'date_from':'2026-11-02','date_to':'2026-11-02'})
    assert result.status_code == 200, result.text
    assert {row['id'] for row in result.json()['items']} == set(ids[1:])
    legacy=client.get('/api/pdv/sales',params={'date_from':'2026-11-02','date_to':'2026-11-02'})
    assert legacy.status_code == 200, legacy.text
    assert {row['id'] for row in legacy.json()} == set(ids[1:])
