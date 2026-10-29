"""Public quote parsing and frozen sale presentation use synthetic isolated data."""
from datetime import timedelta
from decimal import Decimal
import json
import io
import pytest
from pypdf import PdfReader
from test_assistant import setup
from test_pdv_unknown_stock import pdv_app, sale_payload
from app.database import Base
from app.models.exchange_sync import ExchangeSync
from app.models.exchange_rate import ExchangeRate, CurrencyPair
from app.models.pdv import PdvSale
from app.services import bonanza_rates as bonanza, pdv_receipts
from app.models.access import now


def board(moment):
    return {'actualizado':moment.isoformat(), 'sucursales':[
        {'cod':0,'corto':'MATRIZ','cotizaciones':[{'prefix':'usa','compra':100,'venta':200}], 'arbitrajes':[]},
        {'cod':2,'corto':'JEBAI','cotizaciones':[{'prefix':'usa','compra':5750,'venta':5850},
            {'prefix':'brasil','venta':1180}], 'arbitrajes':[{'prefix':'dore','compra':5.12,'venta':5.35}]}]}


def test_jebai_venta_uses_the_direct_usd_brl_quote():
    moment=now(); _,rates=bonanza.parse(board(moment),moment)
    assert rates=={CurrencyPair.USD_TO_PYG:Decimal('5850'),CurrencyPair.USD_TO_BRL:Decimal('5.35')}
    assert rates[CurrencyPair.USD_TO_BRL]!=Decimal('5850')/1180


@pytest.mark.parametrize('fault',['branch','missing','duplicate','zero','boolean','nan','old','future'])
def test_bad_quotes_are_rejected_before_any_update(fault):
    moment=now(); data=board(moment)
    if fault=='branch': data['sucursales'][1]['cod']=3
    if fault=='missing': data['sucursales'][1]['arbitrajes']=[]
    if fault=='duplicate': data['sucursales'].append(data['sucursales'][1])
    if fault in ('zero','boolean','nan'): data['sucursales'][1]['cotizaciones'][0]['venta']={'zero':0,'boolean':True,'nan':'NaN'}[fault]
    if fault=='old': data['actualizado']=(moment-timedelta(days=8)).isoformat()
    if fault=='future': data['actualizado']=(moment+timedelta(minutes=6)).isoformat()
    with pytest.raises(ValueError): bonanza.parse(data,moment)


def test_six_hour_schedule_preserves_history_and_failure_keeps_last_rates(setup):
    factory,_,_=setup; moment=now(); calls=[]
    def source(): calls.append(1); return board(moment)
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[ExchangeSync.__table__])
        assert not bonanza.sync(db,source,moment)['updated'] and not calls
        db.add(ExchangeSync(id='bonanza',enabled=True)); db.flush()
        assert bonanza.sync(db,source,moment)['updated']; db.commit()
        assert db.query(ExchangeRate).count()==2
        assert not bonanza.sync(db,source,moment+timedelta(hours=5,minutes=59))['updated']
        assert len(calls)==1
        assert bonanza.sync(db,source,moment+timedelta(hours=6))['updated']; db.commit()
        assert len(calls)==2 and db.query(ExchangeRate).count()==2
        def broken(): raise ValueError('provider_unavailable')
        result=bonanza.sync(db,broken,moment+timedelta(hours=12)); db.commit()
        assert result['error']=='provider_unavailable'
        assert db.query(ExchangeRate).filter_by(is_active=True).count()==2
        assert db.get(ExchangeSync,'bonanza').last_error
        changed=board(moment+timedelta(hours=18)); changed['sucursales'][1]['cotizaciones'][0]['venta']=5900
        assert bonanza.sync(db,lambda:changed,moment+timedelta(hours=18))['updated']; db.commit()
        assert db.query(ExchangeRate).count()==3
        assert db.query(ExchangeRate).filter_by(is_active=True,currency_pair=CurrencyPair.USD_TO_PYG).one().rate==5900


def test_sale_freezes_rate_ticket_total_usd_and_rejects_a_stale_quote(pdv_app):
    factory,client,customer=pdv_app
    body=sale_payload([],customer)
    body['items']=[{'item_name':'Synthetic shirt','quantity':1,'unit_price_gs':480000,'is_avulso':True,'location':'loja'}]
    body['payments']=[{'method':'cash_gs','currency':'GS','amount_original':480000,'exchange_rate':1,'amount_gs':480000}]
    body['usd_rate_gs']=6000
    result=client.post('/api/pdv/sales',json=body)
    assert result.status_code==201,result.text
    from uuid import UUID
    with factory() as db:
        sale=db.get(PdvSale,UUID(result.json()['id']))
        assert sale.usd_rate_gs==6000 and sale.total_gs==480000
        snap=pdv_receipts.build_snapshot(sale)
        from app.services.pdv_receipt_layout import view
        assert view(snap)['total']=='US$ 80,00'
        pdf_text=''.join(page.extract_text() for page in PdfReader(io.BytesIO(pdv_receipts.render(snap))).pages)
        assert 'US$ 80,00' in pdf_text
        assert view(snap)['payments'][0]['equivalent']=='US$ 80,00'
        rate=db.query(ExchangeRate).filter_by(is_active=True).one();rate.rate=7000;db.commit()
        assert view(pdv_receipts.build_snapshot(sale))['total']=='US$ 80,00'
        before=db.query(PdvSale).count()
    response=client.post('/api/pdv/sales',json=body)
    assert response.status_code==409 and 'câmbio mudou' in response.text
    with factory() as db: assert db.query(PdvSale).count()==before


def test_legacy_without_rate_never_makes_up_a_dollar_total():
    from app.services.pdv_receipt_layout import view
    snapshot={'sale_id':'12345678-1234-1234-1234-123456789012','date':now().isoformat(),'total':'480000',
        'subtotal':'480000','discount':'0','items':[],'payments':[],'customer':'Synthetic','seller':'Synthetic'}
    assert view(snapshot)['total']=='US$ —'


def test_sync_configuration_requires_owner_and_only_fetches_on_enable(setup,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.endpoints import exchange_sync
    from app.database import get_db
    from app.dependencies import get_current_active_user
    from app.models import Usuario
    from app.models.usuario import UsuarioRole
    from app.models.access import AuditEvent
    factory,_,uid=setup
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[ExchangeSync.__table__,AuditEvent.__table__])
    calls=[]
    def source():calls.append(1);return board(now())
    monkeypatch.setattr(bonanza,'fetch',source)
    app=FastAPI();app.include_router(exchange_sync.router,prefix='/bonanza')
    def database():
        with factory() as db:yield db
    def user():
        with factory() as db:return db.get(Usuario,uid)
    app.dependency_overrides[get_db]=database;app.dependency_overrides[get_current_active_user]=user
    client=TestClient(app)
    assert client.get('/bonanza').status_code==403
    assert client.put('/bonanza',json={'enabled':True}).status_code==403
    with factory() as db:
        u=db.get(Usuario,uid);u.email='lucas@eleven.com';u.role=UsuarioRole.ADMIN;db.commit()
    assert client.get('/bonanza').json()['enabled'] is False and not calls
    assert client.put('/bonanza',json={'enabled':True}).status_code==200 and len(calls)==1
    assert client.get('/bonanza').json()['column']=='Venta' and len(calls)==1
    assert client.put('/bonanza',json={'enabled':False}).json()['enabled'] is False and len(calls)==1


def test_sales_summary_sums_each_rounded_dollar_total_and_exposes_missing_rates(pdv_app):
    factory,client,_=pdv_app
    with factory() as db:
        db.add_all([PdvSale(total_gs=120,subtotal_gs=120,usd_rate_gs=6000),PdvSale(total_gs=120,subtotal_gs=120,usd_rate_gs=6000)])
        db.commit()
    data=client.get('/api/pdv/management').json()
    assert Decimal(data['summary']['net_usd'])==Decimal('.04')
    assert all(Decimal(row['net_usd'])==Decimal('.02') for row in data['items'])
    with factory() as db:db.add(PdvSale(total_gs=100,subtotal_gs=100));db.commit()
    data=client.get('/api/pdv/management').json()
    assert data['summary']['usd_unavailable']==1
    assert any(row['net_usd'] is None for row in data['items'])
