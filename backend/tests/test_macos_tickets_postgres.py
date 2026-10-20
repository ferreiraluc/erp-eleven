import uuid
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from time import monotonic, sleep
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest
from test_access_postgres import pg, upgrade
from test_pdv_stock_postgres import pdv_pg


def test_migration_keeps_existing_windows_and_jobs(pg):
    engine, schema = pg
    with engine.begin() as conn:
        conn.exec_driver_sql(f'SET LOCAL search_path TO {schema}')
        conn.exec_driver_sql('CREATE TABLE print_devices(id int primary key, name text, auto_receipts boolean)')
        conn.exec_driver_sql("INSERT INTO print_devices VALUES (1,'Zebra',true),(2,'Samsung',false)")
        conn.exec_driver_sql('CREATE TABLE print_jobs(id int primary key, status text)')
        conn.exec_driver_sql("INSERT INTO print_jobs VALUES (1,'claimed'),(2,'submitted')")
        upgrade(conn,'n6c7d8e9f0a1_macos_receipt_agent.py')
        assert conn.exec_driver_sql('SELECT driver FROM print_devices').scalars().all() == ['windows','windows']
        assert conn.exec_driver_sql('SELECT name,auto_receipts FROM print_devices ORDER BY id').all() == [('Zebra',True),('Samsung',False)]
        assert conn.exec_driver_sql('SELECT status,claim_key FROM print_jobs ORDER BY id').all() == [('claimed',None),('submitted',None)]
        key=str(uuid.uuid4())
        conn.exec_driver_sql("UPDATE print_jobs SET claim_key=%s WHERE id=1",(key,))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.exec_driver_sql("UPDATE print_jobs SET claim_key=%s WHERE id=2",(key,))


def test_concurrent_mac_claims_recover_one_job(pdv_pg):
    from app.database import Base
    from app.api.endpoints import printing
    from app.models.printing import PrintJob
    factory, client, _, _, _ = pdv_pg
    with factory() as db: Base.metadata.create_all(db.get_bind())
    client.app.include_router(printing.router, prefix='/api/printing')
    device=client.post('/api/printing/receipt-device/macos').json()
    headers={'Authorization':'Bearer '+device['token']}
    requested=client.post(f"/api/printing/receipt-devices/{device['device']['id']}/test",
                          json={'confirm':True,'request_key':str(uuid.uuid4())})
    assert requested.status_code == 200, requested.text
    params={'driver':'escpos_tcp','continuous_tickets':True,'claim_key':str(uuid.uuid4())}
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers=list(pool.map(lambda _:client.post('/api/printing/agent/claim',headers=headers,params=params),range(2)))
    assert [r.status_code for r in answers] == [200,200], [r.text for r in answers]
    assert answers[0].json() == answers[1].json()
    with factory() as db: assert db.query(PrintJob).count() == 1


def test_checkout_waiting_on_cutover_sees_new_destination(pdv_pg):
    from app.database import Base
    from app.models.printing import PrintDevice
    from app.services.pdv_receipts import destination
    factory, _, _, _, _ = pdv_pg
    old_id, new_id = uuid.uuid4(), uuid.uuid4()
    with factory() as db:
        Base.metadata.create_all(db.get_bind())
        db.add_all([
            PrintDevice(id=old_id, name='Synthetic Zebra', purpose='tickets',
                        token_hash=uuid.uuid4().hex, auto_receipts=True),
            PrintDevice(id=new_id, name='Synthetic Mac', purpose='tickets',
                        token_hash=uuid.uuid4().hex, driver='escpos_tcp'),
        ])
        db.commit()
    pids = Queue()
    def checkout():
        with factory() as db:
            pids.put(db.execute(text('SELECT pg_backend_pid()')).scalar_one())
            device = destination(db, lock=True)
            return device.id if device else None
    with factory() as cutover, ThreadPoolExecutor(max_workers=1) as pool:
        old = cutover.query(PrintDevice).filter_by(id=old_id).with_for_update().one()
        future = pool.submit(checkout)
        pid = pids.get(timeout=5)
        try:
            deadline = monotonic()+5
            with factory() as observer:
                while not observer.execute(
                        text('SELECT cardinality(pg_blocking_pids(:pid))'), {'pid':pid}).scalar_one():
                    assert monotonic() < deadline, 'Checkout did not wait for the destination lock'
                    sleep(.02)
            old.auto_receipts = False
            cutover.flush()
            cutover.get(PrintDevice, new_id).auto_receipts = True
            cutover.commit()
        finally:
            cutover.rollback()
        assert future.result(timeout=5) == new_id
