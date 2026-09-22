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


def test_bot_print_confirm_permissions_and_duplicate(print_env):
    from app.models.assistant import AssistantAction, AssistantIdentity
    from app.models.usuario import UsuarioRole
    from app.services.assistant_printing import AddressArgs, prepare_print
    from app.services.assistant_schedule import confirm_action
    from app.services.assistant_agent import respond
    from test_assistant import incoming
    factory, client = print_env
    device(client)
    with factory() as db:
        user = db.query(Usuario).one()
        identity = db.query(AssistantIdentity).filter_by(channel='telegram').one()
        args = AddressArgs(pais='PY', nome='Cliente Teste', endereco='Calle de Prueba 123', cidade='Asunción', remetente='mona')
        msg = incoming(db, user.id, 'Imprime este endereço', channel='telegram')
        assert 'erro' in prepare_print(db, msg, identity, args)
        user.role = UsuarioRole.ADMIN
        assert 'confirmacao' in prepare_print(db, msg, identity, args)
        assert db.query(PrintJob).count() == 0
        action = db.query(AssistantAction).one()
        assert action.payload['remetente'] is None
        foreign = incoming(db, user.id, 'confirmo', channel='whatsapp')
        assert 'mesma conversa' in confirm_action(db, foreign, identity, action)
        confirm = incoming(db, user.id, 'pode imprimir', channel='telegram')
        assert 'fila de impressão' in respond(db, confirm, identity)
        assert db.query(PrintJob).one().pdf.startswith(b'%PDF-')
        assert 'Nenhuma alteração' in confirm_action(db, confirm, identity, action)
        assert db.query(PrintJob).count() == 1


def test_brazil_validation_sender_snapshot_cancel(print_env):
    from pydantic import ValidationError
    from app.models.printing import PrintSender
    from app.models.assistant import AssistantAction, AssistantIdentity
    from app.models.usuario import UsuarioRole
    from app.services.assistant_printing import AddressArgs, prepare_print, render_address
    from app.services.assistant_schedule import confirm_action
    from test_assistant import incoming
    factory, client = print_env
    device(client)
    values = dict(pais='BR', nome='Cliente Teste', endereco='Rua Teste 123', cidade='Curitiba')
    with pytest.raises(ValidationError): AddressArgs(**values)
    args = AddressArgs(**values, estado='PR', cep='80000-000', cpf='12345678901', remetente='debora')
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[PrintSender.__table__])
        user = db.query(Usuario).one(); user.role = UsuarioRole.ADMIN
        identity = db.query(AssistantIdentity).filter_by(channel='telegram').one()
        msg = incoming(db, user.id, 'Imprime com remetente Débora', channel='telegram')
        assert 'erro' in prepare_print(db, msg, identity, args)
        sender = PrintSender(id='debora', name='Remetente de Teste', lines=['Remetente de Teste', 'Rua Exemplo 10'])
        db.add(sender); db.flush()
        assert 'confirmacao' in prepare_print(db, msg, identity, args)
        action = db.query(AssistantAction).one()
        sender.lines = ['Alterado depois da prévia']
        assert action.payload['remetente']['linhas'][0] == 'Remetente de Teste'
        assert render_address(action.payload).startswith(b'%PDF-')
        confirm = incoming(db, user.id, 'cancela', channel='telegram')
        assert 'cancelado' in confirm_action(db, confirm, identity, action, cancel=True)
        assert db.query(PrintJob).count() == 0


def test_recipient_cpf_required_formatted_and_only_for_brazil():
    from pydantic import ValidationError
    from app.services.assistant_printing import AddressArgs
    values = dict(pais='BR', nome='Cliente Teste', endereco='Rua Exemplo 123',
                  cidade='Curitiba', estado='PR', cep='80000-000', remetente='mona')
    for cpf in ['', '123', '12345678901abc']:
        with pytest.raises(ValidationError): AddressArgs(**values, cpf=cpf)
    assert AddressArgs(**values, cpf='12345678901').cpf == '123.456.789-01'
    assert AddressArgs(**values, cpf='123.456.789-01').cpf == '123.456.789-01'
    values['pais'] = 'PY'
    assert AddressArgs(**values, cpf='12345678901').cpf == ''


def test_old_brazil_draft_cannot_print_without_recipient_cpf():
    from types import SimpleNamespace
    from app.services.assistant_printing import enqueue_print
    draft = SimpleNamespace(payload={'endereco': {'pais': 'BR'}})
    assert 'CPF do destinatário' in enqueue_print(None, draft)
