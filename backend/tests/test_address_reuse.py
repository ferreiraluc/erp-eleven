"""Repeated packages share one address, while historical operations remain independent."""
import copy
import importlib.util
import uuid
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError
from test_address_manager import env
from test_assistant import setup, incoming
from app.models.address_book import SavedAddress, FreightOrder
from app.models.printing import PrintJob
from app.models.assistant import AssistantIdentity, AssistantAction, utcnow
from app.services import superfrete as sf, assistant_freight as bot
from app.services.address_identity import fingerprint
from app.services.address_book import resolve_address

BASE={'pais':'BR','nome':'Izabela Lima da Silva','cpf':'12345678909','endereco':'Rua Teste','numero':'25','bairro':'José Bonifácio','complemento':'Ap 12','cidade':'São Paulo','estado':'SP','cep':'08250-520'}


def create(client,data=None,label='Casa'):
    result=client.post('/manager/addresses',json={'label':label,'data':data or BASE})
    assert result.status_code==200,result.text
    return result.json()


def test_normalized_identity_recipient_location_and_blank_blocks():
    equivalent={**BASE,'nome':' IZABELA   LIMA DA SILVA ','cidade':'sao paulo','bairro':'Jose Bonifacio','cep':'08250520'}
    assert fingerprint(BASE)==fingerprint(equivalent)
    for change in ({'nome':'Outro cliente'},{'numero':'26'},{'complemento':'Ap 13'},{'pais':'PY'},{'cidade':'Outra cidade'}):
        assert fingerprint(BASE)!=fingerprint(BASE|change)
    assert fingerprint({'pais':'PY','nome':'João'}) is None
    assert fingerprint({'pais':'PY'}) is None
    assert fingerprint({'pais':'PY','nome':'João','telefone':'(099) 123-456','cidade':'Asunción'})==fingerprint({'pais':'PY','nome':'Joao','telefone':'099123456','cidade':'Asuncion'})


def test_create_reuses_normalized_address_and_preserves_customer_link(env):
    factory,c,uid,_=env
    first=create(c)
    second=create(c,{**BASE,'bairro':'Jose Bonifacio','cidade':'sao paulo','cep':'08250520'},label='Repetido')
    assert second['id']==first['id'] and second['reused']
    assert c.get('/manager/addresses').json()['total']==1
    assert c.get('/manager/overview').json()['addresses']==1
    assert create(c,BASE|{'complemento':'Ap 13'})['id']!=first['id']
    assert create(c,BASE|{'nome':'Outro cliente'})['id']!=first['id']
    bad=c.post('/manager/addresses',json={'label':'Conflito','data':BASE|{'cpf':'98765432100'}})
    assert bad.status_code==409


def test_ten_bot_quotes_one_address_and_separate_usage_records(env,monkeypatch):
    factory,c,uid,_=env
    calls=[]
    def quote_only(method,path,body):
        assert path=='calculator';calls.append(path)
        return [{'id':1,'name':'PAC','price':20}]
    monkeypatch.setattr(sf,'call',quote_only)
    args={'endereco':BASE,'remetente':BASE,'package':{'weight':1,'height':15,'width':20,'length':15},'products':[{'name':'Camiseta','quantity':1,'unitary_value':50}],'non_commercial':True}
    with factory() as db:
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        for day in range(10):
            message=incoming(db,uid,'Cote este pacote',channel='telegram')
            data=copy.deepcopy(args)
            if day%2:data['endereco'].update(cidade='Sao Paulo',bairro='Jose Bonifacio',cep='08250520')
            output=bot.execute(db,message,identity,'cotar_superfrete',data)
            assert output['state']=='quoted'
            assert bot.execute(db,message,identity,'cotar_superfrete',data)['id']==output['id']
        address=db.query(SavedAddress).one();key=address.id
        assert db.query(FreightOrder).count()==10
        order=db.query(FreightOrder).first();order.state='released';order.tracking='TEST123'
        db.commit()
    assert len(calls)==10
    history=c.get(f'/manager/addresses/{key}/usage').json()
    assert history['total']==10 and history['summary']['quotes']==10 and history['summary']['labels']==1
    assert all(row['recipient']==BASE['nome'] for row in history['items'])
    assert c.get(f'/manager/addresses/{key}/usage?offset=8&limit=2').json()['total']==10
    assert len(c.get(f'/manager/addresses/{key}/usage?offset=8&limit=2').json()['items'])==2
    assert c.get(f'/manager/addresses/{key}/usage?kind=impressao').json()['total']==0


def test_print_usage_repeat_is_idempotent_and_edit_preserves_snapshot(env):
    factory,c,uid,did=env
    address=create(c,{'pais':'PY','nome':'Juan','cidade':'Asunción','telefone':'123'})
    payload={'request_key':str(uuid.uuid4()),'address_id':address['id'],'device_id':did,'data':address['data']}
    for _ in range(3):
        job=c.post('/manager/print',json=payload);assert job.status_code==200,job.text
        assert c.post('/manager/print',json=payload).json()['id']==job.json()['id']
        payload['request_key']=str(uuid.uuid4())
    assert c.get('/manager/addresses').json()['total']==1
    usage=c.get('/manager/addresses/'+address['id']+'/usage').json()
    assert usage['summary']['prints']==3
    body={k:address[k] for k in ['label','data','version','cliente_id','pdv_cliente_id','active']}
    body['data']={**body['data'],'cidade':'Encarnación'}
    assert c.put('/manager/addresses/'+address['id'],json=body).status_code==200
    historic=c.get('/manager/addresses/'+address['id']+'/usage').json()
    assert all('Asunción' in row['address_text'] for row in historic['items'])


def test_edited_duplicate_is_redirected_and_history_stays_accessible(env):
    factory,c,uid,did=env
    original=create(c,{'pais':'PY','nome':'Juan','cidade':'Asunción','telefone':'123'})
    another=create(c,{'pais':'PY','nome':'Juan','cidade':'Encarnación','telefone':'123'})
    payload={'request_key':str(uuid.uuid4()),'address_id':original['id'],'device_id':did,'data':original['data']}
    assert c.post('/manager/print',json=payload).status_code==200
    body={k:original[k] for k in ['label','version','cliente_id','pdv_cliente_id','active']};body['data']=another['data']
    result=c.put('/manager/addresses/'+original['id'],json=body)
    assert result.status_code==200 and result.json()['id']==another['id']
    assert c.get('/manager/addresses').json()['total']==1
    assert c.get('/manager/addresses?active=false').json()['total']==0
    assert c.get('/manager/addresses/'+another['id']+'/usage').json()['summary']['prints']==1
    assert c.get('/manager/addresses/'+original['id']+'/usage').json()['summary']['prints']==1
    assert c.put('/manager/addresses/'+original['id'],json=body).status_code==409


def test_database_rejects_uncontrolled_duplicate_insert(env):
    factory,c,uid,_=env
    create(c)
    with factory() as db:
        db.add(SavedAddress(label='Duplicado',data=BASE,created_by=uid))
        with pytest.raises(IntegrityError):db.flush()
        db.rollback()


def test_migration_consolidates_eight_variants_without_deleting_history(env):
    factory,c,uid,did=env
    path=Path(__file__).parents[1]/'alembic/versions/t0u1v2w3x4y5_unique_addresses.py'
    spec=importlib.util.spec_from_file_location('address_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    ids=[];freights=[]
    with factory() as db:
        for index in range(8):
            key=uuid.uuid4();ids.append(key)
            data={**BASE,'cidade':'Sao Paulo' if index%2 else 'São Paulo','cep':'08250520' if index%3 else '08250-520'}
            # Old rows have no identity key yet. Core insert bypasses ORM listeners.
            db.execute(insert(SavedAddress.__table__).values(id=key,label=BASE['nome'],data=data,created_by=uid,active=True,version=1,updated_at=utcnow()+timedelta(seconds=index)))
            row=FreightOrder(request_key=uuid.uuid4(),user_id=uid,address_id=key,environment='sandbox',state='quoted',rates=[],payload={'to':{'name':BASE['nome'],'city':data['cidade']},'_request':{'address_id':str(key)}})
            db.add(row);db.flush();freights.append((row.id,copy.deepcopy(row.payload)))
        migration.consolidate(db.connection());db.expire_all()
        assert db.query(SavedAddress).count()==8
        assert db.query(SavedAddress).filter_by(active=True,merged_into_id=None).count()==1
        target=resolve_address(db,ids[0]);assert target.id==ids[-1]
        for key,snapshot in freights:
            assert db.get(FreightOrder,key).payload==snapshot
        db.commit()
    assert c.get('/manager/addresses').json()['total']==1
    assert c.get(f'/manager/addresses/{ids[-1]}/usage').json()['total']==8
    assert c.get(f'/manager/addresses/{ids[0]}/usage').json()['total']==8


def test_history_requires_manager_authentication():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.endpoints.address_manager import router
    app=FastAPI();app.include_router(router,prefix='/manager')
    assert TestClient(app).get('/manager/addresses/'+str(uuid.uuid4())+'/usage').status_code in (401,403)
