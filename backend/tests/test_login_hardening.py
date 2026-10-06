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


def test_rotating_ips_and_emails_do_not_reset_limits(monkeypatch):
    auth._attempts.clear()
    monkeypatch.setattr(auth.time, 'monotonic', lambda: 1000)
    try:
        for i in range(30): auth.login_limit('lucas@eleven.com', str(i))
        with pytest.raises(HTTPException) as blocked:
            auth.login_limit('LUCAS@eleven.com', 'another')
        assert blocked.value.status_code == 429 and blocked.value.headers['Retry-After'] == '600'
        auth._attempts.clear()
        for i in range(60): auth.login_limit(f'user{i}@eleven.com', 'one-ip')
        with pytest.raises(HTTPException): auth.login_limit('another@eleven.com', 'one-ip')
        monkeypatch.setattr(auth.time, 'monotonic', lambda: 1601)
        auth.login_limit('another@eleven.com', 'one-ip')
    finally:
        auth._attempts.clear()


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
