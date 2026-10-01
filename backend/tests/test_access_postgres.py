"""Run against disposable PostgreSQL: ACCESS_TEST_DATABASE_URL=postgresql://... ."""
import importlib.util
import os
from pathlib import Path
import uuid

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url


@pytest.fixture
def pg():
    url=os.getenv('ACCESS_TEST_DATABASE_URL')
    if not url: pytest.skip('Set ACCESS_TEST_DATABASE_URL to an isolated local PostgreSQL')
    assert make_url(url).host in ('127.0.0.1','localhost','postgres'), 'Only isolated local/CI databases are allowed'
    engine=sa.create_engine(url)
    schema='access_test_'+uuid.uuid4().hex
    with engine.begin() as conn: conn.exec_driver_sql(f'CREATE SCHEMA {schema}')
    try: yield engine,schema
    finally:
        with engine.begin() as conn: conn.exec_driver_sql(f'DROP SCHEMA {schema} CASCADE')
        engine.dispose()


def upgrade(conn,filename):
    path=Path(__file__).parents[1]/'alembic'/'versions'/filename
    spec=importlib.util.spec_from_file_location('isolated_migration',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    with Operations.context(MigrationContext.configure(conn)): mod.upgrade()


def test_new_migrations_preserve_users_and_only_backfill_explicit_customers(pg):
    engine,schema=pg
    owner,vendor,customer,order,linked,unlinked=[uuid.uuid4() for _ in range(6)]
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE usuarios(id uuid PRIMARY KEY,email varchar(100) NOT NULL UNIQUE,nome varchar(100))')
        conn.exec_driver_sql('CREATE TABLE vendedores(id uuid PRIMARY KEY,usuario_id uuid REFERENCES usuarios(id))')
        conn.exec_driver_sql('CREATE TABLE clientes(id uuid PRIMARY KEY,nome varchar(200))')
        conn.exec_driver_sql('CREATE TABLE pedidos(id uuid PRIMARY KEY,cliente_id uuid REFERENCES clientes(id))')
        conn.exec_driver_sql('CREATE TABLE rastreamentos(id uuid PRIMARY KEY,pedido_id uuid REFERENCES pedidos(id),destinatario varchar(200))')
        conn.execute(sa.text('INSERT INTO usuarios VALUES(:id,:email,:nome)'),dict(id=owner,email='lucas@eleven.com',nome='Lucas'))
        conn.execute(sa.text('INSERT INTO vendedores VALUES(:id,:user)'),dict(id=vendor,user=owner))
        conn.execute(sa.text('INSERT INTO clientes VALUES(:id,:name)'),dict(id=customer,name='Nome igual'))
        conn.execute(sa.text('INSERT INTO pedidos VALUES(:id,:customer)'),dict(id=order,customer=customer))
        conn.execute(sa.text('INSERT INTO rastreamentos VALUES(:id,:order,:name)'),[dict(id=linked,order=order,name='Nome igual'),dict(id=unlinked,order=None,name='Nome igual')])
        upgrade(conn,'z6a7b8c9d0e1_access_audit.py')
        upgrade(conn,'a7b8c9d0e1f2_customer_tracking_links.py')
        user=conn.execute(sa.text('SELECT id,email,auth_version,must_change_password,sales_scope FROM usuarios')).one()
        assert user==(owner,'lucas@eleven.com',0,False,'all')
        assert conn.execute(sa.text('SELECT cliente_id FROM rastreamentos WHERE id=:id'),{'id':linked}).scalar()==customer
        assert conn.execute(sa.text('SELECT cliente_id FROM rastreamentos WHERE id=:id'),{'id':unlinked}).scalar() is None
        assert {'auth_sessions','audit_events','activity_spans'} <= set(sa.inspect(conn).get_table_names(schema=schema))
        assert any(index['name']=='ix_usuarios_email_lower' and index['unique'] for index in sa.inspect(conn).get_indexes('usuarios',schema=schema))
    # Index and FK validation are PostgreSQL behavior, not inferred from SQLite.
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.execute(sa.text('INSERT INTO usuarios(id,email) VALUES(:id,:email)'),{'id':uuid.uuid4(),'email':'LUCAS@ELEVEN.COM'})
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
            conn.execute(sa.text('UPDATE usuarios SET vendedor_id=:id'),{'id':uuid.uuid4()})


def test_activity_endpoint_serializes_credit_across_concurrent_tabs(pg, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from threading import Barrier
    from types import SimpleNamespace
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Usuario, Vendedor
    from app.models.usuario import UsuarioRole
    from app.models.access import AuthSession, AuditEvent, ActivitySpan, now
    from app.api.endpoints import user_admin

    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,AuthSession,AuditEvent,ActivitySpan)])
    factory=sessionmaker(bind=isolated)
    moment=now(); monkeypatch.setattr(user_admin,'now',lambda:moment)
    user_id,session_id=uuid.uuid4(),uuid.uuid4()
    span_ids=[uuid.uuid4(),uuid.uuid4()]
    with factory() as db:
        db.add(Usuario(id=user_id,nome='Fixture',email='fixture@example.com',senha_hash='not-used',role=UsuarioRole.GERENTE))
        db.flush()
        db.add(AuthSession(id=session_id,user_id=user_id,expires_at=moment+timedelta(hours=1),activity_credit_at=moment-timedelta(seconds=15)))
        db.flush()
        for span_id in span_ids:
            db.add(ActivitySpan(id=span_id,user_id=user_id,session_id=session_id,module='inventory',started_at=moment-timedelta(seconds=15),last_seen_at=moment-timedelta(seconds=15)))
        db.commit()
    barrier=Barrier(2)
    def tick(span_id):
        with factory() as db:
            user=db.get(Usuario,user_id)
            barrier.wait(timeout=5)
            return user_admin.activity(user_admin.Activity(id=span_id,module='inventory',sequence=1,seconds=30),
                                      SimpleNamespace(state=SimpleNamespace(auth_session_id=session_id)),user,db)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(tick,span_ids))
        assert sum(r['active_seconds'] for r in results)==15
        with factory() as db:
            assert db.query(sa.func.sum(ActivitySpan.active_seconds)).scalar()==15
    finally:
        isolated.dispose()


def test_manual_and_receipt_registration_serialize_the_same_code(pg, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from app.config import settings
    from app.database import Base
    from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
    from app.models.assistant import AssistantAction, AssistantMessage
    from app.services.receipt_tracking import confirm_receipt, KIND
    from app.api.endpoints.rastreamento import criar_rastreamento
    from app.schemas.rastreamento import RastreamentoCreate

    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Cliente,Pedido,Rastreamento,AssistantMessage,AssistantAction)])
    factory=sessionmaker(bind=isolated,autoflush=False)
    uid,mid,aid=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    code='RR473124829BR'
    with factory() as db:
        db.add(Usuario(id=uid,nome='Fixture',email='fixture@example.com',senha_hash='unused'));db.flush()
        db.add(AssistantMessage(id=mid,user_id=uid,channel='telegram',external_id='local-fixture',conversation_id='local-only',sender_id='local-only',text='Confirmo'));db.flush()
        db.add(AssistantAction(id=aid,user_id=uid,source_message_id=mid,kind=KIND,payload={'objetos':[{'codigo':code,'destinatario':'Fixture'}]}))
        db.commit()
    barrier=Barrier(2)
    def run(channel):
        with factory() as db:
            barrier.wait(timeout=5)
            if channel=='receipt':
                result=confirm_receipt(db,db.get(AssistantMessage,mid),db.get(AssistantAction,aid));db.commit();return result
            try:
                result=criar_rastreamento(RastreamentoCreate(codigo_rastreio='rr 473 124 829 br'),db,db.get(Usuario,uid))
                return str(result.id)
            except HTTPException as exc:
                assert exc.status_code==409
                db.rollback();return 'already_registered'
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(run,['receipt','web']))
        with factory() as db:
            assert db.query(Rastreamento).count()==1
            assert db.query(Rastreamento).one().codigo_rastreio==code
            assert db.get(AssistantAction,aid).status=='executed'
    finally:
        isolated.dispose()


def test_scheduler_preserves_newer_manual_results_and_updates_order_atomically(pg,monkeypatch):
    from datetime import datetime
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app import database, main
    from app.database import Base
    from app.models import Usuario, Vendedor, Cliente, Pedido, Rastreamento
    from app.models.pedido import PedidoStatus
    from app.models.rastreamento import RastreamentoStatus as Status
    from app.services import wonca_service

    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Cliente,Pedido,Rastreamento)])
    factory=sessionmaker(bind=isolated,autoflush=False)
    monkeypatch.setattr(database,'SessionLocal',factory)
    order_id=uuid.uuid4()
    with factory() as db:
        db.add(Pedido(id=order_id,numero_pedido='LOCAL-FIXTURE',descricao='Fixture',valor_total=1,status=PedidoStatus.PROCESSANDO));db.flush()
        for code in ('FIRST','SECOND'):
            db.add(Rastreamento(codigo_rastreio=code,pedido_id=order_id,status=Status.PENDENTE))
        db.commit()
    def provider(code):
        if code=='FIRST':
            with factory() as db:
                row=db.query(Rastreamento).filter_by(codigo_rastreio=code).one()
                row.status=Status.EM_TRANSITO;row.ultima_atualizacao=datetime(2026,9,30,12)
                row.historico_eventos=[{'status':'Newer manual result'}];db.commit()
        return [{'status':'Older provider result'}],{},Status.ENTREGUE
    monkeypatch.setattr(wonca_service,'parse_tracking',provider)
    try:
        main._job_atualizar_rastreamentos()
        with factory() as db:
            first=db.query(Rastreamento).filter_by(codigo_rastreio='FIRST').one()
            second=db.query(Rastreamento).filter_by(codigo_rastreio='SECOND').one()
            assert first.status==Status.EM_TRANSITO and first.historico_eventos==[{'status':'Newer manual result'}]
            assert second.status==Status.ENTREGUE
            assert db.get(Pedido,order_id).status==PedidoStatus.ENVIADO
        monkeypatch.setattr(wonca_service,'parse_tracking',lambda _: ([],{},Status.ENTREGUE))
        main._job_atualizar_rastreamentos()
        with factory() as db:assert db.get(Pedido,order_id).status==PedidoStatus.ENTREGUE
    finally:
        isolated.dispose()


@pytest.mark.parametrize('operation',['single','upsert','batch'])
def test_manual_refresh_never_applies_old_provider_data_to_an_edited_code(pg,monkeypatch,operation):
    from sqlalchemy.orm import sessionmaker
    from fastapi import HTTPException
    from app.config import settings
    from app.database import Base
    from app.models import Usuario,Vendedor,Cliente,Pedido,Rastreamento
    from app.models.rastreamento import RastreamentoStatus as Status
    from app.api.endpoints import rastreamento as api
    from app.services import wonca_service
    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    engine,schema=pg
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated,tables=[m.__table__ for m in (Usuario,Vendedor,Cliente,Pedido,Rastreamento)])
    factory=sessionmaker(bind=isolated,autoflush=False)
    tracking_id=uuid.uuid4()
    with factory() as db:
        db.add(Rastreamento(id=tracking_id,codigo_rastreio='ORIGINAL',status=Status.PENDENTE));db.commit()
    def provider(code):
        assert code=='ORIGINAL'
        with factory() as other:
            current=other.get(Rastreamento,tracking_id)
            current.codigo_rastreio='EDITED';current.status=Status.EM_TRANSITO
            current.historico_eventos=[{'status':'Current parcel'}];other.commit()
        return [{'status':'Old parcel delivered'}],{},Status.ENTREGUE
    monkeypatch.setattr(wonca_service,'parse_tracking',provider)
    try:
        with factory() as db:
            if operation=='batch':
                result=api.atualizar_todos_rastreamentos(db,None)
                assert result['updated']==0 and result['skipped']==['ORIGINAL']
            else:
                with pytest.raises(HTTPException) as error:
                    if operation=='single':api.atualizar_rastreamento_online(tracking_id,db,None)
                    else:api.consultar_e_salvar_rastreamento({'codigo':'ORIGINAL'},db,None)
                assert error.value.status_code==409
                db.rollback()
        with factory() as db:
            current=db.get(Rastreamento,tracking_id)
            assert current.codigo_rastreio=='EDITED' and current.status==Status.EM_TRANSITO
            assert current.historico_eventos==[{'status':'Current parcel'}]
    finally:isolated.dispose()
