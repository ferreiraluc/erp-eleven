"""Synthetic products only: no external APIs, real printing or production DB."""
import hashlib
import io
import uuid
from datetime import timedelta
from zipfile import ZipFile

import pytest
from sqlalchemy import event

from app.api.endpoints import inventory_labels, inventory
from app.database import Base
from app.dependencies import get_current_active_user
from app.models.assistant import utcnow
from app.models.inventory import Item, StockMovement
from app.models.inventory_receiving import ReceivingLot, ReceivingLotItem
from app.models.printing import PrintDevice, PrintJob
from app.models.usuario import Usuario, UsuarioRole
from app.services import product_labels as labels
from test_pdv_receipts import tickets, configure
from test_pdv_unknown_stock import pdv_app, make_item


@pytest.fixture
def label_env(tickets):
    factory, client, _ = tickets
    client.app.include_router(inventory_labels.router, prefix='/api/inventory-labels')
    client.app.include_router(inventory.router, prefix='/api/inventory')
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[ReceivingLot.__table__, ReceivingLotItem.__table__])
        a = make_item(db); a.name = 'T-shirt Branco S'; a.size = 'S'; a.color = 'Branco'; a.group_key = 'T-shirt'
        b = make_item(db); b.name = 'T-shirt Azul M'; b.size = 'M'; b.color = 'Azul'; b.group_key = 'T-shirt'
        c = make_item(db); c.name = 'Outra peça'; c.image_data = 'not-read' * 1000
        lot = ReceivingLot(name='Leva 1', notes='Synthetic', received_on=utcnow().date(),
                           request_fingerprint='a'*64, created_by=db.query(Usuario).first().id)
        db.add(lot); db.flush()
        db.add(ReceivingLotItem(lot_id=lot.id, item_id=b.id, item_name=b.name, item_sku=b.sku_internal, created_by=lot.created_by))
        db.commit()
        ids, lot_id = [str(a.id), str(b.id), str(c.id)], str(lot.id)
    return factory, client, ids, lot_id


def selection(client, ids):
    response = client.post('/api/inventory-labels/selection', json={'item_ids': ids})
    assert response.status_code == 200, response.text
    return response.json()['items']


def payload(client, ids, copies=1):
    return dict(request_key=str(uuid.uuid4()), confirm=True, items=[dict(
        item_id=p['id'], code=p['inventory_code'], name=p['name'], color=p['color'], size=p['size'], copies=copies)
        for p in selection(client, ids)])


def setup_device(client):
    response = client.post('/api/inventory-labels/device', json={'confirm': True})
    assert response.status_code == 200, response.text
    return response.json()


def enqueue(client, body):
    response = client.post('/api/inventory-labels/batches', json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_grade_and_lot_union_is_deduplicated_without_images(label_env):
    factory, client, ids, lot_id = label_env
    statements = []
    engine = factory.kw['bind']
    def record(conn, cursor, statement, *args): statements.append(statement)
    event.listen(engine, 'before_cursor_execute', record)
    try:
        response = client.post('/api/inventory-labels/selection', json={
            'item_ids': [ids[0]], 'group_keys': ['T-shirt'], 'lot_ids': [lot_id]})
        assert response.status_code == 200, response.text
        assert {i['id'] for i in response.json()['items']} == set(ids[:2])
        assert not any('image_data' in sql or 'additional_images' in sql for sql in statements)
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert client.get('/api/inventory-labels/catalog', params={'mode': 'grades'}).json()['total'] == 1
    assert client.get('/api/inventory-labels/catalog', params={'mode': 'lots'}).json()['total'] == 1
    assert client.get('/api/inventory-labels/catalog').json()['total'] == 3


def test_cutover_requires_active_mac_empty_queue_and_revokes_old_token(label_env):
    factory, client, _, _ = label_env
    old = configure(client)
    a4 = client.post('/api/printing/devices', json={'name': 'Samsung A4'}).json()
    assert client.post('/api/inventory-labels/device', json={'confirm': True}).status_code == 409
    with factory() as db:
        db.get(PrintDevice, uuid.UUID(old['device']['id'])).auto_receipts = False
        db.flush()
        mac = PrintDevice(name='3nStar', purpose='tickets', driver='escpos_tcp', auto_receipts=True, token_hash='f'*64)
        db.add(mac); db.commit(); mac_id = mac.id
        job = PrintJob(device_id=uuid.UUID(old['device']['id']), user_id=db.query(Usuario).first().id,
                       request_key=uuid.uuid4(), source='pdv_receipt', pdf=b'', sha256='', status='pending', expires_at=utcnow()+timedelta(days=1))
        db.add(job); db.commit(); jid=job.id
    assert client.post('/api/inventory-labels/device', json={'confirm': True}).status_code == 409
    with factory() as db:
        db.get(PrintJob, jid).status = 'submitted'; db.commit()
    new = setup_device(client)
    assert new['device']['id'] == old['device']['id']
    assert client.post('/api/printing/agent/connect', headers={'Authorization': 'Bearer '+old['token']}, json={'name': 'Zebra', 'profile': 'tickets'}).status_code == 401
    assert setup_device(client)['token'] is None
    assert client.put('/api/printing/receipt-device', json={'name': 'Zebra', 'auto_receipts': True}).status_code == 409
    with factory() as db:
        assert db.get(PrintJob, jid).source == 'pdv_receipt'
        assert db.get(PrintDevice, mac_id).auto_receipts is True
        assert db.get(PrintDevice, uuid.UUID(a4['id'])).purpose == 'documents'


def test_confirmed_batch_is_atomic_idempotent_and_preserves_stock(label_env):
    factory, client, ids, _ = label_env
    setup_device(client)
    body = payload(client, ids[:2], 3)
    assert client.post('/api/inventory-labels/batches', json={**body, 'confirm': False}).status_code == 422
    batch = enqueue(client, body)
    assert batch['total'] == 6 and len(batch['jobs']) == 2
    assert enqueue(client, body) == batch
    changed = {**body, 'items': [{**body['items'][0], 'copies': 4}]}
    assert client.post('/api/inventory-labels/batches', json=changed).status_code == 409
    with factory() as db:
        assert db.query(PrintJob).count() == 2
        assert db.query(StockMovement).count() == 0
        assert all(i.current_stock == 10 for i in db.query(Item))
        db.get(Item, uuid.UUID(ids[0])).name = 'Nome alterado'; db.commit()
    assert enqueue(client, body)['id'] == batch['id']  # replay retains original snapshot
    stale = {**body, 'request_key': str(uuid.uuid4())}
    assert client.post('/api/inventory-labels/batches', json=stale).status_code == 409
    with factory() as db: assert db.query(PrintJob).count() == 2


def test_queue_claim_recovery_cancel_and_no_expiry_or_wrong_profile(label_env):
    factory, client, ids, _ = label_env
    device = setup_device(client)
    headers = {'Authorization': 'Bearer '+device['token']}
    body = payload(client, ids[:2])
    batch = enqueue(client, body)
    assert client.post('/api/printing/agent/connect', headers=headers, json={'name': 'Zebra', 'profile': 'tickets'}).status_code == 409
    assert client.post('/api/printing/agent/connect', headers=headers, json={'name': 'Zebra', 'profile': 'product_labels'}).status_code == 200
    assert client.post('/api/printing/agent/claim', headers=headers).status_code == 409
    with factory() as db:
        for job in db.query(PrintJob): job.expires_at = utcnow()-timedelta(days=1)
        db.commit()
    params = {'product_labels': True, 'claim_key': str(uuid.uuid4())}
    claim = client.post('/api/printing/agent/claim', headers=headers, params=params).json()
    assert claim['id'] == batch['jobs'][0]['id'] and claim['format'] == 'zpl'
    assert client.post('/api/printing/agent/claim', headers=headers, params=params).json() == claim
    assert client.post('/api/printing/agent/claim', headers=headers, params={**params, 'claim_key': str(uuid.uuid4())}).status_code == 409
    document = client.get(f"/api/printing/agent/jobs/{claim['id']}/zpl", headers=headers)
    assert hashlib.sha256(document.content).hexdigest() == claim['sha256']
    assert client.get(f"/api/printing/agent/jobs/{claim['id']}/pdf", headers=headers).status_code == 409
    cancelled = client.post(f"/api/inventory-labels/batches/{batch['id']}/cancel", json={'confirm': True}).json()
    assert [j['status'] for j in cancelled['jobs']] == ['claimed', 'cancelled']
    assert client.post(f"/api/printing/agent/jobs/{claim['id']}/result", headers=headers, json={
        'status': 'uncertain', 'diagnostic': {'code': 'label_send_uncertain', 'agent_version': '2026.10.21.1'}}).status_code == 200
    assert client.post('/api/printing/agent/claim', headers=headers, params={**params, 'claim_key': str(uuid.uuid4())}).status_code == 204


def test_zpl_escapes_text_uses_qr_and_fixed_media(label_env):
    _, client, ids, _ = label_env
    row = selection(client, ids[:1])[0]
    snap = dict(code=row['inventory_code'], copies=7, name='Camiseta ^XZ ~JA _A1 Ç', color='Azul', size='2XL')
    data = labels.render_zpl(snap).decode('ascii')
    assert data.count('^XZ') == 1 and '~JA' not in data and '_5E_58_5A' in data
    assert '^MNY' in data and '^PW480^LL240' in data and '^BQN,2,5' in data
    assert '^PQ7,0,1,N' in data and f"^FDMA,{row['inventory_code']}^FS" in data
    assert all(x < 480 and y+h <= 240 for x, y, h, _ in labels.layout(snap))
    preview = client.get('/api/inventory-labels/preview/'+ids[0])
    assert preview.status_code == 200 and '<svg' in preview.text and row['inventory_code'] in preview.text


def test_internal_scan_exact_not_manufacturer_collision_or_deleted_product(label_env):
    factory, client, ids, _ = label_env
    code = selection(client, ids[:1])[0]['inventory_code']
    with factory() as db:
        db.get(Item, uuid.UUID(ids[1])).barcode = code
        db.commit()
    url = '/api/inventory/items/barcode/'+code
    assert [p['id'] for p in client.get(url, params={'include_images': False}).json()] == ids[:1]
    assert [p['id'] for p in client.get('/api/inventory-labels/catalog', params={'q': code.lower()}).json()['items']] == ids[:1]
    with factory() as db:
        db.get(Item, uuid.UUID(ids[0])).deleted_at = utcnow(); db.commit()
    assert client.get(url, params={'include_images': False}).json() == []


def test_limits_permissions_and_installer(label_env):
    factory, client, ids, _ = label_env
    setup_device(client)
    body = payload(client, ids)
    assert client.post('/api/inventory-labels/batches', json={**body, 'items': body['items']*2}).status_code == 422
    assert client.post('/api/inventory-labels/batches', json={**body, 'items': [{**body['items'][0], 'copies': 101}]}).status_code == 422
    own_batch = enqueue(client, body)
    with factory() as db:
        staff = Usuario(nome='Funcionário', email='staff@synthetic.invalid', role=UsuarioRole.GERENTE, senha_hash='unused')
        db.add(staff); db.commit(); db.refresh(staff); db.expunge(staff)
    client.app.dependency_overrides[get_current_active_user] = lambda: staff
    assert client.post('/api/inventory-labels/device', json={'confirm': True}).status_code == 403
    assert client.get('/api/inventory-labels/batches/'+own_batch['id']).status_code == 404
    assert client.get('/api/inventory-labels/batches').json() == []
    assert enqueue(client, {**body, 'request_key': str(uuid.uuid4())})['total'] == 3


def test_label_installer_keeps_profile_and_contains_no_credentials(label_env):
    _, client, _, _ = label_env
    result = client.get('/api/printing/agent-package', params={'profile': 'product_labels'})
    assert result.status_code == 200
    with ZipFile(io.BytesIO(result.content)) as archive:
        assert all('config.json' not in name and 'journal' not in name for name in archive.namelist())
        assert '-Profile product_labels' in archive.read('Eleven-Impressao/Instalar.cmd').decode()
        assert "$AgentProfile = 'product_labels'" in archive.read('Eleven-Impressao/Instalar.ps1').decode()
        assert 'Eleven-Impressao/AgenteEtiquetas.ps1' in archive.namelist()
