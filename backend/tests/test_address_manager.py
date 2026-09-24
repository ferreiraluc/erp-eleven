import uuid
from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base,get_db
from app.models.address_book import SavedAddress,PrintLayout,FreightOrder,FreightWebhook
from app.models.printing import PrintDevice,PrintJob,PrintSender
from app.models.usuario import Usuario,UsuarioRole
from app.models.cliente import Cliente
from app.api.endpoints import address_manager as api,freight
from app.services import superfrete as sf
from test_assistant import setup


@pytest.fixture
def env(setup):
    factory,_,uid=setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(),tables=[m.__table__ for m in [SavedAddress,PrintLayout,PrintDevice,PrintJob,PrintSender,FreightOrder,FreightWebhook]])
        user=db.get(Usuario,uid);user.role=UsuarioRole.ADMIN
        device=PrintDevice(name='Teste',token_hash='x'*64)
        db.add(device);db.flush();did=str(device.id);db.commit()
    app=FastAPI();app.include_router(api.router,prefix='/manager');app.include_router(freight.router,prefix='/freight')
    def session():
        with factory() as db:yield db
    def user():
        with factory() as db:return db.get(Usuario,uid)
    app.dependency_overrides[get_db]=session;app.dependency_overrides[api.manager]=user
    return factory,TestClient(app),uid,did


def test_addresses_customer_link_version_and_history(env):
    factory,c,uid,did=env
    with factory() as db:
        customer=Cliente(nome='Teste',telefone='123');db.add(customer);db.commit();cid=str(customer.id)
    payload={'label':'Casa teste','data':{'pais':'PY','nome':'Cliente Teste','cidade':'Asunción','telefone':'123'},'cliente_id':cid}
    r=c.post('/manager/addresses',json=payload);assert r.status_code==200,r.text
    address=r.json();assert c.get('/manager/addresses',params={'customer_id':cid}).json()['total']==1
    body={**payload,'version':address['version'],'label':'Novo nome'}
    assert c.put('/manager/addresses/'+address['id'],json=body).status_code==200
    assert c.put('/manager/addresses/'+address['id'],json=body).status_code==409
    printing={'request_key':str(uuid.uuid4()),'device_id':did,'address_id':address['id'],'data':payload['data']}
    assert c.post('/manager/preview',json=printing).content.startswith(b'%PDF-')
    job=c.post('/manager/print',json=printing);assert job.status_code==200,job.text
    assert c.post('/manager/print',json=printing).json()['id']==job.json()['id']
    assert c.post('/manager/print',json={**printing,'data':{**payload['data'],'nome':'Outro'}}).status_code==409
    jid=job.json()['id']
    with factory() as db:
        j=db.get(PrintJob,uuid.UUID(jid));j.pdf=b'';j.status='submitted';db.commit()
    assert c.get('/manager/history/'+jid+'/pdf').content.startswith(b'%PDF-')
    assert c.post('/manager/history/'+jid+'/cancel').status_code==409
    assert c.get('/manager/history').json()['items'][0]['recipient']=='Cliente Teste'


def test_layout_sender_and_anonymous():
    app=FastAPI();app.include_router(api.router,prefix='/manager')
    with TestClient(app) as c:
        for path in ['/addresses','/history','/senders','/layouts']:assert c.get('/manager'+path).status_code in (401,403)


def sf_order(factory,uid,state='quoted'):
    with factory() as db:
        order=FreightOrder(request_key=uuid.uuid4(),user_id=uid,environment=sf.environment(),state=state,
            payload={'to':{'name':'Cliente Teste'},'from':{'city':'Teste'}},rates=[{'id':1,'price':20,'name':'PAC'}])
        db.add(order);db.commit();return order.id


def test_checkout_requires_exact_price_and_never_retries_uncertain(env,monkeypatch):
    factory,c,uid,did=env
    key=sf_order(factory,uid)
    calls=[]
    def provider(method,path,body):
        calls.append(path)
        if path=='cart':return {'id':'provider-test','price':21,'status':'pending'}
        raise sf.HTTPException(502,'timeout')
    monkeypatch.setattr(sf,'call',provider)
    assert c.post(f'/freight/orders/{key}/cart',json={'service':1}).json()['state']=='pending'
    assert c.post(f'/freight/orders/{key}/cart',json={'service':1}).json()['state']=='pending'
    assert calls==['cart']
    assert c.post(f'/freight/orders/{key}/pay',json={'expected_price':'20.00'}).status_code==409
    assert c.post(f'/freight/orders/{key}/pay',json={'expected_price':'21.00'}).json()['state']=='uncertain'
    assert c.post(f'/freight/orders/{key}/pay',json={'expected_price':'21.00'}).status_code==409
    assert calls==['cart','checkout']


def test_safe_label_and_document_validation():
    assert sf.safe_label('https://evil.example/a.pdf') is None
    assert sf.safe_label('http://api.superfrete.com/x') is None
    assert sf.safe_label('https://sandbox.superfrete.com/_etiqueta/pdf/test')
    with pytest.raises(sf.HTTPException):sf.party({'pais':'PY'})


def test_bot_paid_pdf_delivered_and_printed_automatically(env,monkeypatch):
    from app.services import assistant_freight as bot
    from app.services.assistant_schedule import confirm_action
    from app.models.assistant import AssistantIdentity,AssistantAction
    from app.services.assistant_replies import DocumentReply
    from test_assistant import incoming
    factory,c,uid,did=env
    monkeypatch.setattr(bot,'SessionLocal',factory)
    monkeypatch.setattr(sf,'sync_tracking',lambda db,row:None)
    key=sf_order(factory,uid,'pending')
    with factory() as db:
        f=db.get(FreightOrder,key);f.provider_id='provider-test';f.price=Decimal('20.00');db.commit()
    calls=[]
    def provider(method,path,body=None):
        calls.append(path)
        if path=='checkout':return {'success':True,'purchase':{'orders':[{'id':'provider-test','tracking':'TEST123','print':{'url':'https://sandbox.superfrete.com/_etiqueta/pdf/test'}}]}}
        if path.startswith('order/info'):return {'id':'provider-test','status':'released','tracking':'TEST123'}
        if path=='tag/print':return {'url':'https://sandbox.superfrete.com/_etiqueta/pdf/test'}
        raise AssertionError(path)
    monkeypatch.setattr(sf,'call',provider)
    monkeypatch.setattr(sf,'label_pdf',lambda url:b'%PDF-1.4\nmock')
    with factory() as db:
        source=incoming(db,uid,'Emitir etiqueta',channel='telegram')
        action=AssistantAction(source_message_id=source.id,user_id=uid,kind='frete_emitir',payload={'freight_id':str(key),'price':'20.00','recipient':'Teste','environment':sf.environment(),'service_name':'PAC'})
        db.add(action);db.commit();aid=action.id
    with factory() as db:
        action=db.get(AssistantAction,aid)
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        message=incoming(db,uid,'confirmo',channel='telegram');db.commit()
        response=confirm_action(db,message,identity,action)
        assert 'automaticamente' in response
        assert db.query(PrintJob).count()==0
        assert db.query(AssistantAction).filter_by(kind='frete_imprimir').count()==0
        db.commit()
    from app.services import freight_labels
    from app.models.assistant import utcnow,AssistantDelivery
    monkeypatch.setattr(freight_labels,'SessionLocal',factory)
    with factory() as db:
        db.get(FreightOrder,key).label_check_at=utcnow();db.commit()
    assert freight_labels.process_label()
    assert not freight_labels.process_label()
    with factory() as db:
        assert db.query(PrintJob).count()==1
        assert db.query(AssistantDelivery).one().document_pdf.startswith(b'%PDF-')
        assert db.get(FreightOrder,key).print_job_id
    assert calls.count('checkout')==1


def test_layout_optimistic_version_and_telegram_document(env,monkeypatch):
    from types import SimpleNamespace
    from app.services import assistant_channels as channel
    from app.schemas.address_book import LayoutConfig
    factory,c,uid,did=env
    body={'name':'Teste','config':LayoutConfig().model_dump(),'version':0}
    assert c.put('/manager/layouts/py',json=body).status_code==200
    assert c.put('/manager/layouts/py',json=body).status_code==409
    body['version']=1;body['config']['title']='ENTREGA'
    assert c.put('/manager/layouts/py',json=body).status_code==200
    sent=[]
    monkeypatch.setattr(channel,'enabled_channels',lambda:{'telegram'})
    monkeypatch.setattr(channel.settings,'TELEGRAM_BOT_TOKEN','test-token')
    monkeypatch.setattr(channel.settings,'TELEGRAM_GROUP_ID','-123')
    def send(url,**kwargs):
        sent.append((url,kwargs['json']))
        return SimpleNamespace(status_code=200,json=lambda:{'ok':True,'result':{'message_id':9}})
    monkeypatch.setattr(channel.requests,'post',send)
    delivery=SimpleNamespace(channel='telegram',destination='-123:4',text='Confira antes de imprimir.',document_url='https://sandbox.superfrete.com/_etiqueta/pdf/test')
    assert channel.send_delivery(delivery)=='9'
    assert sent[0][0].endswith('/sendDocument')
    assert sent[0][1]['document']==delivery.document_url
    assert sent[0][1]['message_thread_id']==4


def test_bot_quotes_with_sender_in_message_without_sender_registration(env,monkeypatch):
    from app.services import assistant_freight as bot
    from app.models.assistant import AssistantIdentity
    from test_assistant import incoming
    factory,c,uid,did=env
    calls=[]
    def provider(method,path,body=None):
        calls.append((path,body))
        return [{'id':1,'name':'PAC','price':20,'delivery_time':5}]
    monkeypatch.setattr(sf,'call',provider)
    address={'pais':'BR','nome':'Cliente Teste','endereco':'Rua Teste','numero':'10','bairro':'Centro','cidade':'São Paulo','estado':'SP','cep':'01001000','cpf':'12345678909'}
    sender={**address,'nome':'Remetente da conversa','cep':'85865010','cidade':'Foz do Iguaçu','estado':'PR'}
    with factory() as db:
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        message=incoming(db,uid,'Cotar com remetente enviado e declaração não comercial',channel='telegram')
        args={'endereco':address,'remetente':sender,'package':{'weight':0.3,'height':5,'width':15,'length':20},'products':[{'name':'Camiseta','quantity':5,'unitary_value':'50.00'}],'non_commercial':True}
        result=bot.execute(db,message,identity,'cotar_superfrete',args)
        assert result.get('state')=='quoted',result
        order=db.get(FreightOrder,uuid.UUID(result['id']))
        assert order.payload['from']['name']=='Remetente da conversa'
        assert order.payload['products'][0]['quantity']==5
        assert order.payload['options']['non_commercial'] is True
        assert db.query(PrintSender).count()==0
        assert bot.execute(db,message,identity,'cotar_superfrete',args)['id']==result['id']
        assert [p for p,_ in calls]==['calculator']
        assert calls[0][1]['from']['postal_code']=='85865010'
        assert db.query(PrintJob).count()==0


def test_sender_missing_fields_are_specific():
    with pytest.raises(sf.HTTPException) as exc:
        sf.party({'pais':'BR','nome':'Teste','endereco':'Rua teste','cidade':'Foz do Iguaçu','estado':'PR','cep':'85865010'})
    assert exc.value.detail=='Complete no remetente: bairro.'


def test_legacy_print_sender_is_same_freight_address(env,monkeypatch):
    from app.services.sender_addresses import sender_address
    factory,c,uid,did=env
    with factory() as db:
        sender=PrintSender(id='legacy',name='Remetente Teste',lines=['Rua Exemplo, 330','Centro','Foz do Iguaçu - PR','CEP 85865-310','CPF: 123.456.789-09'])
        db.add(sender);db.commit()
        data=sender_address(sender)
        assert data['bairro']=='Centro' and data['numero']=='330'
        assert data['cep']=='85865310'
    address=c.post('/manager/addresses',json={'label':'Destino','data':{**data,'nome':'Cliente'}}).json()
    calls=[]
    monkeypatch.setattr(sf,'call',lambda method,path,body:(calls.append(body) or [{'id':1,'price':20,'name':'PAC'}]))
    payload={'request_key':str(uuid.uuid4()),'address_id':address['id'],'sender_id':'legacy','package':{'weight':1,'height':15,'width':20,'length':15},'products':[{'name':'Camiseta','quantity':5,'unitary_value':50}],'non_commercial':True}
    r=c.post('/freight/quotes',json=payload)
    assert r.status_code==200,r.text
    assert calls[0]['from']['postal_code']=='85865310'
    assert c.get('/manager/senders').json()[0]['data']['bairro']=='Centro'
    with factory() as db:
        f=db.get(FreightOrder,uuid.UUID(r.json()['id']))
        assert f.payload['from']['address']=='Rua Exemplo'
        assert f.payload['from']['district']=='Centro'
    # A conversational complement overrides only the supplied field.
    payload['request_key']=str(uuid.uuid4());payload['remetente']={'bairro':'Porto Meira'}
    r=c.post('/freight/quotes',json=payload);assert r.status_code==200,r.text
    with factory() as db:
        f=db.get(FreightOrder,uuid.UUID(r.json()['id']))
        assert f.payload['from']['district']=='Porto Meira'
        assert f.payload['from']['postal_code']=='85865310'


def test_agent_quote_serializes_dates_and_retains_failed_user_details(env,monkeypatch):
    import json
    from app.services import assistant_agent as agent
    from app.models.assistant import AssistantIdentity
    from test_assistant import incoming
    factory,c,uid,did=env
    address={'pais':'BR','nome':'Teste','endereco':'Rua Teste','numero':'10','bairro':'Centro','cidade':'São Paulo','estado':'SP','cep':'01001000','cpf':'12345678909'}
    args={'endereco':address,'remetente':address,'package':{'weight':1,'height':15,'width':20,'length':15},'products':[{'name':'Camiseta','quantity':5,'unitary_value':50}],'non_commercial':True}
    monkeypatch.setattr(sf,'call',lambda *a,**kw:[{'id':1,'name':'PAC','price':20}])
    seen=[]
    def complete(messages,**kwargs):
        if not seen:
            assert kwargs['tool_choice']['function']['name']=='consultar_enderecos'
            assert not any('frete não configurado' in (m.get('content') or '') for m in messages)
            assert any('Bairro Porto Meira' in m.get('content','') for m in messages)
            seen.append(True)
            return {'tool_calls':[{'id':'quote','type':'function','function':{'name':'cotar_superfrete','arguments':json.dumps(args)}}]}
        output=json.loads(messages[-1]['content'])
        assert output['state']=='quoted'
        assert isinstance(output['created_at'],str)
        return {'content':'PAC R$ 20. Escolha o serviço.'}
    monkeypatch.setattr(agent,'complete',complete)
    with factory() as db:
        stale=incoming(db,uid,'Use o remetente salvo',channel='telegram');stale.status='done';stale.response='O remetente está com frete não configurado no gestor.';db.flush()
        previous=incoming(db,uid,'Bairro Porto Meira',channel='telegram');previous.status='failed';db.flush()
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        msg=incoming(db,uid,'Cote a etiqueta com os dados enviados',channel='telegram')
        answer=agent.respond(db,msg,identity)
        assert 'PAC' in answer
        assert db.query(FreightOrder).count()==1
        assert db.query(PrintJob).count()==0


def test_legacy_sender_parsing_does_not_turn_name_or_phone_into_district():
    from types import SimpleNamespace
    from app.services.sender_addresses import sender_address,sender_lines
    profile=SimpleNamespace(name='Nome completo',data=None,lines=['Nome curto','Rua Exemplo 10','Curitiba - PR','CEP 80010000'])
    data=sender_address(profile)
    assert data['endereco']=='Rua Exemplo' and data['numero']=='10'
    assert data['bairro']==''
    profile.data={**data,'bairro':'Centro','endereco':'Rua Atualizada'}
    assert 'Rua Atualizada, 10' in sender_lines(profile)


def test_service_number_uses_saved_quote_and_creates_confirmable_preview(env,monkeypatch):
    from app.services import assistant_agent as agent,assistant_freight as bot
    from app.models.assistant import AssistantIdentity,AssistantAction
    from test_assistant import incoming
    factory,c,uid,did=env
    monkeypatch.setattr(bot,'SessionLocal',factory)
    monkeypatch.setattr(agent,'complete',lambda *a,**kw:pytest.fail('Service selection must not depend on AI'))
    calls=[]
    def provider(method,path,body=None):
        calls.append((path,body))
        assert path=='cart'
        return {'id':'cart-test','price':46.49,'status':'pending'}
    monkeypatch.setattr(sf,'call',provider)
    with factory() as db:
        source=incoming(db,uid,'Cotar etiqueta',channel='telegram')
        order=FreightOrder(request_key=source.id,user_id=uid,environment=sf.environment(),state='quoted',payload={'to':{'name':'Cliente'},'from':{'name':'Remetente'}},rates=[{'id':1,'name':'PAC','price':25.65},{'id':2,'name':'SEDEX','price':46.49}])
        db.add(order);db.flush();source.response=bot.quote_preview(order);source.status='done';db.commit();key=order.id
    with factory() as db:
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        message=incoming(db,uid,'2',channel='telegram');db.commit()
        result=agent.respond(db,message,identity)
        assert 'SEDEX' in result and '46.49' in result and 'confirmo' in result
        action=db.query(AssistantAction).filter_by(source_message_id=message.id).one()
        assert action.kind=='frete_emitir' and action.payload['freight_id']==str(key)
        db.commit()
    with factory() as db:
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        message=incoming(db,uid,'2',channel='telegram');db.commit()
        assert 'SEDEX' in agent.respond(db,message,identity)
        assert db.query(AssistantAction).filter_by(status='draft').count()==1
    assert len(calls)==1 and calls[0][1]['service']==2
    assert not any(path=='checkout' for path,_ in calls)
