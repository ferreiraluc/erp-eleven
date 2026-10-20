"""Opt-in migration and reliable claims; no live network or physical printing."""
import io
import uuid
from datetime import timedelta

from pypdf import PdfReader
from app.models.assistant import utcnow
from app.models.printing import PrintDevice, PrintJob
from app.models.pdv import PdvSale
from app.models.usuario import Usuario, UsuarioRole
from app.dependencies import get_current_active_user
from test_pdv_receipts import tickets, configure, sale
from test_pdv_unknown_stock import pdv_app


def prepare(client):
    result = client.post('/api/printing/receipt-device/macos')
    assert result.status_code == 200, result.text
    data = result.json()
    return data['device'], {'Authorization': 'Bearer '+data['token']}


def connect(client, headers):
    result = client.post('/api/printing/agent/connect', headers=headers,
                         json={'name':'3nStar test', 'profile':'tickets', 'driver':'escpos_tcp'})
    assert result.status_code == 200, result.text


def claim(client, headers, key=None):
    return client.post('/api/printing/agent/claim', headers=headers, params={
        'driver':'escpos_tcp', 'continuous_tickets':True, 'claim_key':str(key or uuid.uuid4())})


def test_job(client, device, key=None):
    response = client.post(f"/api/printing/receipt-devices/{device['id']}/test",
                           json={'confirm':True, 'request_key':str(key or uuid.uuid4())})
    assert response.status_code == 200, response.text
    return response.json()['job']


test_job.__test__ = False


def validated(client, device, headers):
    connect(client, headers)
    job = test_job(client, device)
    assert claim(client, headers).json()['id'] == job['id']
    result = client.post(f"/api/printing/agent/jobs/{job['id']}/result", headers=headers,
                         json={'status':'submitted', 'diagnostic':{'code':'network_accepted', 'agent_version':'2026.10.20.1'}})
    assert result.status_code == 200
    return job


def activate(client, device, test=None):
    return client.post(f"/api/printing/receipt-devices/{device['id']}/activate",
                       json={'confirm':True,'test_job_id':test['id'] if test else None})


def test_preparation_preserves_zebra_a4_sales_and_does_not_print(tickets):
    factory, client, customer = tickets
    zebra = configure(client)
    a4 = client.post('/api/printing/devices', json={'name':'Samsung'}).json()
    mac, headers = prepare(client)
    again = client.post('/api/printing/receipt-device/macos').json()
    assert again['device']['id'] == mac['id'] and again['token'] is None
    assert not mac['auto_receipts'] and mac['driver'] == 'escpos_tcp'
    assert client.get('/api/printing/receipt-device').json()['device']['id'] == zebra['device']['id']
    with factory() as db:
        assert db.query(PrintJob).count() == 0 and db.query(PdvSale).count() == 0
        assert db.get(PrintDevice, uuid.UUID(a4['id'])).active
    sale(client, customer)
    with factory() as db: assert str(db.query(PrintJob).one().device_id) == zebra['device']['id']
    assert claim(client, headers).status_code == 204


def test_claim_protocol_isolation_and_lost_response_recovery(tickets):
    factory, client, _ = tickets
    zebra = configure(client)
    mac, headers = prepare(client)
    key = uuid.uuid4()
    job = test_job(client, mac)
    assert client.post('/api/printing/agent/connect', headers=headers, json={'name':'Wrong','profile':'tickets'}).status_code == 409
    assert client.post('/api/printing/agent/claim', headers=headers, params={'continuous_tickets':True}).status_code == 409
    assert client.post('/api/printing/agent/claim', headers=headers, params={'driver':'escpos_tcp','continuous_tickets':True}).status_code == 422
    a = claim(client, headers, key)
    b = claim(client, headers, key)
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert a.json()['id'] == job['id'] and a.json()['paper_mode'] == 'continuous'
    assert claim(client, headers).status_code == 409
    foreign = {'Authorization':'Bearer '+zebra['token']}
    assert claim(client, foreign, key).status_code == 409
    pdf = client.get('/api/printing/agent/jobs/'+job['id']+'/pdf', headers=headers)
    pages = PdfReader(io.BytesIO(pdf.content)).pages
    assert len(pages) == 1 and 'PRUEBA DE IMPRESORA' in pages[0].extract_text()
    assert 'Crédito' in pages[0].extract_text()
    for _ in range(2):
        assert client.post('/api/printing/agent/jobs/'+job['id']+'/result', headers=headers,
                           json={'status':'uncertain','diagnostic':{'code':'network_interrupted','agent_version':'2026.10.20.1'}}).status_code == 200
    assert claim(client, headers, key).status_code == 409
    assert claim(client, headers).status_code == 204
    with factory() as db:
        only = db.query(PrintJob).one()
        assert only.status == 'uncertain' and only.pdf == b'' and only.claim_key == key


def test_activation_requires_printed_test_confirmation_recent_agent_and_empty_old_queue(tickets):
    factory, client, customer = tickets
    zebra = configure(client)
    mac, headers = prepare(client)
    assert activate(client, mac).status_code == 409
    test = test_job(client, mac)
    assert activate(client, mac, test).status_code == 409
    assert claim(client, headers).json()['id'] == test['id']
    client.post('/api/printing/agent/jobs/'+test['id']+'/result', headers=headers, json={'status':'submitted'})
    with factory() as db:
        db.get(PrintDevice, uuid.UUID(mac['id'])).last_seen_at = utcnow()-timedelta(minutes=5)
        db.commit()
    assert activate(client, mac, test).status_code == 409
    connect(client, headers)
    assert client.post(f"/api/printing/receipt-devices/{mac['id']}/activate",
                       json={'test_job_id':test['id']}).status_code == 422
    old_sale = sale(client, customer)
    assert activate(client, mac, test).status_code == 409
    # Isolated state represents the old station completing its own authorized job.
    with factory() as db:
        job = db.query(PrintJob).filter_by(source='pdv_receipt').one()
        job.status = 'submitted'; db.commit()
    assert activate(client, mac, test).status_code == 200
    sale(client, customer)
    with factory() as db:
        assert not db.get(PrintDevice, uuid.UUID(zebra['device']['id'])).auto_receipts
        assert db.get(PrintDevice, uuid.UUID(zebra['device']['id'])).active
        assert db.get(PrintDevice, uuid.UUID(mac['id'])).auto_receipts
        latest = db.query(PrintJob).filter_by(status='pending').one()
        assert str(latest.device_id) == mac['id']
        assert latest.snapshot['width'] == 80 and latest.snapshot['height'] == 0
    assert activate(client, zebra['device']).status_code == 409  # don't abandon the Mac's queue either
    assert client.get(f"/api/pdv/sales/{old_sale['id']}/receipt/pdf").status_code == 200


def test_pending_mac_jobs_survive_outage_over_24_hours(tickets):
    factory, client, _ = tickets
    mac, headers = prepare(client)
    job = test_job(client, mac)
    with factory() as db:
        db.get(PrintJob, uuid.UUID(job['id'])).expires_at = utcnow()-timedelta(days=7)
        db.commit()
    assert claim(client, headers).json()['id'] == job['id']
    with factory() as db: assert db.query(PrintJob).one().status == 'claimed'


def test_pause_stops_new_receipts_without_dropping_confirmed_queue(tickets):
    factory, client, customer = tickets
    mac, headers = prepare(client)
    test = validated(client, mac, headers)
    assert activate(client, mac, test).status_code == 200
    sale(client, customer)
    url = f"/api/printing/receipt-devices/{mac['id']}/pause"
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={'confirm':True}).status_code == 200
    sale(client, customer)
    with factory() as db:
        assert db.query(PdvSale).count() == 2
        assert db.query(PrintJob).filter_by(source='pdv_receipt').count() == 1
    assert claim(client, headers).status_code == 200


def test_test_request_idempotency_and_rotation_target_only_mac(tickets):
    factory, client, _ = tickets
    zebra = configure(client)
    mac, headers = prepare(client)
    url = f"/api/printing/receipt-devices/{mac['id']}/test"
    assert client.post(url, json={'request_key':str(uuid.uuid4())}).status_code == 422
    key = uuid.uuid4()
    a, b = test_job(client, mac, key), test_job(client, mac, key)
    assert a == b
    rotated = client.post('/api/printing/receipt-device/credential', params={'confirm':True, 'device_id':mac['id']})
    assert rotated.status_code == 200 and rotated.headers['cache-control'] == 'no-store'
    assert claim(client, headers).status_code == 401
    zheaders = {'Authorization':'Bearer '+zebra['token']}
    assert client.post('/api/printing/agent/connect', headers=zheaders, json={'name':'Zebra','profile':'tickets'}).status_code == 200
    with factory() as db: assert db.query(PrintJob).count() == 1


def test_staff_cannot_prepare_test_activate_or_list_credentials(tickets):
    factory, client, _ = tickets
    mac, _ = prepare(client)
    with factory() as db:
        employee = Usuario(nome='Teste', email='staff@example.invalid', senha_hash='unused', role=UsuarioRole.VENDEDOR)
        db.add(employee); db.commit(); staff_id=employee.id
    def staff():
        with factory() as db: return db.get(Usuario, staff_id)
    client.app.dependency_overrides[get_current_active_user] = staff
    assert client.get('/api/printing/receipt-devices').status_code == 403
    assert client.post('/api/printing/receipt-device/macos').status_code == 403
    assert client.post(f"/api/printing/receipt-devices/{mac['id']}/test",
                       json={'confirm':True,'request_key':str(uuid.uuid4())}).status_code == 403
    assert activate(client, mac).status_code == 403
