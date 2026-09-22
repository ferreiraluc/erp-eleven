"""Isolated print authorization, idempotency and at-most-once dispatch checks."""
import hashlib
import uuid
from datetime import timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.models.printing import PrintDevice, PrintJob
from app.models.usuario import Usuario
from app.models.assistant import utcnow
from app.api.endpoints import printing
from test_assistant import setup


@pytest.fixture
def print_env(setup):
    factory, _, user_id = setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintDevice.__table__, PrintJob.__table__])
    app = FastAPI()
    app.include_router(printing.router, prefix="/api/printing")
    def session():
        with factory() as db:
            yield db
    def admin():
        with factory() as db:
            return db.get(Usuario, user_id)
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[printing.administrator] = admin
    return factory, TestClient(app)


def device(client):
    d = client.post('/api/printing/devices', json={'name': 'HP test'}).json()
    return d, {'Authorization': 'Bearer ' + d['token']}


def enqueue(client, d, key=None, pdf=b'%PDF-1.4\ntest'):
    return client.post('/api/printing/jobs', data={
        'device_id': d['id'], 'request_key': str(key or uuid.uuid4())},
        files={'file': ('test.pdf', pdf, 'application/pdf')})


def test_claim_once_and_ack_idempotent(print_env):
    factory, client = print_env
    d, headers = device(client)
    key = uuid.uuid4()
    job = enqueue(client, d, key).json()
    assert enqueue(client, d, key).json()['id'] == job['id']
    assert enqueue(client, d, key, b'%PDF-1.4\nchanged').status_code == 409
    claim = client.post('/api/printing/agent/claim', headers=headers)
    assert claim.json()['id'] == job['id']
    assert client.post('/api/printing/agent/claim', headers=headers).status_code == 204
    pdf = client.get(f"/api/printing/agent/jobs/{job['id']}/pdf", headers=headers)
    assert hashlib.sha256(pdf.content).hexdigest() == claim.json()['sha256']
    for _ in range(2):
        assert client.post(f"/api/printing/agent/jobs/{job['id']}/result", headers=headers,
                           json={'status': 'submitted'}).status_code == 200
    assert client.post(f"/api/printing/agent/jobs/{job['id']}/result", headers=headers,
                       json={'status': 'uncertain'}).status_code == 409
    with factory() as db:
        assert db.get(PrintJob, uuid.UUID(job['id'])).pdf == b''
        assert db.get(PrintDevice, uuid.UUID(d['id'])).token_hash != d['token']


def test_device_isolation_revocation_and_expiry(print_env):
    factory, client = print_env
    d, headers = device(client)
    other, foreign = device(client)
    job = enqueue(client, d).json()
    assert client.post('/api/printing/agent/claim').status_code == 401
    assert client.post('/api/printing/agent/claim', headers=foreign).status_code == 204
    assert client.get(f"/api/printing/agent/jobs/{job['id']}/pdf", headers=foreign).status_code == 404
    assert client.post(f"/api/printing/agent/jobs/{job['id']}/result", headers=foreign,
                       json={'status': 'submitted'}).status_code == 404
    with factory() as db:
        db.get(PrintJob, uuid.UUID(job['id'])).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.post('/api/printing/agent/claim', headers=headers).status_code == 204
    assert client.post(f"/api/printing/devices/{d['id']}/revoke").status_code == 200
    assert client.post('/api/printing/agent/claim', headers=headers).status_code == 401
    assert enqueue(client, other, pdf=b'not pdf').status_code == 400


def test_admin_routes_reject_anonymous():
    app = FastAPI()
    app.include_router(printing.router, prefix='/api/printing')
    with TestClient(app) as client:
        assert client.get('/api/printing/devices').status_code in (401, 403)
