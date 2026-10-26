"""Owner-reviewed cleanup preserves operational rows and rejects stale identities."""
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_assistant import setup
from test_address_manager import env
from test_customer_maintenance import pair
from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import Usuario, Cliente
from app.models.usuario import UsuarioRole
from app.models.address_book import SavedAddress
from app.api.endpoints.directory_duplicates import router
from app.services.directory_duplicates import candidates, merge_pair
from app.services.address_book import address_family
from app.services.user_audit import bind_actor


@pytest.fixture
def review_app(env):
    factory,_,uid,_=env
    with factory() as db:
        user=db.get(Usuario,uid);user.email='lucas@eleven.com';db.commit()
    app=FastAPI();app.include_router(router,prefix='/api/clientes')
    def session():
        with factory() as db:yield db
    def user():
        with factory() as db:return db.get(Usuario,uid)
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_active_user]=user
    return factory,TestClient(app),uid


def test_customer_review_has_no_effect_until_owner_confirms_and_replay_is_safe(review_app):
    factory,c,uid=review_app
    with factory() as db:
        target,source,order,_,_=pair(db,uid)
        body={'kind':'customers','target_id':str(target.id),'source_id':str(source.id)};db.commit()
    base='/api/clientes/maintenance/duplicates'
    assert len(c.get(base,params={'kind':'customers'}).json()['items'])==1
    preview=c.post(base+'/preview',json=body)
    assert preview.status_code==200,preview.text
    request={**body,'confirm':True,'plan_token':preview.json()['plan_token']}
    with factory() as db:assert db.get(Cliente,uuid.UUID(body['source_id'])).merged_into_id is None
    assert c.post(base+'/confirm',json={**request,'confirm':False}).status_code==422
    response=c.post(base+'/confirm',json=request)
    assert response.status_code==200,response.text
    assert c.post(base+'/confirm',json=request).json()['state']=='already_merged'
    assert c.get(base,params={'kind':'customers'}).json()['items']==[]
    with factory() as db:assert db.query(Cliente).count()==2


def address_pair(db,uid,**overrides):
    data={'pais':'BR','nome':'Ana Correia','cidade':'São Paulo','estado':'SP','cep':'01310000','numero':'100','bairro':'Centro','cpf':'12345678901'}
    target=SavedAddress(label='Ana principal',data={**data,'endereco':'Avenida Paulista'},created_by=uid,active=False)
    source=SavedAddress(label='Ana duplicada',data={**data,'endereco':'Av. Paulista',**overrides},created_by=uid)
    db.add_all([target,source]);db.commit()
    return target,source


def test_address_cleanup_retains_source_data_alias_and_history_family(env):
    factory,_,uid,_=env
    with factory() as db:
        bind_actor(db,db.get(Usuario,uid))
        target,source=address_pair(db,uid)
        assert len(candidates(db,'addresses')['items'])==1
        original=dict(source.data)
        plan=merge_pair(db,'addresses',target.id,source.id)
        assert plan['state']=='ready' and not source.merged_into_id
        result=merge_pair(db,'addresses',target.id,source.id,apply=True,expected_plan=plan['plan_token'])
        assert result['state']=='merged' and source.data==original and not source.active and target.active
        assert address_family(db,target)=={target.id,source.id}
        assert merge_pair(db,'addresses',target.id,source.id,apply=True)['state']=='already_merged'


@pytest.mark.parametrize('change', ['document','customer','location','version'])
def test_address_conflicts_and_stale_plan_never_merge(env,change):
    from fastapi import HTTPException
    factory,_,uid,_=env
    with factory() as db:
        target,source=address_pair(db,uid)
        plan=merge_pair(db,'addresses',target.id,source.id)
        if change=='document':source.data={**source.data,'cpf':'98765432100'}
        elif change=='location':source.data={**source.data,'numero':'101'}
        elif change=='version':source.version+=1
        else:
            a,b=Cliente(nome='Pessoa Um'),Cliente(nome='Pessoa Dois');db.add_all([a,b]);db.flush()
            target.cliente_id=a.id;source.cliente_id=b.id
        db.flush()
        with pytest.raises(HTTPException) as error:
            merge_pair(db,'addresses',target.id,source.id,apply=True,expected_plan=plan['plan_token'])
        assert error.value.status_code==409
        assert source.merged_into_id is None and source.active


def test_duplicate_directory_is_owner_only_and_never_confuses_pdv_customers(review_app):
    factory,c,uid=review_app
    with factory() as db:
        db.get(Usuario,uid).role=UsuarioRole.GERENTE;db.commit()
    base='/api/clientes/maintenance/duplicates'
    assert c.get(base,params={'kind':'customers'}).status_code==403
    assert c.post(base+'/preview',json={'kind':'customers','target_id':str(uuid.uuid4()),'source_id':str(uuid.uuid4())}).status_code==403
