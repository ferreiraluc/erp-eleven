"""Count sheets use isolated data and the queue only; no physical printing."""
import copy
import hashlib
import io
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import event, update

from app.api.endpoints import inventory_count_list as api, address_manager, printing
from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models.assistant import utcnow
from app.models.inventory import Item, StockMovement
from app.models.printing import PrintDevice, PrintJob
from app.models.usuario import Usuario, UsuarioRole
from app.schemas.inventory_count_list import CountSnapshot
from app.services import inventory_count_list as lists
from test_assistant import setup  # noqa: F401
from test_address_manager import env  # noqa: F401


@pytest.fixture
def counts(env):
    factory, _, user_id, device_id = env
    device_id = uuid.UUID(device_id)
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[StockMovement.__table__])
        db.get(PrintDevice, device_id).name = 'HP Loja A4'
        first = Item(name='Camiseta <Boss> & Eleven', sku_internal='LEGACY-ONE', inventory_code='INV-ABC123',
                     color='Branco', size='M', location='Prateleira 4', stock_loja=2, stock_deposito=7,
                     current_stock=9, image_data='large-original-not-to-load', cost_price=75, sale_price=150)
        second = Item(name='Calça azul', sku_internal='LEGACY-TWO', inventory_code='INV-DEF456',
                      stock_loja=0, stock_deposito=3, current_stock=3, is_active=False)
        db.add_all([first, second]); db.flush()
        ids = [first.id, second.id]
        # Explicit NULL simulates legacy balances, which must not become zero.
        db.execute(update(Item).where(Item.id == second.id).values(stock_loja=None))
        db.commit()
    app = FastAPI()
    app.include_router(api.router, prefix='/counts')
    app.include_router(printing.router, prefix='/printing')
    app.include_router(address_manager.router, prefix='/addresses')
    def session():
        with factory() as db:
            yield db
    def user():
        with factory() as db:
            return db.get(Usuario, user_id)
    def device():
        with factory() as db:
            return db.get(PrintDevice, device_id)
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = user
    app.dependency_overrides[printing.printer] = device
    return factory, TestClient(app), user_id, device_id, ids


def preview(client, ids):
    response = client.post('/counts/preview', json={'item_ids': [str(key) for key in ids]})
    assert response.status_code == 200, response.text
    return response.json()


def signed(value):
    return {'snapshot': value['snapshot'], 'signature': value['signature']}


def request(value, device_id):
    return {**signed(value), 'device_id': str(device_id), 'request_key': str(uuid.uuid4()), 'confirm': True}


def test_preview_uses_selected_database_balances_without_images_or_prices(counts):
    factory, client, _, device_id, ids = counts
    statements = []
    with factory() as db:
        engine = db.get_bind()
    def capture(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith('SELECT') and 'inventory_items' in statement:
            statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = preview(client, [ids[1], ids[0], ids[1]])
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    snapshot = result['snapshot']
    assert [row['id'] for row in snapshot['items']] == [str(ids[1]), str(ids[0])]
    assert snapshot['totals'] == {'items': 2, 'stock_loja': 2, 'stock_deposito': 10,
                                  'unknown_loja': 1, 'unknown_deposito': 0}
    assert snapshot['items'][0]['stock_loja'] is None
    assert result['suggested_device_id'] == str(device_id)
    assert 'token_hash' not in result['devices'][0]
    assert statements and all('image_data' not in sql and 'price' not in sql for sql in statements)
    assert 'sale_price' not in str(snapshot) and 'large-original' not in str(snapshot)
    with factory() as db:
        assert db.query(PrintJob).count() == db.query(StockMovement).count() == 0
        assert db.get(Item, ids[0]).stock_deposito == 7


def test_preview_rejects_missing_deleted_and_out_of_bounds_without_partial_list(counts):
    factory, client, _, _, ids = counts
    assert client.post('/counts/preview', json={'item_ids': [str(ids[0]), str(uuid.uuid4())]}).status_code == 409
    assert client.post('/counts/preview', json={'item_ids': []}).status_code == 422
    assert client.post('/counts/preview', json={'item_ids': ['invalid']}).status_code == 422
    assert client.post('/counts/preview', json={'item_ids': [str(ids[0])] * 5001}).status_code == 422
    with factory() as db:
        db.get(Item, ids[1]).deleted_at = utcnow(); db.commit()
    assert client.post('/counts/preview', json={'item_ids': [str(key) for key in ids]}).status_code == 409


def test_signed_pdf_is_deterministic_paginated_and_has_distinct_stock_columns(counts):
    factory, client, _, _, ids = counts
    value = preview(client, ids)
    first = client.post('/counts/pdf', json=signed(value))
    second = client.post('/counts/pdf', json=signed(value))
    assert first.status_code == 200 and first.content == second.content
    assert first.headers['cache-control'] == 'no-store'
    pdf = PdfReader(io.BytesIO(first.content))
    page = pdf.pages[0]
    assert round(float(page.mediabox.width)) == 595 and round(float(page.mediabox.height)) == 842
    text = page.extract_text()
    for expected in ['ELEVEN', 'CONFERÊNCIA DE ESTOQUE', 'Camiseta <Boss> & Eleven', 'INV-ABC123',
                     'Prateleira 4', 'Saldo no sistema', 'Contagem física', 'Loja', 'Depósito', 'Não inf.', 'Página 1']:
        assert expected in text
    assert '75' not in text and '150' not in text
    with factory() as db:
        assert db.query(PrintJob).count() == 0


def test_signature_owner_expiry_shape_and_explicit_confirmation_are_enforced(counts, monkeypatch):
    factory, client, _, device_id, ids = counts
    value = preview(client, ids)
    forged = copy.deepcopy(value)
    forged['snapshot']['items'][0]['name'] = 'Outra peça'
    assert client.post('/counts/pdf', json=signed(forged)).status_code == 403
    forged = copy.deepcopy(value)
    forged['snapshot']['user_id'] = str(uuid.uuid4())
    assert client.post('/counts/pdf', json=signed(forged)).status_code == 403
    forged = copy.deepcopy(value)
    forged['snapshot']['totals']['stock_loja'] += 1
    assert client.post('/counts/pdf', json=signed(forged)).status_code == 422
    body = request(value, device_id)
    assert client.post('/counts/print', json={**body, 'confirm': False}).status_code == 422
    assert client.post('/counts/print', json={**body, 'confirm': 1}).status_code == 422
    assert client.post('/counts/print', json={k: v for k, v in body.items() if k != 'confirm'}).status_code == 422
    moment = utcnow() + timedelta(hours=2)
    monkeypatch.setattr(lists, 'utcnow', lambda: moment)
    assert client.post('/counts/pdf', json=signed(value)).status_code == 409
    response = client.post('/counts/print', json=body)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'inventory_count_preview_expired'
    assert response.json()['detail']['not_queued'] is True
    with factory() as db:
        assert db.query(PrintJob).count() == db.query(StockMovement).count() == 0


@pytest.mark.parametrize('role,expected', [(UsuarioRole.GERENTE, 200), (UsuarioRole.VENDEDOR, 403), (UsuarioRole.LIMPEZA, 403)])
def test_inventory_reports_respect_backend_roles(counts, role, expected):
    factory, client, user_id, _, ids = counts
    with factory() as db:
        db.get(Usuario, user_id).role = role; db.commit()
    assert client.post('/counts/preview', json={'item_ids': [str(ids[0])]}).status_code == expected


def test_anonymous_cannot_download_report():
    app = FastAPI(); app.include_router(api.router, prefix='/counts')
    with TestClient(app) as client:
        assert client.get('/counts/jobs/' + str(uuid.uuid4()) + '/pdf').status_code == 401


@pytest.mark.parametrize('purpose,driver,active', [('tickets', 'windows', True), ('tickets', 'escpos_tcp', True),
                                                ('product_labels', 'windows', True), ('documents', 'windows', False)])
def test_only_active_a4_windows_devices_receive_lists(counts, purpose, driver, active):
    factory, client, _, _, ids = counts
    with factory() as db:
        wrong = PrintDevice(name='Wrong', token_hash=uuid.uuid4().hex * 2, purpose=purpose, driver=driver, active=active)
        db.add(wrong); db.commit(); key = wrong.id
    value = preview(client, ids)
    assert str(key) not in [row['id'] for row in value['devices']]
    response = client.post('/counts/print', json=request(value, key))
    assert response.status_code == 409 and response.json()['detail']['not_queued'] is True
    with factory() as db:
        assert db.query(PrintJob).count() == 0


def test_queue_retries_preserve_original_snapshot_after_expiry_edits_and_offline_device(counts, monkeypatch):
    factory, client, _, device_id, ids = counts
    value = preview(client, ids)
    body = request(value, device_id)
    response = client.post('/counts/print', json=body)
    assert response.status_code == 200, response.text
    job_id = response.json()['id']
    with factory() as db:
        item = db.get(Item, ids[0]); item.stock_loja = 99; item.name = 'Nome atualizado'
        db.get(PrintDevice, device_id).active = False
        db.commit()
    moment = utcnow() + timedelta(hours=2)
    monkeypatch.setattr(lists, 'utcnow', lambda: moment)
    retry = client.post('/counts/print', json=body)
    assert retry.status_code == 200 and retry.json()['id'] == job_id
    changed = copy.deepcopy(body); changed['device_id'] = str(uuid.uuid4())
    assert client.post('/counts/print', json=changed).status_code == 409
    changed = copy.deepcopy(body); changed['snapshot']['items'][0]['name'] = 'Outra lista'
    changed['signature'] = lists.signature(changed['snapshot'])
    assert client.post('/counts/print', json=changed).status_code == 409
    with factory() as db:
        job = db.get(PrintJob, uuid.UUID(job_id))
        assert db.query(PrintJob).count() == 1 and db.query(StockMovement).count() == 0
        assert job.snapshot == value['snapshot'] and job.address_id is None
        assert job.source == 'inventory_list' and job.sha256 == hashlib.sha256(job.pdf).hexdigest()


def test_existing_a4_claim_and_ack_regenerate_identical_pdf_and_isolate_address_history(counts):
    factory, client, user_id, device_id, ids = counts
    body = request(preview(client, ids), device_id)
    job_id = client.post('/counts/print', json=body).json()['id']
    original = client.get(f'/counts/jobs/{job_id}/pdf').content
    # Exercise prepare_document from the actual existing agent claim dispatcher.
    with factory() as db:
        db.get(PrintJob, uuid.UUID(job_id)).pdf = b''; db.commit()
    claim = client.post('/printing/agent/claim')
    assert claim.status_code == 200, claim.text
    assert claim.json() == {'id': job_id, 'sha256': hashlib.sha256(original).hexdigest()}
    assert client.get(f'/printing/agent/jobs/{job_id}/pdf').content == original
    assert client.post(f'/printing/agent/jobs/{job_id}/result', json={'status': 'submitted'}).status_code == 200
    with factory() as db:
        job = db.get(PrintJob, uuid.UUID(job_id))
        assert job.pdf == b'' and job.snapshot == body['snapshot']
        assert db.get(Item, ids[0]).stock_loja == 2 and db.query(StockMovement).count() == 0
    assert client.get(f'/counts/jobs/{job_id}/pdf').content == original
    assert client.get(f'/counts/jobs/{job_id}').json()['status'] == 'submitted'
    assert client.post('/counts/print', json=body).json()['id'] == job_id
    assert client.post('/printing/agent/claim').status_code == 204
    assert client.get('/addresses/history').json()['total'] == 0
    assert client.get('/addresses/overview').json()['statuses'] == {}
    for suffix in ['', '/pdf']:
        assert client.get(f'/addresses/history/{job_id}{suffix}').status_code == 404
    assert client.post(f'/addresses/history/{job_id}/cancel').status_code == 404
    other_id = uuid.uuid4()
    client.app.dependency_overrides[get_current_active_user] = lambda: Usuario(id=other_id, role=UsuarioRole.GERENTE)
    assert client.get(f'/counts/jobs/{job_id}').status_code == 404
    assert client.get(f'/counts/jobs/{job_id}/pdf').status_code == 404


def test_bad_historical_snapshot_does_not_block_following_document(counts):
    factory, client, _, device_id, ids = counts
    value = preview(client, ids)
    first = client.post('/counts/print', json=request(value, device_id)).json()['id']
    second = client.post('/counts/print', json=request(value, device_id)).json()['id']
    with factory() as db:
        broken = db.get(PrintJob, uuid.UUID(first)); broken.pdf = b''; broken.snapshot = {'broken': True}; db.commit()
    assert client.post('/printing/agent/claim').status_code == 204
    failed = client.get('/counts/jobs/' + first).json()
    assert failed['status'] == 'failed' and 'lista de conferência' in failed['diagnostic_message']
    assert client.post('/printing/agent/claim').json()['id'] == second


def test_maximum_selection_pdf_is_bounded_and_long_values_wrap(counts):
    _, client, _, _, ids = counts
    value = preview(client, ids[:1])['snapshot']
    line = value['items'][0]
    value['items'] = [{**line, 'id': str(uuid.uuid4()), 'name': ('Camisa & <importada> ' * 10)[:200],
                       'code': 'SKU-' + 'L' * 46, 'location': 'Prateleira\n' * 8,
                       'size': 'M' * 50, 'color': 'Azul ' * 10} for _ in range(5000)]
    value['totals'] = {'items': 5000, 'stock_loja': 10000, 'stock_deposito': 35000,
                       'unknown_loja': 0, 'unknown_deposito': 0}
    pdf = lists.render(CountSnapshot.model_validate(value))
    assert pdf.startswith(b'%PDF-') and len(pdf) < lists.MAX_PDF_BYTES
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) > 30
    assert 'Página 1' in reader.pages[0].extract_text()
    assert '5000' in reader.pages[-1].extract_text()
    assert 'Saldo no sistema' in reader.pages[-1].extract_text()
