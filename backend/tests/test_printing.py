"""Isolated print authorization, idempotency and at-most-once dispatch checks."""
import hashlib
import uuid
from datetime import timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.models.printing import PrintDevice, PrintJob
from app.models.address_book import SavedAddress, PrintLayout
from app.models.usuario import Usuario
from app.models.assistant import utcnow
from app.api.endpoints import printing
from test_assistant import setup


@pytest.fixture
def print_env(setup):
    factory, _, user_id = setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[SavedAddress.__table__, PrintLayout.__table__, PrintDevice.__table__, PrintJob.__table__])
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


def test_recipient_cpf_rules_are_brazil_only_and_py_preserves_document_text():
    from pydantic import ValidationError
    from app.services.assistant_printing import AddressArgs
    values = dict(pais='BR', nome='Cliente Teste', endereco='Rua Exemplo 123',
                  cidade='Curitiba', estado='PR', cep='80000-000', remetente='mona')
    for cpf in ['123', '12345678901abc']:
        with pytest.raises(ValidationError): AddressArgs(**values, cpf=cpf)
    for empty in ['', '000.000.000-00', '11111111111']:
        assert AddressArgs(**values, cpf=empty).cpf == ''
    assert AddressArgs(**values, cpf='12345678901').cpf == '123.456.789-01'
    assert AddressArgs(**values, cpf='123.456.789-01').cpf == '123.456.789-01'
    values['pais'] = 'PY'
    for document in ['', '000.000.000-00', '11111111111', '12345678901', 'A-4.567.890']:
        assert AddressArgs(**values, cpf=document).cpf == document


def test_placeholder_cpf_is_not_rendered(monkeypatch):
    from app.services import assistant_printing as printing
    captured = []
    original = printing.Paragraph
    def paragraph(text, style):
        captured.append(text)
        return original(text, style)
    monkeypatch.setattr(printing, 'Paragraph', paragraph)
    payload = {'endereco': dict(pais='BR', nome='Teste', endereco='Rua Exemplo 10', cidade='Curitiba',
                               estado='PR', cep='80000-000', telefone='', cpf='000.000.000-00'),
               'remetente': {'nome': 'Teste', 'linhas': ['Remetente Teste']}}
    printing.render_address(payload)
    assert not any('CPF' in text or '000.000.000-00' in text for text in captured)
    captured.clear()
    payload['endereco']['cpf'] = '12345678901'
    printing.render_address(payload)
    assert 'CPF: 123.456.789-01' in captured


def test_paraguay_prints_supplied_fields_without_street(monkeypatch):
    from app.services import assistant_printing as printing
    args = printing.AddressArgs(pais='PY', nome='Cliente Teste', telefone='+595 900 123456', cidade='Asunción')
    assert args.endereco == ''
    assert printing.AddressArgs(pais='PY', telefone='123456').nome == ''
    captured = []
    original = printing.Paragraph
    def paragraph(text, style):
        captured.append(text)
        return original(text, style)
    monkeypatch.setattr(printing, 'Paragraph', paragraph)
    printing.render_address({'endereco': args.model_dump(), 'remetente': None})
    assert 'Cliente Teste' in captured and 'Asunción' in captured
    assert 'Tel.: +595 900 123456' in captured
    assert not any('REMETENTE' in t or 'CPF' in t or 'CEP' in t for t in captured)


def test_agent_replacement_preserves_identity_queue_and_credential(print_env):
    factory, client = print_env
    old, headers = device(client)
    other, _ = device(client)
    job = enqueue(client, old).json()
    for _ in range(2):
        response = client.post('/api/printing/agent/connect', headers=headers,
                               json={'name': ' Samsung SL-M2035W '})
        assert response.status_code == 200
        assert response.json() == {'id': old['id'], 'name': 'Samsung SL-M2035W'}
    with factory() as db:
        current = db.get(PrintDevice, uuid.UUID(old['id']))
        assert current.token_hash == hashlib.sha256(old['token'].encode()).hexdigest()
        assert current.last_seen_at is not None
        assert db.query(PrintDevice).count() == 2
        assert db.get(PrintDevice, uuid.UUID(other['id'])).name == other['name']
        pending = db.get(PrintJob, uuid.UUID(job['id']))
        assert pending.device_id == current.id and pending.status == 'pending'
    assert client.post('/api/printing/agent/claim', headers=headers).json()['id'] == job['id']
    assert client.post('/api/printing/agent/claim', headers=headers).status_code == 204
    assert client.post('/api/printing/agent/connect', headers=headers,
                       json={'name': 'Other', 'device_id': other['id']}).status_code == 422
    for name in (' ', 'Line\nbreak', 'x' * 101):
        assert client.post('/api/printing/agent/connect', headers=headers,
                           json={'name': name}).status_code == 422
    assert client.post('/api/printing/agent/connect', json={'name': 'Samsung'}).status_code == 401
    client.post(f"/api/printing/devices/{old['id']}/revoke")
    assert client.post('/api/printing/agent/connect', headers=headers,
                       json={'name': 'Samsung'}).status_code == 401


def test_agent_package_has_only_distributable_files(print_env):
    import io
    from zipfile import ZipFile
    _, client = print_env
    response = client.get('/api/printing/agent-package')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {'Eleven-Impressao/' + name for name in (
            'Instalar.cmd', 'Instalar.ps1', 'Configuracao.ps1', 'Agente.ps1', 'LEIA-ME.txt')}
        assert b'Samsung SL-M2035W' in archive.read('Eleven-Impressao/Instalar.ps1')
    app = FastAPI()
    app.include_router(printing.router, prefix='/api/printing')
    d, headers = device(client)
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/printing/agent-package').status_code in (401, 403)
        assert anonymous.get('/api/printing/agent-package', headers=headers).status_code in (401, 403)


def test_bot_print_uses_replacement_name_without_new_device(print_env):
    from app.models.assistant import AssistantIdentity, AssistantAction
    from app.models.usuario import UsuarioRole
    from app.services.assistant_printing import AddressArgs, prepare_print
    from app.services.assistant_documents import query_prints
    from app.services.assistant_queries import QueryArgs
    from test_assistant import incoming
    factory, client = print_env
    old, headers = device(client)
    client.post('/api/printing/agent/connect', headers=headers, json={'name': 'Samsung SL-M2035W'})
    with factory() as db:
        user = db.query(Usuario).one(); user.role = UsuarioRole.ADMIN
        identity = db.query(AssistantIdentity).filter_by(channel='telegram').one()
        msg = incoming(db, user.id, 'Imprime este endereço', channel='telegram')
        response = prepare_print(db, msg, identity, AddressArgs(pais='PY', nome='Cliente Teste'))
        assert 'Samsung SL-M2035W' in response['confirmacao']
        action = db.query(AssistantAction).one()
        assert action.payload['device_id'] == old['id']
        assert db.query(PrintJob).count() == 0
        assert query_prints(db, msg, identity, QueryArgs())['impressoras'][0]['nome'] == 'Samsung SL-M2035W'
