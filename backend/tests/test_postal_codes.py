import copy
import uuid
import pytest
import requests
from app.services import postal_codes as pc
from app.services.assistant_tools import execute_tool
from app.models.assistant import AssistantIdentity, AssistantAction
from app.models.printing import PrintSender, PrintJob
from app.models.address_book import SavedAddress
from test_assistant import setup, incoming
from test_address_manager import env

lookup_client = pc.lookup_cep
OFFICIAL={'cep':'01050-030','endereco':'Rua Major Quedinho','bairro':'Centro','cidade':'São Paulo','estado':'SP'}


@pytest.fixture
def found(monkeypatch):
    monkeypatch.setattr(pc,'lookup_cep',lambda cep:{'status':'found','data':dict(OFFICIAL)})


def test_lookup_validates_format_caches_and_sends_only_cep(monkeypatch):
    pc._cache.clear();calls=[]
    class Response:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def json(self):return {'cep':'01050-030','logradouro':'Rua Major Quedinho - de 1/2 ao fim','bairro':'Centro','localidade':'São Paulo','uf':'SP','complemento':'lado par'}
    def get(url,**kwargs):calls.append((url,kwargs));return Response()
    monkeypatch.setattr(pc.requests,'get',get)
    for invalid in ('01050-03','01050-030/../../','https://example.com','１２３４５６７８'):
        assert lookup_client(invalid)['status']=='invalid'
    one=lookup_client('01050-030');assert one['data']==OFFICIAL
    one['data']['cidade']='Modified'
    assert lookup_client('01050030')['data']['cidade']=='São Paulo'
    assert len(calls)==1 and calls[0][0]=='https://viacep.com.br/ws/01050030/json/'
    assert calls[0][1]=={'timeout':(2,4),'allow_redirects':False}


def test_unavailable_timeout_and_not_found(monkeypatch):
    pc._cache.clear()
    def unavailable(*args,**kw):raise requests.Timeout()
    monkeypatch.setattr(pc.requests,'get',unavailable)
    assert lookup_client('01050030')['status']=='unavailable'
    class Missing:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def json(self):return {'erro':True}
    monkeypatch.setattr(pc.requests,'get',lambda *a,**k:Missing())
    assert lookup_client('99999999')['status']=='not_found'


def test_complete_missing_fields_preserves_private_fields_and_py(found):
    supplied={'pais':'BR','nome':'Cliente','cep':'01050030','numero':'322','complemento':'Apt 805','cpf':'12345678909'}
    result=pc.complete_address(supplied)
    assert result['data']==supplied|OFFICIAL
    assert result['filled']==['endereco','bairro','cidade','estado']
    assert supplied['cep']=='01050030'
    assert pc.complete_address({'pais':'PY','nome':'Juan','cidade':'Asunción'})['status']=='skipped'


def test_conflicts_do_not_overwrite_or_mix_locations_and_abbreviations_agree(found):
    raw={'pais':'BR','cep':'01050-030','endereco':'Rua Outra','numero':'10'}
    result=pc.complete_address(raw)
    assert result['data']==raw and result['conflicts'][0]['field']=='endereco'
    assert result['filled']==[] and 'Rua Outra' in result['warnings'][0]
    for street in ('R. Major Quedinho','Rua Major Quedinho, 322, Apto 805'):
        result=pc.complete_address({**raw,'endereco':street,'cidade':'Sao Paulo'})
        assert not result['conflicts'] and result['data']['bairro']=='Centro'
    assert not pc.agrees('endereco','Rua Major Quedinho Filho, 322',OFFICIAL['endereco'])


def test_general_cep_does_not_invent_street_or_number(monkeypatch):
    monkeypatch.setattr(pc,'lookup_cep',lambda cep:{'status':'found','data':{**OFFICIAL,'endereco':'','bairro':''}})
    result=pc.complete_address({'pais':'BR','cep':'01050030','endereco':''})
    assert not result['data']['endereco'] and 'numero' not in result['data']
    assert 'bairro' not in result['filled']


def test_frontend_registration_and_print_use_same_completed_address(env,found):
    factory,client,uid,did=env
    with factory() as db:
        db.add(PrintSender(id='teste',name='Remetente',lines=['Remetente','Rua A, 1']));db.commit()
    raw={'pais':'BR','nome':'Cliente Teste','cep':'01050030','numero':'322','complemento':'Apt 805'}
    check=client.post('/manager/postal-code',json=raw)
    assert check.status_code==200 and check.json()['data']['bairro']=='Centro'
    saved=client.post('/manager/addresses',json={'label':'Cliente Teste','data':raw}).json()
    assert saved['data']['endereco']==OFFICIAL['endereco']
    body={'request_key':str(uuid.uuid4()),'device_id':did,'data':raw,'sender_id':'teste'}
    job=client.post('/manager/print',json=body);assert job.status_code==200,job.text
    assert client.post('/manager/print',json=body).json()['id']==job.json()['id']
    assert client.get('/manager/addresses').json()['total']==1
    with factory() as db:
        printed=db.get(PrintJob,uuid.UUID(job.json()['id']))
        assert printed.snapshot['endereco']['bairro']=='Centro'
        assert printed.address_id==uuid.UUID(saved['id'])
        assert pc.street_line(printed.snapshot['endereco'])=='Rua Major Quedinho, 322, Centro, Apt 805'


def test_bot_print_completes_before_required_field_validation(env,found):
    factory,_,uid,_=env
    with factory() as db:
        db.add(PrintSender(id='teste',name='Remetente',lines=['Remetente','Rua A, 1']));db.flush()
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        msg=incoming(db,uid,'Imprima Cliente CEP 01050030 número 322 sem CPF',channel='telegram')
        args={'pais':'BR','nome':'Cliente','cep':'01050030','numero':'322','remetente':'teste'}
        out=execute_tool(db,msg,identity,'preparar_impressao',args)
        assert 'confirmacao' in out
        action=db.query(AssistantAction).filter_by(source_message_id=msg.id).one()
        assert action.payload['endereco']['bairro']=='Centro' and action.payload['endereco']['cpf']==''
        assert not db.query(PrintJob).count()


def test_quote_completes_postal_fields_without_modifying_sender_profile(env,found,monkeypatch):
    from app.services import assistant_freight as bot, superfrete as sf
    factory,_,uid,_=env
    calls=[]
    def calculator(method,path,payload):
        calls.append((method,path,payload));return [{'id':1,'name':'PAC','price':20}]
    monkeypatch.setattr(sf,'call',calculator)
    raw={'pais':'BR','nome':'Cliente','cep':'01050030','numero':'322','cpf':'12345678909'}
    args={'endereco':raw,'remetente':{**raw,'nome':'Loja'},'package':{'weight':1,'height':15,'width':20,'length':15},'products':[{'name':'Camiseta','quantity':1,'unitary_value':50}],'non_commercial':True}
    with factory() as db:
        identity=db.query(AssistantIdentity).filter_by(channel='telegram').one()
        msg=incoming(db,uid,'Cote este pacote',channel='telegram')
        result=bot.execute(db,msg,identity,'cotar_superfrete',args)
        assert result['state']=='quoted' and result['postal_warnings']==[]
        from app.models.address_book import FreightOrder
        order=db.get(FreightOrder,uuid.UUID(result['id']))
        assert order.payload['to']['district']=='Centro' and order.payload['from']['city']=='São Paulo'
        assert db.query(SavedAddress).one().data['bairro']=='Centro'
        assert len(calls)==1 and calls[0][1]=='calculator'
