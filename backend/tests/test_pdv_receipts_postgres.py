"""New printer defaults preserve existing A4 agents on real PostgreSQL."""
import pytest
from sqlalchemy.exc import IntegrityError
from test_access_postgres import pg, upgrade
from test_pdv_stock_postgres import pdv_pg, item, payload


def test_receipt_printer_migration_preserves_a4_and_limits_auto_destination(pg):
    engine,schema=pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE print_devices (id integer primary key, name text, token_hash text, active boolean)')
        conn.exec_driver_sql("INSERT INTO print_devices VALUES (1,'Samsung','keep',true)")
        upgrade(conn,'h0c1d2e3f4a5_receipt_printer.py')
        assert tuple(conn.exec_driver_sql('SELECT id,name,token_hash,active,purpose,auto_receipts FROM print_devices').one()) == (1,'Samsung','keep',True,'documents',False)
        conn.exec_driver_sql("INSERT INTO print_devices (id,name,purpose,auto_receipts) VALUES (2,'Zebra','tickets',true)")
        assert conn.exec_driver_sql('SELECT paper_width_mm,paper_height_mm FROM print_devices WHERE id=2').one()==(60,80)
        with pytest.raises(IntegrityError),conn.begin_nested():
            conn.exec_driver_sql("INSERT INTO print_devices (id,name,purpose,auto_receipts) VALUES (3,'Other','tickets',true)")
        conn.exec_driver_sql("INSERT INTO print_devices (id,name) VALUES (4,'Documentos')")


def test_concurrent_receipt_requests_dispatch_one_job(pdv_pg):
    from concurrent.futures import ThreadPoolExecutor
    import uuid
    from app.database import Base
    from app.models.printing import PrintDevice, PrintJob
    factory, client, customer, _, _ = pdv_pg
    with factory() as db:
        Base.metadata.create_all(db.get_bind())
        db.add(PrintDevice(name='Synthetic Zebra',token_hash='a'*64,purpose='tickets',auto_receipts=True))
        db.commit()
    product=item(factory)
    sold=client.post('/api/pdv/sales',json=payload(customer,[(product,1,'loja')])).json()
    url=f"/api/pdv/sales/{sold['id']}/receipt"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:client.post(url),range(2)))
    assert [r.status_code for r in results]==[200,200], [r.text for r in results]
    assert results[0].json()['job']['id']==results[1].json()['job']['id']
    with factory() as db:
        assert db.query(PrintJob).count()==1
        db.query(PrintJob).one().status='uncertain';db.commit()
    keys=[str(uuid.uuid4()),str(uuid.uuid4())]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda k:client.post(url,params={'copy_key':k,'confirm_copy':True}),keys))
    assert sorted(r.status_code for r in results)==[200,409]
    with factory() as db:
        assert db.query(PrintJob).count()==2


def test_ticket_prefix_search_uses_uuid_bounds_in_postgres(pdv_pg):
    import uuid
    from app.models.pdv import PdvSale
    factory,client,customer,_,_=pdv_pg
    product=item(factory)
    sale=client.post('/api/pdv/sales',json=payload(customer,[(product,1,'loja')])).json()
    prefix=sale['id'].replace('-','')[:10].upper()
    with factory() as db:
        source=db.get(PdvSale,uuid.UUID(sale['id']))
        collision=PdvSale(id=uuid.UUID(prefix+'0'*22),vendedor_id=source.vendedor_id,status='completed')
        db.add(collision);db.commit();other_id=str(collision.id)
    results=client.get('/api/pdv/management',params={'q':prefix}).json()
    assert {row['id'] for row in results['items']}=={sale['id'],other_id}
