"""Operation grouping is a read model; immutable evidence and permissions stay intact."""
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

from app.database import Base
from app.models.access import AuditEvent, now
from app.models.inventory import Item, Supplier, StockMovement
from app.models.pdv import PdvSale, PdvSaleItem, PdvPayment
from app.models.usuario import Usuario
from app.services.user_audit import bind_actor
from app.services.inventory_service import create_movement
from app.services import audit_groups
from test_access import setup, login  # noqa: F401


def event(user_id, **overrides):
    values = dict(user_id=user_id, actor_name='Sol', source='web', action='create', module='pdv',
                  entity='pdv_sales', entity_id=str(uuid.uuid4()), request_id=str(uuid.uuid4()),
                  occurred_at=now(), changes={})
    values.update(overrides)
    return AuditEvent(**values)


def test_rebinding_same_actor_preserves_confirmed_request_but_never_carries_context_between_accounts():
    db=SimpleNamespace(info={})
    user=SimpleNamespace(id=uuid.uuid4(),nome='Sol')
    bind_actor(db,user,source='whatsapp',request_id='message-1',route='/api/pdv/sales',method='POST')
    again=bind_actor(db,user)
    assert again['request_id']=='message-1' and again['source']=='whatsapp'
    assert again['route']=='/api/pdv/sales' and again['method']=='POST'
    different=bind_actor(db,SimpleNamespace(id=uuid.uuid4(),nome='Lucas'))
    assert different['source']=='web'
    assert not {'request_id','route','method'} & set(different)


def seed(factory, ids):
    sale_id, other = str(uuid.uuid4()), str(uuid.uuid4())
    request = str(uuid.uuid4())
    stamp = now() - timedelta(minutes=2)
    with factory() as db:
        rows = [
            event(ids['Sol'][0], entity_id=sale_id, request_id=request, occurred_at=stamp),
            event(ids['Sol'][0], entity='pdv_payments', request_id=request, occurred_at=stamp),
            event(ids['Sol'][0], entity='inventory_items', module='inventory', action='update', request_id=request, occurred_at=stamp),
            event(ids['Lucas'][0], actor_name='Lucas', entity_id=sale_id, action='pdv_edit', occurred_at=stamp+timedelta(minutes=1)),
            event(ids['Sol'][0], entity_id=other, occurred_at=stamp),
            event(ids['Sol'][0], entity='vendas', module='vendas', entity_id=sale_id, occurred_at=stamp),
            event(ids['Sol'][0], action='read', entity_id=sale_id, request_id=request, occurred_at=stamp),
        ]
        db.add_all(rows); db.commit()
    return sale_id, other


def test_sale_lifetime_is_one_group_and_group_pagination_never_truncates_its_details(setup):
    client, factory, ids = setup
    sale, other = seed(factory, ids)
    headers = login(client)
    first = client.get('/api/access/audit?grouped=true&module=pdv&limit=1', headers=headers).json()
    second = client.get('/api/access/audit?grouped=true&module=pdv&limit=1&offset=1', headers=headers).json()
    assert first['total'] == 2 and first['event_total'] == 4
    assert first['events'] == [] and first['grouped'] is True
    assert first['groups'][0]['sale_id'] == sale
    assert first['groups'][0]['event_count'] == 3 and first['groups'][0]['actor_count'] == 2
    assert second['groups'][0]['sale_id'] == other
    details = client.get('/api/access/audit/group', params={'key':'pdv_sale:'+sale, 'limit':2}, headers=headers).json()
    assert details['total'] == 4 and len(details['events']) == 2  # includes the inventory write in this sale
    remaining = client.get('/api/access/audit/group', params={'key':'pdv_sale:'+sale, 'limit':2, 'offset':2}, headers=headers).json()
    assert len(remaining['events']) == 2
    assert {e['id'] for e in details['events']}.isdisjoint(e['id'] for e in remaining['events'])
    assert all(e['action'] != 'read' for e in details['events'] + remaining['events'])
    with factory() as db: assert db.query(AuditEvent).filter_by(action='read').count() == 1


def test_filters_apply_before_grouping_and_detail_not_just_to_samples(setup):
    client, factory, ids = setup
    sale, _ = seed(factory, ids); headers=login(client)
    params={'grouped':True, 'module':'inventory', 'user_id':str(ids['Sol'][0]), 'action':'update'}
    result=client.get('/api/access/audit', params=params, headers=headers).json()
    assert result['total']==1 and result['groups'][0]['key']=='pdv_sale:'+sale
    assert result['groups'][0]['event_count']==1
    assert result['users'][0]['operations']==1
    params.pop('grouped'); params['key']='pdv_sale:'+sale
    details=client.get('/api/access/audit/group',params=params,headers=headers).json()
    assert details['total']==1 and details['events'][0]['module']=='inventory'
    assert client.get('/api/access/audit/group',params={**params,'action':'delete'},headers=headers).status_code==404


def test_unrelated_modules_and_same_time_records_are_not_inferred_as_same_sale(setup):
    client, factory, ids=setup
    sale,_=seed(factory,ids);headers=login(client)
    with factory() as db:
        db.add_all([event(ids['Sol'][0],module='inventory',entity='inventory_items',request_id=None),
                    event(ids['Sol'][0],module='inventory',entity='inventory_items',request_id=None)])
        db.commit()
    result=client.get('/api/access/audit?grouped=true&module=vendas',headers=headers).json()
    assert result['total']==1 and result['groups'][0]['sale_id'] is None
    raw=client.get('/api/access/audit?module=inventory',headers=headers).json()
    grouped=client.get('/api/access/audit?grouped=true&module=inventory',headers=headers).json()
    assert raw['total']==3 and len(raw['events'])==3
    assert grouped['total']==3


def test_group_details_and_group_listing_are_exclusive_to_owner(setup):
    client, factory, ids=setup;sale,_=seed(factory,ids)
    for name in ['Sol','Wissam','Junior']:
        headers=login(client,name)
        assert client.get('/api/access/audit?grouped=true',headers=headers).status_code==403
        assert client.get('/api/access/audit/group',params={'key':'pdv_sale:'+sale},headers=headers).status_code==403
    assert client.get('/api/access/audit/group?key=x').status_code==401


def test_conflicting_legacy_sale_anchors_are_not_guessed(setup):
    client,factory,ids=setup;request=str(uuid.uuid4())
    with factory() as db:
        db.add_all([event(ids['Sol'][0],request_id=request),event(ids['Sol'][0],request_id=request),
                    event(ids['Sol'][0],entity='pdv_payments',request_id=request)])
        db.commit()
    result=client.get('/api/access/audit?grouped=true&module=pdv',headers=login(client)).json()
    assert result['total']==3
    assert len([g for g in result['groups'] if g['kind']=='sale'])==2
    assert len([g for g in result['groups'] if g['key']=='request:'+request])==1


def test_new_stock_events_capture_only_safe_product_balances_and_rollback_leaves_no_history(setup):
    client,factory,ids=setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[Supplier.__table__,Item.__table__,StockMovement.__table__])
        item=Item(name='Camiseta bordada',sku_internal='AUDIT-1',inventory_code='INV-ABC123',stock_loja=2,stock_deposito=7,current_stock=9)
        db.add(item);db.commit();item_id=item.id
        bind_actor(db,db.get(Usuario,ids['Sol'][0]),request_id=str(uuid.uuid4()))
        create_movement(db,item_id,'transfer',3,ids['Sol'][0],location_from='deposito',location_to='loja',reason='PRIVATE customer address')
        db.commit()
        event=db.query(AuditEvent).filter_by(entity='stock_movements').one()
        context=event.changes['_context']
        assert context['product']['name']=='Camiseta bordada' and context['product']['code']=='INV-ABC123'
        assert context['movement']=={'item_id':str(item_id),'movement_type':'transfer','quantity':3,'quantity_before':9,'quantity_after':9,'stock_loja_before':2,'stock_loja_after':5,'location_from':'deposito','location_to':'loja'}
        assert 'PRIVATE' not in json.dumps(event.changes)
        count=db.query(AuditEvent).count()
        create_movement(db,item_id,'adjustment',0,ids['Sol'][0],location='loja');db.rollback()
        assert db.query(AuditEvent).count()==count
    result=client.get('/api/access/audit?grouped=true&module=inventory',headers=login(client)).json()
    assert result['total']==1 and result['groups'][0]['event_count']==2
    assert result['groups'][0]['samples'][0]['entity']=='stock_movements'


def test_new_sale_children_keep_sale_reference_after_raw_rows_are_deleted(setup):
    client,factory,ids=setup
    with factory() as db:
        bind_actor(db,db.get(Usuario,ids['Sol'][0]),request_id=str(uuid.uuid4()))
        sale=PdvSale(total_gs=120,subtotal_gs=120,vendedor_id=ids['Sol'][0])
        db.add(sale);db.flush()
        item=PdvSaleItem(sale_id=sale.id,item_name='Camiseta avulsa',quantity=1,unit_price_gs=120,total_gs=120,is_avulso=True)
        db.add(item);db.commit();sale_id=sale.id
        db.delete(item);db.commit()
    result=client.get('/api/access/audit?grouped=true&module=pdv',headers=login(client)).json()
    assert result['total']==1 and result['groups'][0]['sale_id']==str(sale_id)
    assert result['groups'][0]['event_count']==3
    details=client.get('/api/access/audit/group',params={'key':'pdv_sale:'+str(sale_id)},headers=login(client)).json()
    assert all(e['changes']['_context']['sale_id']==str(sale_id) for e in details['events'])


def test_semantic_anchor_is_bounded_independent_of_stock_samples_and_obeys_filters(setup):
    from sqlalchemy import event as sql_event

    _, factory, ids = setup
    sale, request = str(uuid.uuid4()), str(uuid.uuid4())
    stamp = now() - timedelta(minutes=2)
    with factory() as db:
        db.add(event(ids['Sol'][0], entity_id=sale, request_id=request, occurred_at=stamp,
                     changes={'_context': {'sale_id': sale, 'sale': {'seller_name': 'Sol', 'total_gs': '0', 'usd_rate_gs': '6000'}}}))
        for i in range(100):
            db.add(event(ids['Sol'][0], entity='stock_movements', module='inventory', request_id=request,
                         occurred_at=stamp + timedelta(seconds=i),
                         changes={'_context': {'sale_id': sale, 'movement': {'movement_type': 'exit'}}}))
        db.commit()
        queries = []
        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            queries.append(statement)
        sql_event.listen(db.get_bind(), 'before_cursor_execute', capture)
        try:
            total, groups = audit_groups.grouped(db, audit_groups.scope(db, stamp), 0, 50)
        finally:
            sql_event.remove(db.get_bind(), 'before_cursor_execute', capture)
        assert total == 1 and len(queries) == 3
        group = groups[0]
        assert group['event_count'] == 101 and len(group['samples']) == 3
        assert all(row['entity'] == 'stock_movements' for row in group['samples'])
        assert group['summary_event']['entity'] == 'pdv_sales'
        assert group['summary_event']['changes']['_context']['sale']['total_gs'] == '0'
        assert (group['entity_count'], group['action_count'], group['module_count']) == (2, 1, 2)
        _, filtered = audit_groups.grouped(db, audit_groups.scope(db, stamp, module='inventory'), 0, 50)
        assert filtered[0]['summary_event']['entity'] == 'stock_movements'
        assert filtered[0]['event_count'] == 100 and filtered[0]['module_count'] == 1
        assert db.query(AuditEvent).count() == 101


def test_mixed_movement_cannot_be_classified_from_just_three_samples(setup):
    _, factory, ids = setup
    stamp = now() - timedelta(minutes=2)
    request = str(uuid.uuid4())
    with factory() as db:
        # The oldest entry does not fit in three latest transfer samples.
        db.add(event(ids['Sol'][0], entity='stock_movements', module='inventory', request_id=request,
                     occurred_at=stamp, changes={'_context': {'movement': {'movement_type': 'entry'}}}))
        for i in range(1, 5):
            db.add(event(ids['Sol'][0], entity='stock_movements', module='inventory', request_id=request,
                         occurred_at=stamp + timedelta(seconds=i),
                         changes={'_context': {'movement': {'movement_type': 'transfer'}}}))
        db.commit()
        _, groups = audit_groups.grouped(db, audit_groups.scope(db, stamp), 0, 50)
        assert groups[0]['movement_kind'] is None
        assert all(row['changes']['_context']['movement']['movement_type'] == 'transfer' for row in groups[0]['samples'])
        assert (groups[0]['entity_count'], groups[0]['action_count']) == (1, 1)


def test_product_registration_and_conditional_actions_have_correct_anchors(setup):
    _, factory, ids = setup
    stamp = now() - timedelta(minutes=2)
    product_request, order_request = str(uuid.uuid4()), str(uuid.uuid4())
    with factory() as db:
        db.add_all([
            event(ids['Sol'][0], entity='inventory_items', module='inventory', request_id=product_request, occurred_at=stamp),
            event(ids['Sol'][0], entity='stock_movements', module='inventory', request_id=product_request,
                  occurred_at=stamp + timedelta(seconds=1), changes={'_context': {'movement': {'movement_type': 'entry'}}}),
            event(ids['Sol'][0], entity='pedidos', module='pedidos', action='order_conditional_dispatch', request_id=order_request, occurred_at=stamp),
            event(ids['Sol'][0], entity='stock_movements', module='inventory', request_id=order_request,
                  occurred_at=stamp + timedelta(seconds=1), changes={'_context': {'movement': {'movement_type': 'exit'}}}),
        ])
        db.commit()
        _, groups = audit_groups.grouped(db, audit_groups.scope(db, stamp), 0, 50)
        by_key = {group['key']: group for group in groups}
        assert by_key['request:' + product_request]['summary_event']['entity'] == 'inventory_items'
        assert by_key['request:' + order_request]['summary_event']['action'] == 'order_conditional_dispatch'
        assert all(group['sale_id'] is None for group in groups)


def test_deleted_or_unknown_movement_does_not_report_new_physical_transfer(setup):
    _, factory, ids = setup
    stamp = now() - timedelta(minutes=2)
    with factory() as db:
        for action, changes in [('delete', {'_context': {'movement': {'movement_type': 'transfer'}}}),
                                ('create', {'movement_type': {'changed': True}}),
                                ('create', {'movement_type': {'after': 'transfer'}})]:
            db.add(event(ids['Sol'][0], entity='stock_movements', module='inventory', action=action,
                         occurred_at=stamp, changes=changes))
        db.commit()
        _, groups = audit_groups.grouped(db, audit_groups.scope(db, stamp), 0, 50)
        assert len(groups) == 3
        assert sum(group['movement_kind'] == 'transfer' for group in groups) == 1
        assert next(group for group in groups if group['summary_event']['action'] == 'delete')['movement_kind'] is None
