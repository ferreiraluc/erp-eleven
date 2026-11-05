"""Windows claim recovery: no real printers, queue clearing, or production data."""
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

from app.api.endpoints import printing
from app.database import Base
from app.models.printing import PrintJob
from test_access_postgres import pg
from test_assistant import setup
from test_pdv_stock_postgres import pdv_pg
from test_printing import device, enqueue, print_env


def test_windows_recovers_lost_claim_response_without_claiming_next_job(print_env):
    factory, client = print_env
    printer, headers = device(client)
    first, second = [enqueue(client, printer).json() for _ in range(2)]
    key = str(uuid.uuid4())
    url = '/api/printing/agent/claim'
    claimed = client.post(url, params={'claim_key': key}, headers=headers)
    assert claimed.status_code == 200
    assert claimed.json()['id'] == first['id']
    # The request may have succeeded while its response was lost to the agent.
    repeated = client.post(url, params={'claim_key': key}, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json() == claimed.json()
    assert client.post(url, params={'claim_key': str(uuid.uuid4())}, headers=headers).status_code == 409
    # An old installation with the same credential cannot skip the new journal.
    assert client.post(url, headers=headers).status_code == 409
    with factory() as db:
        assert db.get(PrintJob, uuid.UUID(first['id'])).claim_key == uuid.UUID(key)
        assert db.get(PrintJob, uuid.UUID(second['id'])).status == 'pending'
    assert client.get(f"/api/printing/agent/jobs/{first['id']}/pdf", headers=headers).content.startswith(b'%PDF-')


@pytest.mark.parametrize('status', ['submitted', 'uncertain', 'failed'])
def test_final_ack_can_repeat_but_its_claim_key_never_reprints(print_env, status):
    factory, client = print_env
    printer, headers = device(client)
    first, second = [enqueue(client, printer).json() for _ in range(2)]
    key = str(uuid.uuid4())
    url = '/api/printing/agent/claim'
    assert client.post(url, params={'claim_key': key}, headers=headers).status_code == 200
    for _ in range(2):
        assert client.post(f"/api/printing/agent/jobs/{first['id']}/result", json={'status': status}, headers=headers).status_code == 200
    assert client.post(url, params={'claim_key': key}, headers=headers).status_code == 409
    next_job = client.post(url, params={'claim_key': str(uuid.uuid4())}, headers=headers)
    assert next_job.status_code == 200 and next_job.json()['id'] == second['id']
    with factory() as db:
        assert db.get(PrintJob, uuid.UUID(first['id'])).status == status


def test_claim_key_is_device_scoped_and_does_not_adopt_legacy_claims(print_env):
    factory, client = print_env
    first, headers = device(client)
    second, other_headers = device(client)
    legacy = enqueue(client, first).json()
    enqueue(client, first)
    assert client.post('/api/printing/agent/claim', headers=headers).json()['id'] == legacy['id']
    key = str(uuid.uuid4())
    assert client.post('/api/printing/agent/claim', params={'claim_key': key}, headers=headers).status_code == 409
    # Existing legacy journals can still acknowledge their already-claimed job.
    assert client.post(f"/api/printing/agent/jobs/{legacy['id']}/result", json={'status': 'uncertain'}, headers=headers).status_code == 200
    assert client.post('/api/printing/agent/claim', params={'claim_key': key}, headers=headers).status_code == 200
    enqueue(client, second)
    assert client.post('/api/printing/agent/claim', params={'claim_key': key}, headers=other_headers).status_code == 409
    with factory() as db:
        assert db.query(PrintJob).filter_by(device_id=uuid.UUID(second['id']), status='pending').count() == 1


def test_lost_claim_response_then_author_revocation_does_not_strand_queue(print_env):
    from app.models import Usuario
    from app.models.assistant import AssistantIdentity
    from app.services.assistant_schedule import confirm_action
    from test_assistant_print_authorization import prepare_address

    factory, client = print_env
    printer, headers = device(client)
    with factory() as db:
        message, identity, action = prepare_address(db, db.query(Usuario).one().id)
        confirm_action(db, message, identity, action)
        job = db.query(PrintJob).one()
        original, identity_id = str(job.id), identity.id
        db.commit()
    next_job = enqueue(client, printer).json()
    key = str(uuid.uuid4())
    url = '/api/printing/agent/claim'
    first = client.post(url, params={'claim_key': key}, headers=headers)
    assert first.status_code == 200 and first.json()['id'] == original
    # Server claimed the job, but the client lost its response before creating
    # a job journal. Only claim.json survives, then the requester loses access.
    with factory() as db:
        db.get(AssistantIdentity, identity_id).active = False
        db.commit()
    recovered = client.post(url, params={'claim_key': key}, headers=headers)
    assert recovered.status_code == 200
    assert recovered.json() == first.json()
    assert set(recovered.json()) == {'id', 'sha256'}  # No recipient or document.
    assert client.get(f'/api/printing/agent/jobs/{original}/pdf', headers=headers).status_code == 403
    with factory() as db:
        assert db.get(PrintJob, uuid.UUID(original)).status == 'claimed'
    # The agent can now record a pre-dispatch download failure and acknowledge
    # it normally, without resetting/reassigning/printing the revoked job.
    ack = client.post(f'/api/printing/agent/jobs/{original}/result', headers=headers, json={
        'status': 'failed', 'diagnostic': {'code': 'download_failed', 'agent_version': '2026.11.05.1'}})
    assert ack.status_code == 200
    assert client.post(url, params={'claim_key': str(uuid.uuid4())}, headers=headers).json()['id'] == next_job['id']
    with factory() as db:
        revoked = db.get(PrintJob, uuid.UUID(original))
        assert revoked.status == 'failed' and str(revoked.claim_key) == key and revoked.pdf == b''


def test_windows_claim_races_serialize_in_postgres(pdv_pg):
    factory, client, *_ = pdv_pg
    client.app.include_router(printing.router, prefix='/api/printing')
    with factory() as db:
        Base.metadata.create_all(db.get_bind())
    printer, headers = device(client)
    first, second = [enqueue(client, printer).json() for _ in range(2)]
    key = str(uuid.uuid4())
    url = '/api/printing/agent/claim'
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(url, params={'claim_key': key}, headers=headers), range(2)))
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert responses[0].json()['id'] == first['id']
    assert client.post(f"/api/printing/agent/jobs/{first['id']}/result", json={'status': 'submitted'}, headers=headers).status_code == 200
    # Two installations/requests with different keys cannot claim two jobs.
    enqueue(client, printer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda claim_key: client.post(url, params={'claim_key': claim_key}, headers=headers), [str(uuid.uuid4()), str(uuid.uuid4())]))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert next(r for r in responses if r.status_code == 200).json()['id'] == second['id']
    with factory() as db:
        assert db.query(PrintJob).filter_by(device_id=uuid.UUID(printer['id']), status='claimed').count() == 1
        assert db.query(PrintJob).filter_by(device_id=uuid.UUID(printer['id']), status='pending').count() == 1
