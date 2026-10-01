"""Synthetic sender drafts are explicit, bounded and never auto-saved."""
import json
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_address_manager import env
from test_assistant import setup
from app.api.endpoints import address_manager as api
from app.models.printing import PrintSender
from app.models.usuario import Usuario, UsuarioRole
from app.dependencies import get_current_active_user
from app.services import sender_generator as generator
from app.services.sender_addresses import sender_address


@pytest.fixture
def owner_env(env):
    # Change only this test's isolated user. Shared fixtures retain their defaults.
    factory, client, uid, did = env
    with factory() as db:
        user = db.get(Usuario, uid)
        user.email = 'lucas@eleven.com'
        user.role = UsuarioRole.ADMIN
        db.commit()
    current_user = client.app.dependency_overrides.pop(api.manager)
    client.app.dependency_overrides[get_current_active_user] = current_user
    return factory, client, uid, did


def person():
    # Synthetic local fixture, never sent to a provider.
    return {"nome": "Pessoa Teste", "cpf": "000.000.000-00", "idade": 35, "rg": "TEST-ID", "data_nasc": "01/01/1990",
            "sexo": "Feminino", "mae": "Nome de teste", "pai": "Outro teste", "senha": "generated-example-only",
            "cep": "85865-000", "endereco": "Rua de Teste", "numero": 10, "bairro": "Centro", "cidade": "Cidade Teste",
            "estado": "PR", "email": "generated@example.test", "celular": "11900000000", "altura": "1,70"}


def save_body(preview):
    return {"request_key": str(uuid.uuid4()), "approved": True, "source": preview["source"],
            "name": "Remetente para revisão", "data": preview["sender_data"], "active": True}


@pytest.fixture(autouse=True)
def isolated_generator(monkeypatch):
    generator._last_generation.clear()
    def no_network(*args, **kwargs): raise AssertionError("Provider requests must be mocked")
    monkeypatch.setattr(generator.requests, "post", no_network)


def test_import_complete_person_leaves_database_unchanged_and_drops_unknown_fields(owner_env):
    factory, client, _, _ = owner_env
    data = {**person(), "untrusted_extra": "do not keep"}
    result = client.post('/manager/sender-generator/import', json={"json_text": json.dumps([data])})
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    preview = result.json()
    assert preview["person"]["idade"] == "35" and preview["person"]["senha"] == data["senha"]
    assert "untrusted_extra" not in preview["person"]
    assert preview["sender_data"]["telefone"] == data["celular"] and "senha" not in preview["sender_data"]
    assert not preview["saved"] and preview["synthetic"]
    with factory() as db:
        assert db.query(PrintSender).count() == 0


@pytest.mark.parametrize('value', [[], [person(), person()], {"foo": "bar"}, {**person(), "nome": {"bad": "nested"}}, {**person(), "senha": ["nested"]}, {**person(), "bairro": "x" * 251}])
def test_import_rejects_invalid_or_multiple_people(value):
    with pytest.raises(HTTPException):
        generator.import_person(generator.ImportPersonArgs(json_text=json.dumps(value)))


def test_generate_public_form_has_fixed_url_no_redirects_one_person_and_timeout(owner_env, monkeypatch):
    factory, client, _, _ = owner_env
    calls = []
    class Response:
        status_code = 200
        def iter_content(self, chunk_size): yield json.dumps([person()]).encode()
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(generator.requests, "post", post)
    result = client.post('/manager/sender-generator/generate', json={"sexo": "F", "idade": 35, "estado": "PR"})
    assert result.status_code == 200 and result.json()["source"] == "4devs_web_form"
    url, kwargs = calls[0]
    assert url == "https://www.4devs.com.br/ferramentas_online.php"
    assert kwargs["data"] == {"acao": "gerar_pessoa", "sexo": "F", "idade": 35, "pontuacao": "S", "cep_estado": "PR", "txt_qtde": "1", "cep_cidade": ""}
    assert kwargs["timeout"] == (5, 20) and kwargs["stream"] and not kwargs["allow_redirects"]
    assert 'cookies' not in kwargs and 'proxies' not in kwargs
    second = client.post('/manager/sender-generator/generate', json={})
    assert second.status_code == 429 and len(calls) == 1
    with factory() as db:
        assert db.query(PrintSender).count() == 0


@pytest.mark.parametrize('status,body', [(403,b'captcha'),(429,b'rate limited'),(302,b'redirect'),(200,b'<html>captcha</html>'),(200,b'x'*70000),(200,b'{"error":"provider error"}')])
def test_provider_denials_and_html_are_not_bypassed(status, body, monkeypatch):
    calls = []
    class Response:
        status_code = status
        def iter_content(self, chunk_size): yield body
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def post(*args, **kwargs): calls.append((args, kwargs)); return Response()
    monkeypatch.setattr(generator.requests, "post", post)
    with pytest.raises(HTTPException) as error:
        generator.generate_person(generator.GeneratePersonArgs(), uuid.uuid4())
    assert error.value.status_code in (502, 503) and len(calls) == 1
    assert error.value.detail['provider_page'] == generator.PROVIDER_PAGE


def test_generator_rejects_caller_urls_and_invalid_filters(owner_env):
    _, client, _, _ = owner_env
    for body in ({"url": "http://localhost/secret"}, {"estado":"ZZ"}, {"idade":17}, {"sexo":"invalid"}):
        assert client.post('/manager/sender-generator/generate', json=body).status_code == 422


def test_manual_approval_is_required_and_only_sender_fields_are_saved(owner_env):
    factory, client, uid, _ = owner_env
    preview = generator.import_person(generator.ImportPersonArgs(json_text=json.dumps(person())))
    body = save_body(preview)
    unapproved = {**body, "approved": False}
    assert client.post('/manager/sender-generator/save', json=unapproved).status_code == 422
    missing = dict(body); missing.pop("approved")
    assert client.post('/manager/sender-generator/save', json=missing).status_code == 422
    body['data']['nome'] = 'Nome editado e revisado'
    result = client.post('/manager/sender-generator/save', json=body)
    assert result.status_code == 200 and not result.json()['reused']
    repeated = client.post('/manager/sender-generator/save', json=body)
    assert repeated.status_code == 200 and repeated.json()['reused']
    assert repeated.json()['id'] == result.json()['id']
    with factory() as db:
        row = db.query(PrintSender).one()
        assert row.data['nome'] == 'Nome editado e revisado'
        assert row.data['_generator']['synthetic'] is True and row.data['_generator']['reviewed_by'] == str(uid)
        assert 'generated-example-only' not in json.dumps(row.data) and 'TEST-ID' not in json.dumps(row.data)
        assert '_generator' not in sender_address(row)
    assert client.post('/manager/sender-generator/save', json={**body, 'source':'4devs_web_form'}).status_code == 409
    changed = {**body, 'name':'Other sender'}
    assert client.post('/manager/sender-generator/save', json=changed).status_code == 409


def test_sender_edit_keeps_synthetic_marker_out_of_printing_fields(owner_env):
    factory, client, _, _ = owner_env
    preview = generator.import_person(generator.ImportPersonArgs(json_text=json.dumps(person())))
    saved = client.post('/manager/sender-generator/save', json=save_body(preview)).json()
    result = client.get('/manager/senders').json()[0]
    assert result['synthetic'] is True and result['source'] == '4devs_json_import'
    body = {key: result[key] for key in ('name','lines','data','active','version')}
    body['data']['numero'] = '99'
    assert client.put('/manager/senders/' + saved['id'], json=body).status_code == 200
    again = client.get('/manager/senders').json()[0]
    assert again['synthetic'] is True and again['data']['numero'] == '99'
    assert '_generator' not in again['data']


def test_generator_and_save_require_authentication():
    app=FastAPI();app.include_router(api.router,prefix='/manager')
    client=TestClient(app)
    for path in ('generate','import','save'):
        assert client.post('/manager/sender-generator/'+path,json={}).status_code in (401,403)


@pytest.mark.parametrize('email,role', [
    ('wissam@eleven.com', UsuarioRole.GERENTE),
    ('denis@eleven.com', UsuarioRole.GERENTE),
    ('sol@eleven.com', UsuarioRole.GERENTE),
    ('junior@eleven.com', UsuarioRole.GERENTE),
    ('other-admin@example.test', UsuarioRole.ADMIN),
    ('lucas@eleven.com', UsuarioRole.GERENTE),
])
def test_generation_import_and_approval_are_exclusive_to_owner(owner_env, email, role):
    factory, client, uid, _ = owner_env
    with factory() as db:
        user = db.get(Usuario, uid)
        user.email, user.role = email, role
        db.commit()
    preview = generator.import_person(generator.ImportPersonArgs(json_text=json.dumps(person())))
    for path, payload in [('generate', {}), ('import', {'json_text':json.dumps(person())}), ('save', save_body(preview))]:
        response = client.post('/manager/sender-generator/' + path, json=payload)
        assert response.status_code == 403, response.text
    with factory() as db:
        assert db.query(PrintSender).count() == 0


def test_team_keeps_normal_sender_operations_without_generator_permission(owner_env):
    factory, client, uid, _ = owner_env
    with factory() as db:
        user = db.get(Usuario, uid)
        user.email, user.role = 'wissam@eleven.com', UsuarioRole.GERENTE
        db.commit()
    body = {'name':'Remetente cadastrado manualmente','lines':['Nome Teste','Rua Teste, 12'],'data':{'pais':'BR','nome':'Nome Teste'},'active':True}
    response = client.post('/manager/senders', json=body)
    assert response.status_code == 200, response.text
    sender_id = response.json()['id']
    assert client.get('/manager/senders').json()[0]['id'] == sender_id
    response = client.put('/manager/senders/' + sender_id, json={**body,'version':1,'name':'Remetente editado'})
    assert response.status_code == 200, response.text
