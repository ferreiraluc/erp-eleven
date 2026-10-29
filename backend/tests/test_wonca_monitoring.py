"""Signed provider inbox and overnight lifecycle; synthetic data, no network."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_assistant import setup
from test_customer_links import parcel
from app.database import Base, get_db
from app.config import settings
from app.models import Usuario, Rastreamento
from app.models.rastreamento import RastreamentoStatus as Status
from app.models.wonca import WoncaConfig, WoncaSubscription, WoncaEvent
from app.models.access import AuditEvent
from app.dependencies import get_current_active_user
from app.api.endpoints import wonca
from app.services import wonca_monitoring as monitor

MOMENT = datetime(2026, 10, 28, 15, tzinfo=timezone.utc)
ENDPOINT, PROFILE = str(uuid4()), str(uuid4())
SIGNING = 'synthetic-signing-secret-not-base64-decoded'
CODE = 'AA123456789BR'


@pytest.fixture
def monitoring(setup, monkeypatch):
    factory, _, uid = setup
    monkeypatch.setattr(settings, 'ASSISTANT_ENABLED', False)
    monkeypatch.setattr(settings, 'WONCA_API_KEY', 'synthetic-key')
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[m.__table__ for m in (WoncaConfig, WoncaSubscription, WoncaEvent, AuditEvent)])
        db.add(WoncaConfig(id='main', endpoint_id=ENDPOINT, profile_id=PROFILE, interval_hours=2,
            monitor_days=30, daytime_only=True, enabled=True, secret_encrypted=monitor.cipher().encrypt(SIGNING.encode()).decode()))
        db.commit()
    return factory, uid


def subscribe(db, code=CODE, moment=MOMENT, **kwargs):
    row = WoncaSubscription(code=code, endpoint_id=ENDPOINT, profile_id=PROFILE,
        remote_id=str(uuid4()), state='active', created_at=moment,
        expires_at=moment + timedelta(days=30), retry_at=moment, **kwargs)
    db.add(row); db.flush()
    return row


def signed(event_id=None, code=CODE, checked=MOMENT, signing=SIGNING, **fields):
    eid = str(event_id or uuid4())
    event = {'event_id': eid, 'type': 'tracking.updated', 'carrier': 'CARRIER_CORREIOS',
        'code': code, 'checked_at': checked.isoformat(), 'payload': {'codObjeto':code,
        'eventos': [{'data':'28/10/2026 12:00', 'descricao':'Objeto em trânsito'}]}, **fields}
    body = json.dumps(event).encode()
    stamp = str(int(MOMENT.timestamp()))
    headers = {'x-wonca-webhook-timestamp':stamp, 'x-wonca-webhook-algorithm':'hmac-sha256',
        'x-wonca-webhook-event-id':eid, 'x-wonca-webhook-delivery-id':str(uuid4()),
        'x-wonca-webhook-signature':hmac.new(signing.encode(), stamp.encode()+b'.'+body, hashlib.sha256).hexdigest()}
    return body, headers


@pytest.mark.parametrize('fault', ['secret','tamper','old','algorithm','id'])
def test_signature_and_delivery_identity_reject_untrusted_data(monitoring, fault):
    factory, _ = monitoring
    body, headers = signed(signing='wrong' if fault == 'secret' else SIGNING)
    if fault == 'tamper': body += b' '
    if fault == 'old': headers['x-wonca-webhook-timestamp'] = str(int(MOMENT.timestamp())-301)
    if fault == 'algorithm': headers['x-wonca-webhook-algorithm'] = 'sha1'
    if fault == 'id': headers['x-wonca-webhook-event-id'] = str(uuid4())
    with factory() as db:
        with pytest.raises(HTTPException) as err: monitor.receive(db, body, headers, MOMENT)
        assert err.value.status_code in (400,403)
        assert db.query(WoncaEvent).count() == 0


def test_durable_idempotent_receipt_and_atomic_processing(monitoring):
    factory, _ = monitoring
    body, headers = signed()
    with factory() as db:
        row = parcel(db, CODE); rid = row.id; subscribe(db); db.commit()
        assert monitor.receive(db, body, headers, MOMENT) == {'accepted':True}
        db.commit()
    with factory() as db:
        assert monitor.receive(db, body, headers, MOMENT)['duplicate']
        assert db.query(WoncaEvent).count() == 1
        assert monitor.process_one(db)
        db.rollback()
        assert db.query(WoncaEvent).one().status == 'pending'
        assert db.get(Rastreamento,rid).status == Status.PENDENTE
        assert monitor.process_safely(db); db.commit()
        event = db.query(WoncaEvent).one()
        assert event.status == 'processed' and event.payload is None
        assert db.get(Rastreamento,rid).status == Status.EM_TRANSITO
        assert db.get(Rastreamento,rid).historico_eventos
        assert not monitor.process_safely(db)


def test_unknown_code_and_disabled_monitoring_ack_without_processing(monitoring):
    factory, _ = monitoring
    with factory() as db:
        body, headers = signed(); monitor.receive(db,body,headers,MOMENT); db.commit()
        assert db.query(WoncaEvent).one().status == 'ignored'
        assert db.query(WoncaEvent).one().payload is None
        assert db.query(WoncaSubscription).count() == 0
        subscribe(db); db.get(WoncaConfig,'main').enabled = False; db.commit()
        body, headers = signed(); monitor.receive(db,body,headers,MOMENT); db.commit()
        assert db.query(WoncaEvent).filter_by(status='ignored').count() == 2


@pytest.mark.parametrize('reason', ['stale','delivered','archived','expired','empty'])
def test_old_or_inapplicable_event_never_regresses_tracking(monitoring, reason):
    factory, _ = monitoring
    with factory() as db:
        row = parcel(db, CODE); sub = subscribe(db)
        if reason == 'stale': row.provedor_verificado_em = MOMENT + timedelta(seconds=1)
        if reason == 'delivered': row.status = Status.ENTREGUE
        if reason == 'archived': row.ativo = False
        if reason == 'expired': sub.expires_at = MOMENT - timedelta(days=1)
        db.commit()
        body, headers = signed(**({'payload':{'eventos':[]}} if reason == 'empty' else {}))
        monitor.receive(db,body,headers,MOMENT); db.commit()
        assert monitor.process_safely(db); db.commit()
        assert db.query(WoncaEvent).one().status == 'ignored'
        assert not row.historico_eventos


def test_poison_delivery_is_bounded_and_following_event_can_progress(monitoring, monkeypatch):
    factory, _ = monitoring
    with factory() as db:
        parcel(db, CODE); subscribe(db); db.commit()
        body, headers = signed(); monitor.receive(db,body,headers,MOMENT); db.commit()
        def fail(*args): raise RuntimeError('synthetic')
        monkeypatch.setattr(monitor,'normalize_events',fail)
        for _ in range(5): assert monitor.process_safely(db); db.commit()
        event = db.query(WoncaEvent).one()
        assert event.status == 'failed' and event.attempts == 5 and event.payload is None
        assert not monitor.process_safely(db)


class Provider:
    def __init__(self): self.calls=[]; self.fail=False
    def __call__(self, method, data):
        self.calls.append((method,data))
        if self.fail: raise RuntimeError('synthetic_unavailable')
        if method.startswith('Delete'): return {}
        return {'subscriptions':[{'id':str(uuid4()),'endpointId':data['endpointId'],
            'profileId':data['profileId'],'code':item['code'],'active':True,'carrier':item['carrier']} for item in data['entries']]}


def test_day_night_boundaries_and_original_deadline_survive_resume(monitoring):
    factory, _ = monitoring; provider=Provider()
    # Brasília UTC-3: 20:59 active; 21:00 removed; 06:59 stays paused; 07:00 re-enrolled.
    with factory() as db:
        parcel(db,CODE); db.commit()
        start=MOMENT.replace(hour=23, minute=59)
        assert monitor.sync_subscriptions(db,provider,start)['added'] == 1; db.commit()
        row=db.get(WoncaSubscription,CODE); deadline=monitor.utc(row.expires_at)
        assert monitor.sync_subscriptions(db,provider,start+timedelta(seconds=60))['removed']==1; db.commit()
        assert row.state=='paused'
        assert monitor.sync_subscriptions(db,provider,start+timedelta(hours=9))=={'added':0,'removed':0}; db.commit()
        assert monitor.sync_subscriptions(db,provider,start+timedelta(hours=10,minutes=1))['added']==1; db.commit()
        assert row.state=='active' and monitor.utc(row.expires_at)==deadline
        assert [name for name,_ in provider.calls]==['UpsertTrackingSubscriptions','DeleteTrackingSubscriptions','UpsertTrackingSubscriptions']
        assert monitor.sync_subscriptions(db,provider,start+timedelta(hours=10,minutes=2))=={'added':0,'removed':0}


def test_new_shipments_wait_until_seven_and_expired_never_renew(monitoring):
    factory,_=monitoring; provider=Provider()
    with factory() as db:
        parcel(db,CODE); db.commit()
        night=MOMENT.replace(hour=4)
        monitor.sync_subscriptions(db,provider,night); db.commit()
        assert not provider.calls and not db.query(WoncaSubscription).count()
        monitor.sync_subscriptions(db,provider,MOMENT); db.commit()
        assert monitor.sync_subscriptions(db,provider,MOMENT+timedelta(days=30))['removed']==1; db.commit()
        assert db.get(WoncaSubscription,CODE).state=='expired'
        assert monitor.sync_subscriptions(db,provider,MOMENT+timedelta(days=31))=={'added':0,'removed':0}


@pytest.mark.parametrize('reason',['delivered','archived','disabled'])
def test_closed_shipments_or_disabled_config_cancel_only_owned_ids(monitoring,reason):
    factory,_=monitoring; provider=Provider()
    with factory() as db:
        row=parcel(db,CODE); db.commit()
        monitor.sync_subscriptions(db,provider,MOMENT); db.commit()
        remote=db.get(WoncaSubscription,CODE).remote_id
        if reason=='delivered': row.status=Status.ENTREGUE
        if reason=='archived': row.ativo=False
        if reason=='disabled': db.get(WoncaConfig,'main').enabled=False
        db.commit()
        assert monitor.sync_subscriptions(db,provider,MOMENT)['removed']==1; db.commit()
        assert provider.calls[-1]==('DeleteTrackingSubscriptions',{'ids':[remote]})
        assert db.get(WoncaSubscription,CODE).state=='stopped'
        monitor.sync_subscriptions(db,provider,MOMENT); assert len(provider.calls)==2


def test_cancel_failure_is_visible_and_retried_without_falsely_marking_paused(monitoring):
    factory,_=monitoring; provider=Provider()
    with factory() as db:
        parcel(db,CODE); db.commit(); monitor.sync_subscriptions(db,provider,MOMENT); db.commit()
        night=MOMENT.replace(hour=0)+timedelta(days=1); provider.fail=True
        monitor.sync_subscriptions(db,provider,night); db.commit()
        row=db.get(WoncaSubscription,CODE)
        assert row.state=='removing' and row.last_error and row.attempts==1
        monitor.sync_subscriptions(db,provider,night); assert len(provider.calls)==2
        provider.fail=False
        monitor.sync_subscriptions(db,provider,night+timedelta(minutes=2)); db.commit()
        assert row.state=='paused' and row.last_error is None


def test_unacknowledged_upsert_is_recovered_then_cancelled_at_night(monitoring):
    factory,_=monitoring; provider=Provider(); provider.fail=True
    with factory() as db:
        parcel(db,CODE); db.commit(); monitor.sync_subscriptions(db,provider,MOMENT); db.commit()
        assert db.get(WoncaSubscription,CODE).remote_id is None
        provider.fail=False
        result=monitor.sync_subscriptions(db,provider,MOMENT.replace(hour=0)+timedelta(days=1)); db.commit()
        assert result=={'added':1,'removed':1}
        assert db.get(WoncaSubscription,CODE).state=='paused'


def test_batch_is_bounded_and_ignores_delivered_archived_non_correios(monitoring):
    factory,_=monitoring; provider=Provider()
    with factory() as db:
        for i in range(101): parcel(db,f'AA{i:09d}BR')
        parcel(db,'AB999999999BR',status=Status.ENTREGUE)
        parcel(db,'AC999999999BR',ativo=False)
        parcel(db,'not-a-correios-code'); db.commit()
        assert monitor.sync_subscriptions(db,provider,MOMENT)['added']==100; db.commit()
        assert monitor.sync_subscriptions(db,provider,MOMENT)['added']==1; db.commit()
        assert db.query(WoncaSubscription).count()==101
        assert all(len(data['entries'])<=100 for _,data in provider.calls)


def client_for(factory,uid):
    app=FastAPI(); app.include_router(wonca.router,prefix='/monitor')
    def database():
        with factory() as db: yield db
    def user():
        with factory() as db: return db.get(Usuario,uid)
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_active_user]=user
    return TestClient(app)


def test_owner_config_is_encrypted_and_requires_explicit_consumption_confirmation(monitoring):
    factory,uid=monitoring; client=client_for(factory,uid)
    assert client.get('/monitor/config').status_code==403
    with factory() as db:
        db.get(Usuario,uid).email='lucas@eleven.com'
        from app.models.usuario import UsuarioRole
        db.get(Usuario,uid).role=UsuarioRole.ADMIN; db.commit()
    current=client.get('/monitor/config'); assert current.status_code==200
    assert SIGNING not in current.text and 'secret_encrypted' not in current.text
    body={'endpoint_id':ENDPOINT,'profile_id':PROFILE,'enabled':True,'daytime_only':True,'interval_hours':2}
    assert client.put('/monitor/config',json=body).status_code==422
    body['confirm_monitoring']=True
    result=client.put('/monitor/config',json=body)
    assert result.status_code==200, result.text
    assert result.json()['daytime_only'] and SIGNING not in result.text
    with factory() as db:
        encrypted=db.get(WoncaConfig,'main').secret_encrypted
        assert SIGNING not in encrypted and monitor.secret(db.get(WoncaConfig,'main'))==SIGNING
        assert SIGNING not in str([r.changes for r in db.query(AuditEvent)])


def test_webhook_bounds_and_content_type(monitoring):
    factory,uid=monitoring; client=client_for(factory,uid)
    assert client.post('/monitor/webhook',content=b'{}').status_code==415
    assert client.post('/monitor/webhook',content=b'x'*262145,headers={'content-type':'application/json'}).status_code==413
    body,headers=signed(); headers['content-type']='application/json'
    # At current wall clock this synthetic signature is expired, not accepted.
    assert client.post('/monitor/webhook',content=body,headers=headers).status_code==403
