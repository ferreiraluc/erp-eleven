"""Real routes, isolated sale/stock/fiado data, no financial providers."""
import uuid
from decimal import Decimal
import pytest
from test_pdv_unknown_stock import pdv_app, make_item, sale_payload, balances
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.pdv import PdvSale,PdvSaleItem,PdvPayment,PdvFiadoMovement,PdvSaleEvent,PdvCliente
from app.models.inventory import Item,StockMovement
from app.models.access import AuditEvent


def sold(fixture, quantity=2, method='cash_gs'):
    factory,client,cid=fixture
    with factory() as db:
        rid=make_item(db).id;db.commit()
    body=sale_payload([rid],cid);body['items'][0]['quantity']=quantity
    body['payments'][0].update(method=method,amount_original=100*quantity,amount_gs=100*quantity)
    response=client.post('/api/pdv/sales',json=body);assert response.status_code==201,response.text
    sid=response.json()['id']
    return rid,sid,client.get('/api/pdv/management/'+sid).json()


def command(operation,**fields):return {'operation':operation,'reason':'Conferência da venda de teste',**fields}

def review(client,sid,body):
    result=client.post(f'/api/pdv/management/{sid}/preview',json=body)
    assert result.status_code==200,result.text
    return {'command':body,'plan_token':result.json()['plan_token'],'request_id':str(uuid.uuid4()),'confirm':True},result.json()


def apply(client,sid,body):
    request,preview=review(client,sid,body)
    result=client.post(f'/api/pdv/management/{sid}/commit',json=request)
    assert result.status_code==200,result.text
    return request,preview


def test_partial_then_full_return_keeps_receipts_and_only_restock_selected(pdv_app):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app,quantity=3)
    request,p=apply(client,sid,command('return',lines=[{'line_id':data['items'][0]['id'],'quantity':1,'restock':True}]))
    assert p['refund_gs']=='100.00' and p['cash_refund_gs']=='100.00'
    assert client.post(f'/api/pdv/management/{sid}/commit',json=request).json()['replayed']
    with factory() as db:
        assert balances(db,rid)==(8,4,4)
        assert db.get(PdvSale,uuid.UUID(sid)).status=='partially_refunded'
        assert db.query(PdvSaleEvent).count()==1 and db.query(StockMovement).count()==2
    _,p=apply(client,sid,command('cancel',restock=False))
    assert p['refund_gs']=='200.00' and p['stock']==[]
    with factory() as db:
        s=db.get(PdvSale,uuid.UUID(sid))
        assert s.status=='cancelled' and not s.stock_applied and s.refunded_gs==300
        assert balances(db,rid)==(8,4,4)
        assert db.query(PdvPayment).one().amount_gs==300
        assert db.query(PdvSaleEvent).count()==2
    assert client.get('/api/pdv/management').json()['summary']['net_gs']==0


def test_fiado_reversal_uses_posted_debt_and_preserves_prior_receipt(pdv_app):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app,method='fiado')
    assert client.post(f'/api/pdv/clients/{cid}/fiado/payment',json={'valor_gs':210}).status_code==200
    _,p=apply(client,sid,command('return',lines=[{'line_id':data['items'][0]['id'],'quantity':1,'restock':True}]))
    assert p['fiado_credit_gs']=='100.00' and p['cash_refund_gs']=='0.00'
    assert p['warnings']
    with factory() as db:
        assert db.get(PdvCliente,cid).saldo_fiado_gs==Decimal('-90')
        assert db.query(PdvFiadoMovement).filter_by(tipo='payment').one().valor_gs==210
        assert db.query(PdvFiadoMovement).filter_by(tipo='credit').one().valor_gs==100
        assert db.query(PdvPayment).one().amount_gs==200


def edit_body(data):
    return {key:data[key] for key in ['vendedor_id','cliente_id','cliente_nome','items','desconto_gs','payments','notas']}


def test_edit_replaces_product_values_and_customer_debt_atomically(pdv_app):
    factory,client,cid=pdv_app
    old,sid,data=sold(pdv_app,method='fiado')
    with factory() as db:
        new=make_item(db).id
        customer=PdvCliente(nome='Cliente correto',saldo_fiado_gs=0);db.add(customer);db.flush();new_cid=customer.id;db.commit()
    edit=edit_body(data);edit['cliente_id']=str(new_cid)
    edit['items'][0].update(item_id=str(new),quantity=3,unit_price_gs=120,item_name='Nome errado do navegador')
    edit['payments'][0].update(amount_original=360,amount_gs=360)
    request,p=apply(client,sid,command('edit',edit=edit))
    with factory() as db:
        assert balances(db,old)==(10,6,4) and balances(db,new)==(7,3,4)
        assert db.get(PdvCliente,cid).saldo_fiado_gs==20 and db.get(PdvCliente,new_cid).saldo_fiado_gs==360
        s=db.get(PdvSale,uuid.UUID(sid));assert s.total_gs==360 and s.version==2
        assert s.items[0].item_name=='Produto sintético'
        event=db.query(PdvSaleEvent).one()
        assert event.before['items'][0]['item_id']==str(old) and event.before['total_gs']=='200.00'
        assert event.after['items'][0]['item_id']==str(new)
        assert db.query(AuditEvent).filter_by(action='pdv_edit').count()==1
    assert client.post(f'/api/pdv/management/{sid}/commit',json=request).json()['replayed']

    # The original product remains discoverable even after its current sale line
    # was replaced; the revision explains the former value without inventing a sale.
    from app.database import Base
    from app.models.inventory import InventorySession,InventorySessionItem
    from app.services.inventory_history import product_history
    with factory() as db:
        Base.metadata.create_all(db.bind,tables=[InventorySession.__table__,InventorySessionItem.__table__])
        history=product_history(db,old,db.query(Usuario).one(),section='sales')
        assert history['total']==1 and history['rows'][0]['lines'][0]['link']=='revision'
        assert history['rows'][0]['lines'][0]['total_gs']=='200.00'


@pytest.mark.parametrize('change',['stock','sale','fiado','reason'])
def test_stale_review_rejects_without_effects(pdv_app,change):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app,method='fiado')
    request,_=review(client,sid,command('cancel'))
    if change=='reason':request['command']['reason']='Outro motivo de edição'
    else:
        with factory() as db:
            if change=='stock':db.get(Item,rid).stock_loja+=1;db.get(Item,rid).current_stock+=1
            elif change=='sale':db.get(PdvSale,uuid.UUID(sid)).notas='Mudou durante revisão'
            else:db.get(PdvCliente,cid).saldo_fiado_gs+=1
            db.commit()
    assert client.post(f'/api/pdv/management/{sid}/commit',json=request).status_code==409
    with factory() as db:assert db.query(PdvSaleEvent).count()==0 and db.get(PdvSale,uuid.UUID(sid)).status=='completed'


def test_delete_cancels_then_hides_without_destroying_history(pdv_app):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app)
    apply(client,sid,command('delete'))
    assert client.get('/api/pdv/management').json()['total']==0
    archived=client.get('/api/pdv/management?deleted=true').json()
    assert archived['total']==1 and archived['summary']['net_gs']==0
    assert client.get('/api/pdv/sales').json()==[]
    with factory() as db:
        assert balances(db,rid)==(10,6,4)
        assert db.query(PdvSaleItem).count()==db.query(PdvPayment).count()==1
        assert db.query(PdvSaleEvent).one().operation=='delete'
    assert client.get('/api/pdv/management/'+sid).json()['deleted_at']


def test_read_scope_and_all_mutations_are_owner_only(pdv_app):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app)
    request,_=review(client,sid,command('cancel'))
    with factory() as db:
        user=db.query(Usuario).one();user.role=UsuarioRole.GERENTE;user.email='junior@eleven.com';user.sales_scope='own';uid=user.id
        other=Usuario(nome='Colega',email='colleague@test',senha_hash='unused');db.add(other);db.flush()
        s=PdvSale(vendedor_id=other.id,status='completed',total_gs=999);db.add(s);db.flush();other_sid=s.id;db.commit()
    assert client.get('/api/pdv/management').json()['total']==1
    assert client.get('/api/pdv/management/'+str(other_sid)).status_code==404
    assert client.get('/api/pdv/management/'+sid).json()['events']==[]
    assert client.get('/api/pdv/management?deleted=true').status_code==403
    assert client.post(f'/api/pdv/management/{sid}/preview',json=command('cancel')).status_code==403
    assert client.post(f'/api/pdv/management/{sid}/commit',json=request).status_code==403
    assert client.post(f'/api/pdv/sales/{sid}/cancel').status_code==403
    # Operational users can still create sales normally.
    assert client.post('/api/pdv/sales',json=sale_payload([rid],cid)).status_code==201


@pytest.mark.parametrize('bad',['excess_qty','foreign_line','duplicate_line','negative_price','bad_payments','bad_fx','insufficient_stock'])
def test_invalid_corrections_make_no_changes(pdv_app,bad):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app)
    if bad in ('excess_qty','foreign_line','duplicate_line'):
        line={'line_id':str(uuid.uuid4()) if bad=='foreign_line' else data['items'][0]['id'],'quantity':3 if bad=='excess_qty' else 1}
        body=command('return',lines=[line,line] if bad=='duplicate_line' else [line])
    else:
        edit=edit_body(data)
        if bad=='negative_price':edit['items'][0]['unit_price_gs']=-10
        if bad=='bad_payments':edit['payments'][0]['amount_gs']=150
        if bad=='bad_fx':edit['payments'][0]['exchange_rate']=2
        if bad=='insufficient_stock':edit['items'][0]['quantity']=99;edit['payments'][0].update(amount_original=9900,amount_gs=9900)
        body=command('edit',edit=edit)
    result=client.post(f'/api/pdv/management/{sid}/preview',json=body)
    assert result.status_code in (409,422),result.text
    with factory() as db:
        assert balances(db,rid)==(8,4,4) and db.query(PdvSaleEvent).count()==0
        assert db.query(PdvPayment).one().amount_gs==200


def test_discount_rounding_is_exact_across_sequential_partial_returns(pdv_app):
    factory,client,cid=pdv_app
    rid,sid,data=sold(pdv_app,quantity=3)
    edit=edit_body(data);edit['desconto_gs']='299.98';edit['payments'][0].update(amount_original='.02',amount_gs='.02')
    apply(client,sid,command('edit',edit=edit))
    data=client.get('/api/pdv/management/'+sid).json();line=data['items'][0]['id']
    refunds=[]
    for _ in range(3):
        _,p=apply(client,sid,command('return',lines=[{'line_id':line,'quantity':1,'restock':True}]))
        refunds.append(Decimal(p['refund_gs']))
    assert sum(refunds)==Decimal('.02')
    with factory() as db:
        assert db.get(PdvSale,uuid.UUID(sid)).status=='refunded' and balances(db,rid)==(10,6,4)


@pytest.mark.parametrize('mismatch',['underpaid','fiado_ledger'])
def test_refund_rejects_inconsistent_original_payments_without_stock_effects(pdv_app,mismatch):
    factory,client,cid=pdv_app
    rid,sid,_=sold(pdv_app,method='fiado' if mismatch=='fiado_ledger' else 'cash_gs')
    with factory() as db:
        if mismatch=='underpaid':db.query(PdvPayment).one().amount_gs=100
        else:db.query(PdvFiadoMovement).filter_by(sale_id=uuid.UUID(sid),tipo='debit').one().valor_gs=100
        db.commit()
    response=client.post(f'/api/pdv/management/{sid}/preview',json=command('cancel'))
    assert response.status_code==409,response.text
    with factory() as db:
        assert balances(db,rid)==(8,4,4)
        assert db.get(PdvSale,uuid.UUID(sid)).status=='completed'
        assert db.query(PdvSaleEvent).count()==0 and db.query(StockMovement).count()==1
