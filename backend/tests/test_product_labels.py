"""Synthetic products only: no external APIs, real printing or production DB."""
import hashlib
import io
import re
import uuid
from datetime import timedelta
from decimal import Decimal
from zipfile import ZipFile

import pytest
from PIL import Image, ImageChops
from reportlab.graphics.barcode.qr import QrCodeWidget
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
        a.sale_price = Decimal('149.90'); a.sale_currency = 'BRL'; a.barcode = '7891234567890'
        b = make_item(db); b.name = 'T-shirt Azul M'; b.size = 'M'; b.color = 'Azul'; b.group_key = 'T-shirt'
        b.sale_price = Decimal('0.00'); b.sale_currency = 'USD'
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
        item_id=p['id'], code=p['inventory_code'], name=p['name'], color=p['color'], size=p['size'],
        sale_price=p['sale_price'], sale_currency=p['sale_currency'], copies=copies)
        for p in selection(client, ids)])


def zpl_text_fields(payload):
    """Read only user-visible UTF-8 fields; QR data is checked separately."""
    return [bytes.fromhex(value.replace('_', '')).decode('utf-8') for value in
            re.findall(r'\^FH_\^FD((?:_[0-9A-F]{2})+)\^FS', payload.decode('ascii'))]


def raster_from_zpl(payload):
    match = re.search(rb'\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS', payload)
    assert match, 'Expected Zebra ASCII-hex graphic'
    total, repeated, stride = map(int, match.group(1, 2, 3))
    assert (total, repeated, stride) == (14400, 14400, 60)
    packed = bytes.fromhex(match.group(4).decode('ascii'))
    assert len(packed) == total
    return Image.frombytes('1', (480, 240), bytes(byte ^ 0xff for byte in packed))


def raster_from_preview(png):
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    return Image.open(io.BytesIO(png)).convert('1')


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
    assert preview.status_code == 200 and preview.headers['content-type'] == 'image/png'
    assert raster_from_preview(preview.content).size == (480, 240)


def test_new_layout_snapshots_sale_price_and_optional_barcode(label_env):
    factory, client, ids, _ = label_env
    setup_device(client)
    row = selection(client, ids[:1])[0]
    assert row['sale_price'] == '149.90' and row['sale_currency'] == 'BRL'
    body = payload(client, ids[:1], copies=2)
    batch = enqueue(client, body)
    with factory() as db:
        snap = db.get(PrintJob, uuid.UUID(batch['jobs'][0]['id'])).snapshot
    assert snap['layout_version'] == 4
    assert snap['sale_price'] == '149.90' and snap['sale_currency'] == 'BRL'
    assert snap['barcode'] == '7891234567890'
    data = labels.render_zpl(snap)
    fields = zpl_text_fields(data)
    assert data.startswith(b'^XA^CI28^MNY') and b'^PW480^LL240' in data
    assert data.endswith(b'^XZ') and b'^PQ2,0,1,N' in data
    assert not fields and b'^A0' not in data and b'^GFA,14400,14400,60,' in data
    assert len(data) <= 32768  # Windows RAW-agent guard
    preview = client.get('/api/inventory-labels/preview/'+ids[0])
    assert preview.status_code == 200 and preview.headers['content-type'] == 'image/png'
    image = raster_from_zpl(data)
    assert image.tobytes() == raster_from_preview(preview.content).tobytes()
    for field, changed in (('name', 'Outro nome'), ('size', 'XL'), ('color', 'Preto'),
                           ('barcode', '9876543210'), ('sale_price', '0')):
        altered = {**snap, field: changed}
        assert image.tobytes() != raster_from_zpl(labels.render_zpl(altered)).tobytes()


def test_new_layout_qr_is_internal_code_with_quiet_zone_and_zpl_is_not_injectable():
    snap = dict(layout_version=4, code='INV-A7K4P2', copies=7,
                name='Camiseta ^XZ ~JA _A1 Ç', color='Azul', size='2XL',
                barcode='7891234567890', sale_price='149.90', sale_currency='BRL')
    data = labels.render_zpl(snap)
    assert data.count(b'^XZ') == 1 and b'~JA' not in data
    assert data.startswith(b'^XA^CI28^MNY') and data.endswith(b'^XZ')
    assert b'^PW480^LL240' in data and b'^PQ7,0,1,N' in data
    assert len(data) <= 32768
    image = raster_from_zpl(data)
    assert image.size == (480, 240)
    for x, y in ((336, 51), (347, 62), (435, 63), (348, 150), (446, 162)):
        assert image.getpixel((x, y)) == 255
    qr = QrCodeWidget(snap['code'], barLevel='M', qrVersion=3)
    qr.qr.make()
    assert len(qr.qr.modules) == 29
    for row, modules in enumerate(qr.qr.modules):
        for col, dark in enumerate(modules):
            assert (image.getpixel((348 + col*3, 63 + row*3)) == 0) == bool(dark)


def test_new_layout_matches_physical_reference_geometry():
    snap = dict(layout_version=4, code='INV-G6LVB2', copies=1,
                name='Boné Boss 50535236', size='UNIC', color='Green',
                sale_price='72', sale_currency='USD')
    image = raster_from_zpl(labels.render_zpl(snap))

    def ink_bounds(box):
        left, top, right, bottom = box
        ink = [(x, y) for y in range(top, bottom) for x in range(left, right)
               if image.getpixel((x, y)) == 0]
        return min(x for x, _ in ink), min(y for _, y in ink), max(x for x, _ in ink), max(y for _, y in ink)

    assert ink_bounds((130, 0, 340, 55)) == pytest.approx((167, 21, 317, 49), abs=2)  # ELEVEN
    assert ink_bounds((0, 80, 325, 108))[1:] == pytest.approx((89, 66, 100), abs=2)
    assert ink_bounds((0, 108, 325, 137))[1:] == pytest.approx((114, 84, 125), abs=2)
    assert ink_bounds((0, 137, 325, 177))[1:] == pytest.approx((145, 119, 156), abs=2)
    assert ink_bounds((330, 50, 460, 165)) == (348, 63, 434, 149)  # QR
    # USD follows the reference's '$72'; the source product still stores USD.
    assert ink_bounds((0, 180, 180, 230)) == pytest.approx((32, 192, 74, 212), abs=2)


def test_queued_v3_snapshot_keeps_identical_raster_zpl():
    old_snapshot = dict(layout_version=3, code='INV-A7K4P2', copies=7,
                        name='Camiseta ^XZ ~JA _A1 Ç', color='Azul', size='2XL',
                        barcode='7891234567890', sale_price='149.90', sale_currency='BRL')
    assert hashlib.sha256(labels.render_zpl(old_snapshot)).hexdigest() == (
        'bd908f845739bd0e37d20efbcc149c614027698d8fa14c63888446678c9aa8d7')


def test_zero_sale_price_is_a_dash_not_a_fabricated_amount(label_env):
    factory, client, ids, _ = label_env
    row = selection(client, ids[1:2])[0]
    assert row['sale_price'] == '0.00'
    preview = client.get('/api/inventory-labels/preview/'+ids[1])
    assert preview.status_code == 200
    with factory() as db:
        snap = labels.snapshot(db.get(Item, uuid.UUID(ids[1])), 1)
    image = raster_from_preview(preview.content)
    assert raster_from_zpl(labels.render_zpl(snap)).tobytes() == image.tobytes()
    # The left price area contains only the small dash, never a fabricated 0,00.
    ink = ImageChops.invert(image.convert('L').crop((0, 185, 300, 230))).getbbox()
    assert ink and ink[2] - ink[0] < 15


@pytest.mark.parametrize('changed_field, changed_value', [
    ('sale_price', Decimal('150.00')),
    ('sale_currency', 'USD'),
])
def test_price_change_after_selection_requires_a_fresh_confirmation(label_env, changed_field, changed_value):
    factory, client, ids, _ = label_env
    setup_device(client)
    body = payload(client, ids[:1])
    with factory() as db:
        setattr(db.get(Item, uuid.UUID(ids[0])), changed_field, changed_value)
        db.commit()
    response = client.post('/api/inventory-labels/batches', json=body)
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.query(PrintJob).count() == 0


def test_unversioned_snapshot_keeps_identical_legacy_zpl():
    old_snapshot = dict(code='INV-A7K4P2', copies=2, name='Camiseta Azul', size='M', color='Azul')
    assert hashlib.sha256(labels.render_zpl(old_snapshot)).hexdigest() == (
        '8caea4ab7485b1116a617a5f247252ce55f49a454791be64c1f202dd3d86ff23')


def test_queued_v2_snapshot_keeps_identical_zpl():
    old_snapshot = dict(layout_version=2, code='INV-A7K4P2', copies=2,
                        name='Camiseta Azul', size='M', color='Azul',
                        barcode='7891234567890', sale_price='149.90', sale_currency='BRL')
    assert hashlib.sha256(labels.render_zpl(old_snapshot)).hexdigest() == (
        '3f8781cd14c9c805a227242349d7556e404cd78973b05f53389e560421b3ed94')


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
