"""Login defenses against injection, enumeration and rotating attacker identities."""
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event

from app.api.endpoints import auth
from app.schemas.usuario import UsuarioLogin
from test_access import setup, login


def test_injection_never_changes_query_structure_or_authenticates(setup):
    client, factory, _ = setup
    malicious = "' OR 1=1 --"
    with factory() as db:
        queries = []
        def capture(conn, cursor, statement, parameters, context, many):
            queries.append((statement, parameters))
        event.listen(db.bind, 'before_cursor_execute', capture)
        try:
            assert auth.authenticate_user(db, malicious, malicious) is None
        finally:
            event.remove(db.bind, 'before_cursor_execute', capture)
        assert any(malicious.lower() in params and malicious.lower() not in sql.lower() for sql, params in queries)
    assert client.post('/api/auth/login', json={'email': 'lucas@eleven.com', 'senha': malicious}).status_code == 401
    assert client.post('/api/auth/login', json={'email': malicious, 'senha': malicious}).status_code == 422
    assert login(client)


def test_missing_account_still_checks_a_hash_and_returns_same_error(setup, monkeypatch):
    client, factory, _ = setup
    original = auth.verify_password
    check = Mock(wraps=original)
    monkeypatch.setattr(auth, 'verify_password', check)
    missing = client.post('/api/auth/login', json={'email': 'missing@eleven.com', 'senha': 'wrong'})
    assert check.call_count == 1 and check.call_args.args[1] == auth._dummy_hash
    wrong = client.post('/api/auth/login', json={'email': 'lucas@eleven.com', 'senha': 'wrong'})
    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == wrong.json()


def test_rotating_ips_and_emails_do_not_reset_limits(setup):
    from datetime import timedelta
    from app.models.access import now
    from app.models.operations import LoginThrottle
    from app.services.login_throttle import login_limit
    _,factory,_ = setup
    at=now()
    with factory() as db:
        for i in range(30): login_limit(db,'lucas@eleven.com',str(i),at=at)
        with pytest.raises(HTTPException) as blocked:
            login_limit(db,'LUCAS@eleven.com','another',at=at)
        assert blocked.value.status_code==429 and blocked.value.headers['Retry-After']=='600'
        db.query(LoginThrottle).delete();db.commit()
        for i in range(60):login_limit(db,f'user{i}@eleven.com','one-ip',at=at)
    # A different session/process sees the same counter, including failed requests.
    with factory() as db:
        with pytest.raises(HTTPException):login_limit(db,'another@eleven.com','one-ip',at=at)
        login_limit(db,'another@eleven.com','one-ip',at=at+timedelta(seconds=601))
        assert all('@' not in r.bucket and len(r.bucket)==64 for r in db.query(LoginThrottle))


def test_password_length_is_bounded_without_truncating():
    for password in ('x' * 73, 'é' * 37):
        with pytest.raises(ValidationError): UsuarioLogin(email='lucas@eleven.com', senha=password)
    value = 'a\'" <>&' * 4
    assert UsuarioLogin(email='lucas@eleven.com', senha=value).senha == value


def test_api_validation_does_not_echo_credentials():
    from fastapi.testclient import TestClient
    from app.main import app
    # Validation runs before database work. Explicit invalid inputs only.
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: None
    try:
        response = TestClient(app).post('/api/auth/login', json={'email': 'invalid', 'senha': 'PRIVATE-CREDENTIAL-' * 20})
        assert response.status_code == 422
        assert 'PRIVATE-CREDENTIAL' not in response.text
        assert all('input' not in error and 'ctx' not in error for error in response.json()['detail'])
    finally:
        app.dependency_overrides.pop(get_db, None)
