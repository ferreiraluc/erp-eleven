"""Inventory counts use isolated SQLite and synthetic products, never providers."""
from copy import deepcopy
import uuid

import pytest

from test_assistant import setup, incoming
from test_inventory_ocr import stock_app, item
from app.database import Base
from app.models.usuario import Usuario, UsuarioRole
from app.models.assistant import AssistantAction
from app.models.inventory import InventorySession, InventorySessionItem, SessionStatus, StockMovement, Item
from app.services.inventory_service import create_movement
from app.services.assistant_inventory import ItemsArgs, EntryArgs, duplicate_items, prepare_inventory, confirm_inventory
from app.services.assistant_channels import authorized_identity


@pytest.fixture
def counts(stock_app):
    factory,client,uid=stock_app
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[InventorySession.__table__,InventorySessionItem.__table__])
        db.get(Usuario,uid).role=UsuarioRole.GERENTE
        product=item(db,loja=6,deposito=4,barcode='789001')
        pid=str(product.id);db.commit()
    return factory,client,uid,pid


def start(counts,location='deposito'):
    _,client,_,_=counts
    r=client.post('/api/inventory/sessions',json={'name':'Contagem sintética','count_location':location,'location_filter':'metadado livre'})
    assert r.status_code==201,r.text
    assert r.json()['count_location']==location
    assert r.json()['location_filter']=='metadado livre'
    return r.json()['id']


def scan(counts,sid,quantity,pid=None):
    return counts[1].post(f'/api/inventory/sessions/{sid}/scan',json={'item_id':pid or counts[3],'counted_quantity':quantity})


def status(counts,sid,state):
    return counts[1].put(f'/api/inventory/sessions/{sid}/status',json={'status':state})


def apply(counts,sid):
    return counts[1].post(f'/api/inventory/sessions/{sid}/apply')


def test_local_count_preserves_other_location_and_uses_local_baseline(counts):
    factory,client,uid,pid=counts
    sid=start(counts)
    assert scan(counts,sid,3).status_code==201
    data=client.get(f'/api/inventory/sessions/{sid}').json()
    assert data['status']=='counting'
    assert data['session_items'][0]['system_quantity']==4
    assert data['session_items'][0]['difference']==-1
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==200
    with factory() as db:
        product=db.get(Item,uuid.UUID(pid))
        assert (product.current_stock,product.stock_loja,product.stock_deposito)==(9,6,3)
        session=db.get(InventorySession,uuid.UUID(sid))
        assert session.status==SessionStatus.applied and session.approved_by==uid
        movement=db.query(StockMovement).one()
        assert movement.location_from=='deposito' and movement.quantity_before==10 and movement.quantity_after==9


def test_applied_is_terminal_and_reapply_cannot_restore_a_later_exit(counts):
    factory,_,uid,pid=counts
    sid=start(counts,'loja')
    assert scan(counts,sid,5).status_code==201
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==200
    with factory() as db:
        create_movement(db,uuid.UUID(pid),'exit',2,uid,location='loja');db.commit()
    assert apply(counts,sid).status_code==409
    for target in ('open','counting','reviewing','cancelled','applied'):
        assert status(counts,sid,target).status_code==409
    assert scan(counts,sid,9).status_code==409
    with factory() as db:
        assert db.get(Item,uuid.UUID(pid)).stock_loja==3
        assert db.query(StockMovement).count()==2


def test_counting_requires_review_and_nonempty_session_cannot_bypass_apply_route(counts):
    factory,_,_,_=counts
    sid=start(counts)
    assert apply(counts,sid).status_code==409
    assert status(counts,sid,'reviewing').status_code==409
    assert status(counts,sid,'counting').status_code==200
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==409
    assert status(counts,sid,'applied').status_code==409
    assert scan(counts,sid,3).status_code==409
    assert status(counts,sid,'counting').status_code==200
    assert scan(counts,sid,0).status_code==201
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==200
    with factory() as db:assert db.query(StockMovement).count()==1


def test_cancelled_session_cannot_reopen_or_apply(counts):
    sid=start(counts)
    assert status(counts,sid,'cancelled').status_code==200
    assert status(counts,sid,'counting').status_code==409
    assert scan(counts,sid,3).status_code==409
    assert apply(counts,sid).status_code==409


def test_legacy_count_kept_readable_but_never_inferred_from_location_filter(counts):
    factory,client,uid,pid=counts
    with factory() as db:
        row=InventorySession(name='Legacy',location_filter='deposito',status=SessionStatus.reviewing,created_by=uid)
        db.add(row);db.flush();sid=str(row.id)
        db.add(InventorySessionItem(session_id=row.id,item_id=uuid.UUID(pid),system_quantity=10,counted_quantity=10));db.commit()
    assert client.get(f'/api/inventory/sessions/{sid}').json()['count_location'] is None
    assert scan(counts,sid,4).status_code==409
    assert status(counts,sid,'counting').status_code==409
    r=apply(counts,sid)
    assert r.status_code==409 and 'nova contagem' in r.json()['detail']
    assert status(counts,sid,'cancelled').status_code==200
    with factory() as db:
        original=db.query(InventorySessionItem).one()
        assert original.system_quantity==10 and original.counted_quantity==10
        assert db.query(StockMovement).count()==0


@pytest.mark.parametrize('value',[-1,True,1.2,'2',2147483648,None])
def test_count_quantity_strict_nonnegative_bounded(counts,value):
    sid=start(counts)
    assert scan(counts,sid,value).status_code==422
    with counts[0]() as db:assert db.query(InventorySessionItem).count()==0


@pytest.mark.parametrize('payload',[{}, {'count_location':None},{'count_location':'todos'},{'location_filter':'loja'}])
def test_new_count_requires_explicit_scope(counts,payload):
    assert counts[1].post('/api/inventory/sessions',json={'name':'Teste',**payload}).status_code==422


def test_changed_local_balance_requires_recount_and_refreshes_baseline(counts):
    factory,client,uid,pid=counts
    sid=start(counts,'loja')
    assert scan(counts,sid,6).status_code==201
    assert status(counts,sid,'reviewing').status_code==200
    with factory() as db:
        create_movement(db,uuid.UUID(pid),'exit',2,uid,location='loja');db.commit()
    r=apply(counts,sid)
    assert r.status_code==409 and 'mudou após' in r.json()['detail']
    with factory() as db:
        assert db.get(Item,uuid.UUID(pid)).stock_loja==4
        assert db.query(StockMovement).count()==1
    assert status(counts,sid,'counting').status_code==200
    assert scan(counts,sid,3).status_code==201
    reading=client.get(f'/api/inventory/sessions/{sid}').json()['session_items'][0]
    assert reading['system_quantity']==4 and reading['counted_quantity']==3
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==200
    with factory() as db:assert db.get(Item,uuid.UUID(pid)).stock_loja==3


def test_only_other_location_movement_does_not_make_count_stale(counts):
    factory,_,uid,pid=counts
    sid=start(counts,'deposito');assert scan(counts,sid,3).status_code==201
    with factory() as db:
        create_movement(db,uuid.UUID(pid),'entry',2,uid,location='loja');db.commit()
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==200
    with factory() as db:
        product=db.get(Item,uuid.UUID(pid))
        assert (product.stock_loja,product.stock_deposito,product.current_stock)==(8,3,11)


@pytest.mark.parametrize('other',[None,-1])
def test_missing_or_negative_other_local_balance_is_not_invented(counts,other):
    factory,_,_,pid=counts
    sid=start(counts,'deposito');assert scan(counts,sid,3).status_code==201
    with factory() as db:
        db.get(Item,uuid.UUID(pid)).stock_loja=other;db.commit()
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==409
    with factory() as db:
        assert db.get(Item,uuid.UUID(pid)).stock_loja==other
        assert db.query(StockMovement).count()==0


def test_duplicate_history_not_selected_or_deleted_by_scan_or_apply(counts):
    factory,_,_,pid=counts
    sid=start(counts);assert scan(counts,sid,3).status_code==201
    with factory() as db:
        db.add(InventorySessionItem(session_id=uuid.UUID(sid),item_id=uuid.UUID(pid),system_quantity=4,counted_quantity=9));db.commit()
    assert scan(counts,sid,2).status_code==409
    assert status(counts,sid,'reviewing').status_code==200
    r=apply(counts,sid)
    assert r.status_code==409 and 'duplicadas' in r.json()['detail']
    with factory() as db:
        assert db.query(InventorySessionItem).count()==2
        assert db.query(StockMovement).count()==0
        assert db.get(Item,uuid.UUID(pid)).stock_deposito==4


def test_apply_is_atomic_if_later_product_overflows(counts):
    factory,_,_,pid=counts
    sid=start(counts,'deposito')
    with factory() as db:
        second=item(db,loja=2147483647,deposito=0);second_id=str(second.id);db.commit()
    assert scan(counts,sid,3).status_code==201
    assert scan(counts,sid,1,second_id).status_code==201
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==422
    with factory() as db:
        assert db.query(StockMovement).count()==0
        assert db.get(Item,uuid.UUID(pid)).stock_deposito==4
        assert db.get(Item,uuid.UUID(second_id)).stock_deposito==0
        assert db.get(InventorySession,uuid.UUID(sid)).status==SessionStatus.reviewing


def test_duplicate_barcode_returns_choices_and_bot_does_not_select_first(counts):
    factory,client,uid,pid=counts
    with factory() as db:
        other=item(db,barcode='789001');other_id=str(other.id);db.commit()
    results=client.get('/api/inventory/items/barcode/789001').json()
    assert {row['id'] for row in results}=={pid,other_id}
    with factory() as db:
        message=incoming(db,uid,'Adicione 2 do código 789001 na loja',channel='telegram')
        result=prepare_inventory(db,message,authorized_identity(db,'telegram','123'),'preparar_entrada_estoque',EntryArgs(termo='789001',quantidade=2,local='loja'))
        assert 'erro' in result and len(result['candidatos'])==2
        assert db.query(AssistantAction).count()==0 and db.query(StockMovement).count()==0


def test_bot_repeated_barcode_same_batch_rejected_in_preview_and_confirmation(counts):
    factory,_,uid,_=counts
    data=ItemsArgs(itens=[{'nome':'Calça','tamanho':'P','codigo_barras':' 999001 '},
                         {'nome':'Vestido','tamanho':'G','codigo_barras':'999001'}])
    with factory() as db:
        payload=data.model_dump(mode='json')
        assert len(duplicate_items(db,payload['itens']))==1
        message=incoming(db,uid,'Cadastre estes produtos',channel='telegram')
        result=prepare_inventory(db,message,authorized_identity(db,'telegram','123'),'preparar_itens',data)
        assert 'erro' in result and db.query(AssistantAction).count()==0
        # An older queued preview is revalidated before writing its complete batch.
        action=AssistantAction(source_message_id=message.id,user_id=uid,kind='item_cadastrar',payload=deepcopy(payload))
        db.add(action);db.flush()
        answer=confirm_inventory(db,message,action)
        assert 'Nenhum item foi duplicado' in answer and action.status=='cancelled'
        assert db.query(Item).count()==1 and db.query(StockMovement).count()==0


@pytest.mark.parametrize('field',['current_stock','stock_deposito'])
def test_unknown_total_or_counted_local_balance_blocks_apply(counts,field):
    factory,_,_,pid=counts
    sid=start(counts,'deposito');assert scan(counts,sid,3).status_code==201
    with factory() as db:
        setattr(db.get(Item,uuid.UUID(pid)),field,None);db.commit()
    assert status(counts,sid,'reviewing').status_code==200
    assert apply(counts,sid).status_code==409
    with factory() as db:
        assert getattr(db.get(Item,uuid.UUID(pid)),field) is None
        assert db.query(StockMovement).count()==0


def test_unknown_counted_local_does_not_become_zero_during_scan(counts):
    factory,_,_,pid=counts
    sid=start(counts,'deposito')
    with factory() as db:
        db.get(Item,uuid.UUID(pid)).stock_deposito=None;db.commit()
    assert scan(counts,sid,3).status_code==409
    with factory() as db:assert db.query(InventorySessionItem).count()==0
