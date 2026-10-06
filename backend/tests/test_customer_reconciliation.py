"""Identity conflicts, preserved history, repeat runs and vendor privacy."""
import uuid
from datetime import date
from test_assistant import setup
from test_address_manager import env
from app.database import Base
from app.models import Cliente, Pedido, Rastreamento, Vendedor, Usuario, Folga
from app.models.address_book import SavedAddress
from app.models.sales_bi import SalesBIWorkbook
from app.models.printing import PrintJob
from app.models.assistant import utcnow
from app.services.customer_identity import match_recipient, phone_key
from app.services.customer_reconciliation import reconcile, auto_link_tracking
from app.services.address_book import save_or_reuse, edit_address
from app.services.vendor_activity import activity, reconcile_vendors
from app.schemas.address_book import AddressInput
from app.api.endpoints.clientes import historico_enderecos_cliente


def test_address_creation_reuse_and_existing_identity(env):
    factory, _, uid, _ = env
    with factory() as db:
        original=Cliente(nome='João da Silva',telefone='+595972394123')
        db.add(original);db.flush()
        a,_=save_or_reuse(db,{'pais':'PY','nome':'JOAO DA SILVA','cidade':'Asunción','telefone':'0972 394 123'},uid)
        b,_=save_or_reuse(db,{'pais':'PY','nome':'João da Silva','cidade':'Encarnación','telefone':'+595 972394123'},uid)
        repeat,reused=save_or_reuse(db,a.data,uid)
        assert a.cliente_id==b.cliente_id==original.id and repeat.id==a.id and reused
        assert db.query(Cliente).count()==1
        assert phone_key('0972 394 123')==phone_key('+595972394123')


def test_ambiguous_name_keeps_customers_separate_and_review_survives_edit(env):
    factory, _, uid, _=env
    with factory() as db:
        db.add_all([Cliente(nome='Joao Silva'),Cliente(nome='João Silva')]);db.flush()
        a,_=save_or_reuse(db,{'pais':'PY','nome':'Joao Silva','cidade':'Asunción'},uid)
        assert db.query(Cliente).count()==3 and a.customer_link_review
        assert match_recipient(db,'Joao Silva') is None
        body=AddressInput(label='Casa',data=a.data,cliente_id=a.cliente_id,version=a.version)
        a,_=edit_address(db,a.id,body)
        assert a.customer_link_review
        a,_=edit_address(db,a.id,body.model_copy(update={'version':a.version,'customer_link_confirmed':True}))
        assert not a.customer_link_review and a.customer_link_reason=='manual'


def test_document_name_conflict_does_not_reassign_identity_or_unique_document(env):
    factory, _, uid, _=env
    with factory() as db:
        owner=Cliente(nome='Pessoa Original',cpf='12345678909');db.add(owner);db.flush()
        a,_=save_or_reuse(db,{'pais':'BR','nome':'Outro Cliente','cpf':'12345678909','cidade':'São Paulo'},uid)
        assert a.cliente_id != owner.id and a.customer_link_review
        assert db.get(Cliente,a.cliente_id).cpf is None
        assert owner.nome=='Pessoa Original'


def test_paraguay_document_never_becomes_cpf_and_new_address_creates_customer(env):
    factory,_,uid,_=env
    with factory() as db:
        a,_=save_or_reuse(db,{'pais':'PY','nome':'Maria Teste','cidade':'Asunción','cpf':'RUC-111'},uid)
        c=db.get(Cliente,a.cliente_id)
        assert c.nome=='Maria Teste' and c.cpf is None and a.data['cpf']=='RUC-111'


def test_reconciliation_only_links_existing_customers_and_is_idempotent(env):
    factory,_,uid,_=env
    with factory() as db:
        a=SavedAddress(label='Casa',data={'pais':'PY','nome':'Ana Correia','cidade':'Asunción'},created_by=uid)
        known=Cliente(nome='Bruno Silva');db.add_all([a,known]);db.flush()
        order=Pedido(numero_pedido='LOCAL-1',descricao='Fixture',valor_total=42,cliente_nome='Ana Correia')
        db.add(order);db.flush()
        inherited=Rastreamento(codigo_rastreio='LOCAL1',pedido_id=order.id,destinatario='Texto preservado')
        named=Rastreamento(codigo_rastreio='LOCAL2',destinatario='BRUNO SILVA')
        unknown=Rastreamento(codigo_rastreio='LOCAL3',destinatario='Pessoa Sem Cadastro')
        db.add_all([inherited,named,unknown]);db.flush()
        result=reconcile(db)
        assert result['customers_created']==1 and result['addresses_linked']==1
        assert result['orders_linked']==1 and result['tracking_linked']==2
        assert inherited.cliente_id==order.cliente_id==a.cliente_id
        assert named.cliente_id==known.id and unknown.cliente_id is None
        assert inherited.destinatario=='Texto preservado' and order.valor_total==42
        again=reconcile(db)
        assert all(again[k]==0 for k in ('customers_created','addresses_linked','orders_linked','tracking_linked'))
        assert len(again['unmatched_tracking'])==1


def test_new_tracking_preserves_explicit_link_and_ignores_first_name_only(env):
    factory,_,_,_=env
    with factory() as db:
        one,two=Cliente(nome='Ana'),Cliente(nome='Bruno Silva')
        db.add_all([one,two]);db.flush()
        row=Rastreamento(codigo_rastreio='LOCAL',destinatario='Ana')
        assert not auto_link_tracking(db,row) and not row.cliente_id
        row.cliente_id=two.id
        assert not auto_link_tracking(db,row) and row.cliente_id==two.id


def test_customer_usage_includes_merged_addresses_once_and_not_other_customers(env):
    factory,_,uid,did=env
    with factory() as db:
        a,_=save_or_reuse(db,{'pais':'PY','nome':'Cliente Atual','cidade':'Asunción'},uid)
        b=SavedAddress(label='Antigo',data={},created_by=uid,merged_into_id=a.id,active=False)
        db.add(b);db.flush()
        db.add(PrintJob(user_id=uid,device_id=uuid.UUID(did),address_id=b.id,source='bot',
            request_key=uuid.uuid4(),status='submitted',snapshot={},pdf=b'fixture',sha256='0'*64,expires_at=utcnow()))
        db.flush()
        result=historico_enderecos_cliente(str(a.cliente_id),0,30,'all',db,db.get(Usuario,uid))
        assert result['summary']['address_prints']==1 and result['total']==1 and len(result['addresses'])==1


def workbook():
    return SalesBIWorkbook(id='local',kind='archive',filename='local.xlsx',year=2026,month=9,active=True,
        snapshot={'total_usd':'900','source_cell':'Z1','warnings':['Other vendor issue'],
        'sellers':{'Junior':{'total_usd':'100','currencies':{'USD':'100'}},'Lucas':{'total_usd':'800'}},
        'weeks':[{'index':1,'label':'Semana 1','total_usd':'900','sellers':{'Junior':'100','Lucas':'800'}}]})


def test_vendor_mapping_and_own_sales_privacy(env):
    factory,_,uid,_=env
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[SalesBIWorkbook.__table__])
        v=Vendedor(nome='Juninho');other=Vendedor(nome='Lucas')
        db.add_all([v,other,workbook()]);db.flush()
        u=db.get(Usuario,uid);u.vendedor_id=v.id;u.sales_seller='Junior';u.sales_scope='own';db.flush()
        assert reconcile_vendors(db)['vendors_linked']==2
        assert v.sales_seller=='Junior'
        db.add(Folga(vendedor_id=v.id,data=date(2026,9,20)));db.flush()
        own=activity(db,v,u,2026)
        assert own['sales']['selected']['total_usd']==100 and len(own['days_off'])==1
        assert own['sales']['sellers']==['Junior'] and own['sales']['months'][0]['warnings']==[]
        denied=activity(db,other,u,2026)
        assert denied['sales'] is None and not denied['sales_access'] and denied['last_synced_at'] is None
        assert reconcile_vendors(db)['vendors_linked']==0
        u.sales_seller='Lucas'
        assert activity(db,v,u,2026)['sales'] is None
        u.sales_scope='all'
        assert activity(db,other,u,2026)['sales']['selected']['total_usd']==800


def test_vendor_mapping_refuses_duplicate_aliases(env):
    factory,_,_,_=env
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[SalesBIWorkbook.__table__])
        db.add_all([Vendedor(nome='Junior',sales_seller='Junior'),Vendedor(nome='Juninho'),workbook()]);db.flush()
        result=reconcile_vendors(db)
        assert result['vendors_linked']==0 and len(result['vendor_reviews'])==1


def test_new_customer_link_is_audited_with_actor(env):
    from app.models.access import AuditEvent
    from app.services.user_audit import bind_actor
    factory,_,uid,_=env
    with factory() as db:
        bind_actor(db,db.get(Usuario,uid),source='telegram')
        row,_=save_or_reuse(db,{'pais':'PY','nome':'Cliente Auditado','cidade':'Asunción'},uid)
        db.flush()
        event=db.query(AuditEvent).filter_by(action='customer_auto_created').one()
        assert event.user_id==uid and event.source=='telegram'
        assert event.changes['cliente_id']==str(row.cliente_id)
