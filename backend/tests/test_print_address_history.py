"""Real A4 uses, including legacy jobs, share the address's freight history."""
import copy
import importlib.util
import uuid
from datetime import timedelta
from pathlib import Path

from test_assistant import setup, incoming
from test_address_manager import env
from app.models.address_book import SavedAddress, FreightOrder
from app.models.assistant import AssistantAction, utcnow
from app.models.printing import PrintJob, PrintSender
from app.services.address_book import save_or_reuse, save_print_address
from app.services.address_identity import print_matches_saved
from app.services.assistant_printing import AddressArgs, enqueue_print


ADDRESS = {'pais':'BR','nome':'Cliente Exemplo','endereco':'Rua Exemplo','numero':'50',
           'bairro':'Centro','cidade':'Poá','estado':'SP','cep':'08555-010'}
PRINTED = {k:v for k,v in ADDRESS.items() if k not in ('numero','bairro')}
PRINTED['endereco'] = 'Rua Exemplo, 50'


def migration():
    path=Path(__file__).parents[1]/'alembic/versions/w3x4y5z6a7b8_print_address_history.py'
    spec=importlib.util.spec_from_file_location('print_address_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def job(db,uid,did,data=None,source='bot',status='submitted',address_id=None):
    row=PrintJob(device_id=uuid.UUID(did),user_id=uid,request_key=uuid.uuid4(),
        snapshot={'endereco':copy.deepcopy(data or PRINTED)},source=source,status=status,
        pdf=b'',sha256='a'*64,expires_at=utcnow()+timedelta(hours=24),address_id=address_id,
        created_at=utcnow()-timedelta(days=3),finished_at=utcnow() if status=='submitted' else None)
    db.add(row);db.flush()
    return row


def test_backfill_reuses_full_address_and_creates_missing_without_reprinting(env):
    factory,c,uid,did=env
    with factory() as db:
        existing,_=save_or_reuse(db,ADDRESS,uid)
        first=job(db,uid,did);second=job(db,uid,did)
        third=job(db,uid,did,{'pais':'PY','nome':'Juan','cidade':'Asunción','telefone':'123'})
        fourth=job(db,uid,did,{'pais':'PY','nome':'Juan','cidade':'Asunción','telefone':'123'})
        external=job(db,uid,did,source='bot_pdf_ephemeral')
        originals={j.id:(copy.deepcopy(j.snapshot),j.status,j.created_at,j.finished_at) for j in (first,second,third,fourth,external)}
        result=migration().backfill(db.connection());db.expire_all()
        assert result=={'linked':4,'created':1,'skipped':0}
        assert first.address_id==second.address_id==existing.id
        assert third.address_id==fourth.address_id and third.address_id!=existing.id
        assert external.address_id is None
        assert db.query(PrintJob).count()==5 and db.query(SavedAddress).count()==2
        assert db.query(PrintJob).filter_by(status='pending').count()==0
        for key,values in originals.items():
            j=db.get(PrintJob,key)
            assert (j.snapshot,j.status,j.created_at.replace(tzinfo=None),j.finished_at.replace(tzinfo=None))==(
                values[0],values[1],values[2].replace(tzinfo=None),values[3].replace(tzinfo=None))
        assert migration().backfill(db.connection())=={'linked':0,'created':0,'skipped':0}
        db.commit();key=existing.id
    result=c.get(f'/manager/addresses/{key}/usage').json()
    assert result['summary']['address_prints']==2
    assert result['items'][0]['finished_at']


def test_backfill_ignores_incomplete_conflicting_and_ambiguous_snapshots(env):
    factory,c,uid,did=env
    with factory() as db:
        save_or_reuse(db,ADDRESS|{'cpf':'12345678909'},uid)
        conflict=job(db,uid,did,PRINTED|{'cpf':'98765432100'})
        empty=job(db,uid,did,{'pais':'PY','nome':'Só nome'})
        save_or_reuse(db,ADDRESS|{'bairro':'Outro bairro'},uid)
        ambiguous=job(db,uid,did)
        assert migration().backfill(db.connection())=={'linked':0,'created':0,'skipped':3}
        db.expire_all()
        assert all(j.address_id is None for j in (conflict,empty,ambiguous))


def test_print_matching_never_ignores_location_or_apartment():
    assert print_matches_saved(PRINTED,ADDRESS)
    for changes in ({'numero':'51'},{'complemento':'Apto 2'},{'cidade':'Outra cidade'},
                    {'cep':'08555011'},{'nome':'Outro cliente'},{'endereco':'Outra rua'}):
        assert not print_matches_saved(PRINTED,ADDRESS|changes)
    assert not print_matches_saved(PRINTED|{'bairro':'Vila Nova'},ADDRESS)


def test_new_bot_prints_reuse_saved_full_address_and_count_after_submission(env):
    factory,c,uid,did=env
    with factory() as db:
        existing,_=save_or_reuse(db,ADDRESS,uid)
        source=incoming(db,uid,'Imprimir endereço',channel='telegram')
        action=AssistantAction(source_message_id=source.id,user_id=uid,kind='impressao',payload={
            'endereco':AddressArgs(**PRINTED,remetente='teste').model_dump(),
            'remetente':{'nome':'Remetente','linhas':['Remetente','Rua Teste, 10']},'device_id':did})
        db.add(action);db.flush()
        enqueue_print(db,action);enqueue_print(db,action)
        assert db.query(PrintJob).count()==1 and db.query(SavedAddress).count()==1
        printing=db.query(PrintJob).one();assert printing.address_id==existing.id
        db.commit();key=existing.id;jid=printing.id
    summary=c.get(f'/manager/addresses/{key}/usage').json()['summary']
    assert summary['prints']==1 and summary['address_prints']==0
    with factory() as db:
        j=db.get(PrintJob,jid);j.status='submitted';j.finished_at=utcnow();db.commit()
    summary=c.get(f'/manager/addresses/{key}/usage').json()['summary']
    assert summary['address_prints']==1 and summary['completed_prints']==1


def test_history_combines_labels_a4_and_preserves_unsuccessful_operations(env):
    factory,c,uid,did=env
    with factory() as db:
        address,_=save_or_reuse(db,ADDRESS,uid);key=address.id
        for status in ('pending','cancelled','failed','claimed','uncertain','expired','submitted'):
            job(db,uid,did,status=status,address_id=key)
        job(db,uid,did,source='erp',address_id=key)
        job(db,uid,did,source='superfrete',address_id=key)
        job(db,uid,did,source='bot_pdf_ephemeral',address_id=key)
        db.add(FreightOrder(request_key=uuid.uuid4(),user_id=uid,address_id=key,
            environment='production',state='released',rates=[],payload={'to':{'name':ADDRESS['nome']}}))
        db.commit()
    data=c.get(f'/manager/addresses/{key}/usage').json()
    assert data['total']==10
    summary=data['summary']
    assert (summary['prints'],summary['completed_prints'],summary['address_prints'],summary['label_prints'],summary['labels'])==(9,3,2,1,1)
    assert summary['last_printed_at']
    assert c.get(f'/manager/addresses/{key}/usage?kind=impressao').json()['total']==9
    assert c.get(f'/manager/addresses/{key}/usage?kind=frete').json()['total']==1


def test_erp_print_uses_same_address_when_district_omitted(env):
    factory,c,uid,did=env
    with factory() as db:
        address,_=save_or_reuse(db,ADDRESS,uid);key=address.id
        db.add(PrintSender(id='teste',name='Remetente',lines=['Remetente','Rua Teste, 10']));db.commit()
    result=c.post('/manager/print',json={'request_key':str(uuid.uuid4()),'device_id':did,
        'sender_id':'teste','address_id':str(key),'data':PRINTED})
    assert result.status_code==200,result.text
    assert result.json()['address_id']==str(key)
    assert c.get('/manager/addresses').json()['total']==1
