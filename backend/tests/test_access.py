"""Access isolation and session lifecycle; all data are disposable local fixtures."""
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.config import settings
from app.models import Usuario, Vendedor, Cliente, Venda, PdvSale, PdvSaleItem, PdvPayment, PdvCliente, Pedido
from app.models.usuario import UsuarioRole
from app.models.venda import MoedaTipo, PagamentoMetodo
from app.models.access import AuthSession, AuditEvent, ActivitySpan, now
from app.models.sales_bi import SalesBIConfig, SalesBIWorkbook
from app.api.endpoints import auth, user_admin, vendas, pdv, sales_bi, dashboard
from app.services.user_sessions import get_password_hash, aware
from app.services.user_audit import bind_actor
from app.services.assistant_queries import query_sales, SalesArgs
from test_sales_bi import row


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    models = (Usuario,Vendedor,Cliente,Venda,PdvSale,PdvSaleItem,PdvPayment,PdvCliente,Pedido,
              AuthSession,AuditEvent,ActivitySpan,SalesBIWorkbook,SalesBIConfig)
    Base.metadata.create_all(engine, tables=[m.__table__ for m in models])
    factory = sessionmaker(bind=engine, autoflush=False, info={'audit_enabled':True})
    app = FastAPI()
    for prefix, module in [('auth',auth),('access',user_admin),('vendas',vendas),('pdv',pdv),('sales-bi',sales_bi),('dashboard',dashboard)]:
        app.include_router(module.router, prefix='/api/'+prefix)
    def db():
        with factory() as session: yield session
    app.dependency_overrides[get_db] = db
    auth._attempts.clear()
    password_hash = get_password_hash('test-initial')
    ids = {}
    with factory() as session:
        for name, scope in [('Lucas','all'),('Wissam','all'),('Denis','own'),('Sol','own'),('Junior','own')]:
            vendor = Vendedor(id=uuid.uuid4(),nome=name)
            user = Usuario(id=uuid.uuid4(),nome=name,email=name.lower()+'@eleven.com',senha_hash=password_hash,
                           role=UsuarioRole.ADMIN if name=='Lucas' else UsuarioRole.GERENTE,
                           sales_scope=scope,sales_seller=name,vendedor_id=vendor.id,ativo=True)
            session.add_all([vendor,user]);ids[name]=(user.id,vendor.id)
        session.commit()
    yield TestClient(app), factory, ids
    engine.dispose()


def login(client, name='Lucas', password='test-initial'):
    response = client.post('/api/auth/login', json={'email':name+'@eleven.com','senha':password})
    assert response.status_code == 200, response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_login_cannot_trust_old_token_or_cached_role(setup):
    client,factory,ids=setup
    assert client.get('/api/auth/me').status_code==401
    old=jwt.encode({'sub':'lucas@eleven.com','exp':now()+timedelta(days=1)},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+old}).status_code==401
    headers=login(client,'LUCAS')
    me=client.get('/api/auth/me',headers=headers).json()
    assert me['email']=='lucas@eleven.com' and me['sales_scope']=='all' and 'senha_hash' not in me
    with factory() as db:
        user=db.get(Usuario,ids['Lucas'][0]);user.ativo=False;db.commit()
    assert client.get('/api/auth/me',headers=headers).status_code==401


def test_first_password_change_revokes_every_previous_session(setup):
    client,factory,ids=setup
    with factory() as db:
        db.get(Usuario,ids['Junior'][0]).must_change_password=True;db.commit()
    first,second=login(client,'Junior'),login(client,'Junior')
    assert client.get('/api/sales-bi/overview',headers=first).status_code==403
    assert client.get('/api/auth/me',headers=first).json()['must_change_password'] is True
    assert client.post('/api/auth/password',headers=first,json={'current_password':'wrong','new_password':'test-new-pass'}).status_code==400
    changed=client.post('/api/auth/password',headers=first,json={'current_password':'test-initial','new_password':'test-new-pass'})
    assert changed.status_code==200,changed.text
    for headers in [first,second]: assert client.get('/api/auth/me',headers=headers).status_code==401
    current={'Authorization':'Bearer '+changed.json()['access_token']}
    assert client.get('/api/auth/me',headers=current).json()['must_change_password'] is False
    assert client.post('/api/auth/logout',headers=current).status_code==200
    assert client.get('/api/auth/me',headers=current).status_code==401
    assert client.post('/api/auth/login',json={'email':'junior@eleven.com','senha':'test-initial'}).status_code==401
    login(client,'Junior','test-new-pass')


def test_expired_database_session_even_when_jwt_not_expired(setup):
    client,factory,_=setup;headers=login(client)
    with factory() as db:
        db.query(AuthSession).one().expires_at=now()-timedelta(seconds=1);db.commit()
    assert client.get('/api/auth/me',headers=headers).status_code==401


@pytest.mark.parametrize('name',['Wissam','Denis','Sol','Junior'])
def test_admin_audit_and_accounts_are_exclusive_to_lucas(setup,name):
    client,factory,ids=setup;headers=login(client,name)
    for path in ['/api/access/audit','/api/access/users']:
        assert client.get(path,headers=headers).status_code==403
    assert client.post('/api/access/users/'+str(ids['Lucas'][0])+'/reset-password',headers=headers,json={'password':'other-pass'}).status_code==403
    with factory() as db:
        db.get(Usuario,ids[name][0]).role=UsuarioRole.ADMIN;db.commit()
    assert client.get('/api/access/audit',headers=headers).status_code==401


def test_owner_can_create_reset_and_restrict_account_but_not_remove_self(setup):
    client,factory,ids=setup;owner=login(client);staff=login(client,'Denis')
    body={'nome':'Novo','email':'novo@eleven.com','password':'temporary-test','ativo':True,'sales_scope':'own','sales_seller':'Denis','vendedor_id':str(ids['Denis'][1])}
    created=client.post('/api/access/users',headers=owner,json=body)
    assert created.status_code==201,created.text
    assert created.json()['role']=='GERENTE' and created.json()['must_change_password']
    assert client.post('/api/access/users',headers=owner,json=body).status_code==409
    assert client.post('/api/access/users/'+str(ids['Denis'][0])+'/reset-password',headers=owner,json={'password':'new-temporary'}).status_code==200
    assert client.get('/api/auth/me',headers=staff).status_code==401
    body={k:v for k,v in body.items() if k not in ('password','email')};body['ativo']=False
    assert client.put('/api/access/users/'+str(ids['Lucas'][0]),headers=owner,json=body).status_code==400
    assert client.get('/api/access/users',headers=owner).status_code==200


def test_financial_scopes_apply_before_bi_aggregation_and_ignore_forged_seller(setup):
    client,factory,ids=setup
    with factory() as db:
        db.add(row('september',kind='archive'));db.add(row('old-september',kind='archive',year=2025));db.commit()
    staff=login(client,'Junior')
    data=client.get('/api/sales-bi/overview?seller=Lucas',headers=staff).json()
    assert data['selected']['total_usd']==600
    assert data['sellers']==['Junior'] and [r['name'] for r in data['ranking']]==['Junior']
    assert all(w['total_usd'] in [100,200] for w in data['weeks'])
    assert data['access']=={'scope':'own','seller':'Junior'} and data['coverage']['warnings']==0
    assert 'Lucas' not in json.dumps(data)
    assert client.get('/api/sales-bi/sources',headers=staff).json()['sources']==[]
    assert client.get('/api/sales-bi/config',headers=staff).status_code==403
    manager=client.get('/api/sales-bi/overview',headers=login(client,'Wissam')).json()
    assert manager['selected']['total_usd']==2000 and len(manager['ranking'])==2
    with factory() as db:
        db.get(Usuario,ids['Junior'][0]).sales_seller=None;db.commit()
    assert client.get('/api/sales-bi/overview',headers=staff).status_code==403


def test_operational_sales_pdv_and_bot_cannot_leak_another_seller(setup):
    client,factory,ids=setup
    with factory() as db:
        for name,amount in [('Junior',100),('Lucas',900)]:
            db.add(Venda(vendedor_id=ids[name][1],moeda=MoedaTipo.U_DOLLAR,valor_bruto=amount,valor_liquido=amount,metodo_pagamento=PagamentoMetodo.PIX_POWER))
            db.add(PdvSale(vendedor_id=ids[name][0],total_gs=amount,status='completed'))
        db.add(PdvCliente(nome='Cliente fixture',saldo_fiado_gs=123456));db.commit()
        other_sale=db.query(Venda).filter_by(vendedor_id=ids['Lucas'][1]).one().id
        other_pdv=db.query(PdvSale).filter_by(vendedor_id=ids['Lucas'][0]).one().id
        bot=query_sales(db,SalesArgs(),ids['Junior'][0])
        assert len(bot['vendas']['resultados'])==1 and bot['vendas']['resultados'][0]['vendedor']=='Junior'
        assert float(bot['pdv']['valor_total_gs'])==100
    headers=login(client,'Junior')
    assert len(client.get('/api/vendas/',headers=headers).json())==1
    assert client.get('/api/vendas/'+str(other_sale),headers=headers).status_code==404
    assert len(client.get('/api/pdv/sales',headers=headers).json())==1
    assert client.get('/api/pdv/sales/'+str(other_pdv),headers=headers).status_code==404
    assert client.post('/api/pdv/sales/'+str(other_pdv)+'/cancel',headers=headers).status_code==404
    assert client.get('/api/pdv/clients',headers=headers).json()[0]['saldo_fiado_gs'] is None
    assert client.get('/api/dashboard/stats',headers=headers).json()['totalVendas']==100
    assert [r['nome'] for r in client.get('/api/dashboard/vendedores-performance',headers=headers).json()]==['Junior']
    denied={'moeda':'U$','valor_bruto':10,'vendedor_id':str(ids['Lucas'][1]),'metodo_pagamento':'PIX_POWER'}
    assert client.post('/api/vendas/',headers=headers,json=denied).status_code==404


def test_audit_only_committed_mutations_and_no_private_values(setup):
    client,factory,ids=setup
    with factory() as db:
        bind_actor(db,db.get(Usuario,ids['Lucas'][0]),source='telegram')
        customer=Cliente(nome='Private customer',cpf='111.222.333-44',endereco='Private address')
        db.add(customer);db.flush();db.rollback()
        assert db.query(AuditEvent).count()==0
        customer=Cliente(nome='Private customer',cpf='111.222.333-44',endereco='Private address')
        db.add(customer);db.commit()
        db.query(Cliente).filter_by(id=customer.id).update({'ativo':False});db.commit()
        events=db.query(AuditEvent).all()
        assert {e.action for e in events}=={'create','bulk_update'}
        assert all(e.user_id==ids['Lucas'][0] and e.source=='telegram' for e in events)
        encoded=json.dumps([e.changes for e in events]);assert '111.222' not in encoded and 'Private' not in encoded
    data=client.get('/api/access/audit',headers=login(client)).json()
    assert any(e['entity']=='clientes' for e in data['events'])
    assert 'senha_hash' not in json.dumps(data) and 'test-initial' not in json.dumps(data)


def test_cached_clients_no_longer_record_navigation_activity(setup):
    client,factory,ids=setup;headers=login(client,'Junior')
    with factory() as db: before=db.query(AuditEvent).count()
    body={'id':str(uuid.uuid4()),'module':'inventory','sequence':0,'seconds':30}
    for sequence in range(3):
        body['sequence']=sequence
        assert client.post('/api/access/activity',headers=headers,json=body).json()=={'active_seconds':0,'tracking_enabled':False}
    with factory() as db:
        assert db.query(ActivitySpan).count()==0
        assert db.query(AuditEvent).count()==before
        assert 'login' in {row.action for row in db.query(AuditEvent)}
    body['seconds']=10000;assert client.post('/api/access/activity',headers=headers,json=body).status_code==422


def test_login_is_one_event_without_a_duplicate_profile_timestamp_update(setup):
    client,factory,_=setup
    login(client)
    with factory() as db: assert [row.action for row in db.query(AuditEvent)]==['login']


def test_audit_hides_historical_reads_without_deleting_them(setup):
    client,factory,ids=setup;headers=login(client)
    with factory() as db:
        before=db.query(AuditEvent).count()
        for action in ('read','request','create','item_permanently_deleted'):
            db.add(AuditEvent(user_id=ids['Lucas'][0],actor_name='Lucas',source='web',action=action,module='inventory',changes={}))
        db.commit()
    result=client.get('/api/access/audit',headers=headers).json()
    assert {'login','create','item_permanently_deleted'} <= {row['action'] for row in result['events']}
    assert not {'read','request'} & {row['action'] for row in result['events']}
    assert result['total']==before+2 and result['modules']==[] and result['active_seconds']==0
    assert not {'read','request'} & set(result['users'][0]['actions'])
    assert client.get('/api/access/audit?action=read',headers=headers).json()['total']==0
    with factory() as db: assert db.query(AuditEvent).count()==before+4


def test_http_queries_do_not_add_audit_events_but_login_and_mutations_do(setup,monkeypatch):
    from app.main import log_requests
    client,factory,ids=setup
    client.app.middleware('http')(log_requests)
    headers=login(client)
    with factory() as db: before=db.query(AuditEvent).count()
    for _ in range(3):
        assert client.get('/api/access/users',headers=headers).status_code==200
        assert client.get('/api/access/audit',headers=headers).status_code==200
    with factory() as db: assert db.query(AuditEvent).count()==before
    changed=client.put('/api/access/users/'+str(ids['Denis'][0]),headers=headers,
        json={'nome':'Denis Teste','ativo':True,'sales_scope':'own','sales_seller':'Denis','vendedor_id':str(ids['Denis'][1])})
    assert changed.status_code==200,changed.text
    with factory() as db:
        actions={row.action for row in db.query(AuditEvent)}
        assert 'access_changed' in actions and 'update' in actions and not {'read','request'} & actions



def test_provisioning_preserves_user_ids_bot_links_and_personal_password_on_rerun(setup):
    from app.user_access_setup import EMPLOYEES, provision
    from app.services.user_sessions import verify_password
    _,factory,ids=setup
    with factory() as db:
        for name,email,scope,aliases,legacy in EMPLOYEES:
            db.get(Usuario,ids[name][0]).email=legacy[0]
        db.commit()
        result=provision(db,'first-time-password');db.commit()
        assert len(result)==5 and all(r['initial_password'] for r in result)
        for name,(_,vendor_id) in ids.items():
            user=db.get(Usuario,ids[name][0])
            assert user.email==name.lower()+'@eleven.com' and user.must_change_password
            assert db.get(Vendedor,vendor_id).usuario_id==user.id
            assert verify_password('first-time-password',user.senha_hash)
        junior=db.get(Usuario,ids['Junior'][0]);junior.senha_hash=get_password_hash('private-new-pass');junior.must_change_password=False;db.commit()
        version=junior.auth_version
        result=provision(db,'never-applied-password');db.commit()
        assert all(not r['initial_password'] for r in result)
        assert verify_password('private-new-pass',junior.senha_hash) and not junior.must_change_password
        assert junior.auth_version==version


def test_owner_can_list_historical_internal_bot_accounts_without_serialization_error(setup):
    client,factory,_=setup
    with factory() as db:
        db.add(Usuario(nome='Identidade antiga',email='legacy@assistant.invalid',senha_hash='unused',ativo=False))
        db.commit()
    response=client.get('/api/access/users',headers=login(client))
    assert response.status_code==200,response.text
    assert any(u['email']=='legacy@assistant.invalid' and not u['ativo'] for u in response.json())
