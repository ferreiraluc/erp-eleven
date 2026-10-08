from datetime import timedelta
from io import StringIO
import logging
from types import SimpleNamespace
import jwt
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.database import engine_options
from app.services.safe_logging import RedactionFilter
from app.services import worker_health
from app.services.user_sessions import get_password_hash
from test_access import setup,login


def test_logging_never_emits_provider_secrets_queries_or_exception_parameters(monkeypatch):
    monkeypatch.setattr(settings,'TELEGRAM_BOT_TOKEN','private-bot-token-fixture')
    output=StringIO();handler=logging.StreamHandler(output);handler.addFilter(RedactionFilter())
    logger=logging.getLogger('sre-fixture');logger.addHandler(handler);logger.setLevel(logging.INFO)
    try:
        logger.info('GET /api/clientes?q=private-name&cpf=123.456.789-01 private-bot-token-fixture https://user:pass@host/private?token=secret')
        try:raise ValueError('SQL parameters private-name secret-password')
        except ValueError:logger.exception('operation failed')
    finally:logger.removeHandler(handler)
    value=output.getvalue()
    assert 'private-name' not in value and 'private-bot-token' not in value and 'secret-password' not in value
    assert '123.456.789-01' not in value and 'user:pass' not in value and 'token=secret' not in value
    assert 'ValueError' in value


def test_health_reports_failure_closes_connection_and_detects_stalled_worker(monkeypatch):
    from app import main
    class DB:
        bind=SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))
        closed=False
        def __enter__(self):return self
        def __exit__(self,*args):self.closed=True
        def execute(self,*args):raise RuntimeError('private connection URL')
    db=DB();monkeypatch.setattr(main,'SessionLocal',lambda:db)
    monkeypatch.setattr(settings,'ASSISTANT_ENABLED',False)
    for attr,name in [('label_worker','labels'),('sales_bi_worker','sales_bi')]:
        monkeypatch.setattr(main.app.state,attr,SimpleNamespace(is_alive=lambda:True),raising=False);worker_health.beat(name)
    client=TestClient(main.app)
    r=client.get('/health');assert r.status_code==503 and r.json()['database']=='offline' and db.closed
    assert r.headers['cache-control']=='no-store' and 'private connection' not in r.text
    assert client.get('/live').status_code==200
    monkeypatch.setattr(DB,'execute',lambda *args:1)
    assert client.get('/health').status_code==200
    monkeypatch.setitem(worker_health._progress,'labels',worker_health.time.monotonic()-601)
    r=client.get('/health');assert r.status_code==503 and r.json()['label_worker']=='stalled'


def test_postgres_connections_have_limits_but_sqlite_does_not_receive_pg_options(monkeypatch):
    opts=engine_options('postgresql://unused@localhost/test')
    assert opts['pool_pre_ping'] and opts['hide_parameters'] and opts['pool_timeout']<=5
    assert 'statement_timeout=' in opts['connect_args']['options']
    assert 'connect_args' not in engine_options('sqlite://')
    monkeypatch.setattr(settings,'PRODUCTION',True)
    assert engine_options('postgresql://unused@host/test?sslmode=disable')['connect_args']['sslmode']=='require'
    assert engine_options('postgresql://unused@host/test?sslmode=verify-full')['connect_args']['sslmode']=='verify-full'


def test_production_rejects_default_secrets_and_wrong_algorithm(monkeypatch):
    monkeypatch.setattr(settings,'PRODUCTION',True)
    monkeypatch.setattr(settings,'SECRET_KEY','your-secret-key-change-this')
    with pytest.raises(RuntimeError,match='SECRET_KEY'):settings.validate_runtime()
    monkeypatch.setattr(settings,'ALGORITHM','RS256')
    with pytest.raises(RuntimeError,match='ALGORITHM'):settings.validate_runtime()


def test_new_password_policy_does_not_disable_legacy_password_logins(setup):
    client,factory,ids=setup
    from app.models import Usuario
    import bcrypt
    with factory() as db:
        db.get(Usuario,ids['Lucas'][0]).senha_hash=bcrypt.hashpw(b'legacy',bcrypt.gensalt()).decode();db.commit()
    headers=login(client,password='legacy')
    assert client.post('/api/auth/password',headers=headers,json={'current_password':'legacy','new_password':'short'}).status_code==422
    assert client.post('/api/auth/password',headers=headers,json={'current_password':'legacy','new_password':'a'*12}).status_code==422
    with pytest.raises(ValueError):get_password_hash('123456789012')


def test_jwt_requires_signed_claims_and_rejects_algorithm_switch(setup):
    client,_,_=setup;headers=login(client)
    payload=jwt.decode(headers['Authorization'][7:],settings.SECRET_KEY,algorithms=['HS256'])
    for key in ('exp','iat','sid','ver'):
        changed={k:v for k,v in payload.items() if k!=key}
        token=jwt.encode(changed,settings.SECRET_KEY,algorithm='HS256')
        assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401
    token=jwt.encode(payload,settings.SECRET_KEY,algorithm='HS384')
    assert client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401
