"""Daily sign-out deadlines, including an uninterrupted legacy deployment."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest

from app import dependencies
from app.config import settings
from app.models.access import AuthSession
from app.models.usuario import Usuario
from app.services import user_sessions
from app.services.user_sessions import effective_session_expiry, next_daily_session_expiry
from test_access import setup, login


@pytest.mark.parametrize(('moment', 'expected'), [
    ('2026-10-27T23:59:59+00:00', '2026-10-28T00:00:00+00:00'),
    ('2026-10-28T00:00:00+00:00', '2026-10-29T00:00:00+00:00'),
    ('2026-10-28T01:30:00+00:00', '2026-10-29T00:00:00+00:00'),
    ('2026-10-27T20:00:00-03:00', '2026-10-28T00:00:00+00:00'),
    ('2026-10-28T00:15:00-03:00', '2026-10-29T00:00:00+00:00'),
])
def test_cutoff_is_the_next_brasilia_closing_time(moment, expected):
    assert next_daily_session_expiry(datetime.fromisoformat(moment)) == datetime.fromisoformat(expected)


@pytest.mark.parametrize(('issued_text', 'expected', 'duration'), [
    ('2026-10-27T23:59:59+00:00', '2026-10-28T00:00:00+00:00', 1),
    ('2026-10-28T00:00:00+00:00', '2026-10-29T00:00:00+00:00', 86400),
    ('2026-10-28T01:30:00+00:00', '2026-10-29T00:00:00+00:00', 81000),
])
def test_new_token_and_database_session_share_the_same_daily_deadline(monkeypatch, issued_text, expected, duration):
    issued = datetime.fromisoformat(issued_text)
    monkeypatch.setattr(user_sessions, 'now', lambda: issued)
    sessions = []
    user = SimpleNamespace(id=uuid.uuid4(), auth_version=2)
    result = user_sessions.issue_session(SimpleNamespace(add=sessions.append), user)
    payload = jwt.decode(result['access_token'], settings.SECRET_KEY, algorithms=['HS256'],
                         options={'verify_exp': False, 'verify_iat': False})
    assert result['expires_in'] == duration
    assert payload['exp'] == int(datetime.fromisoformat(expected).timestamp())
    assert sessions[0].created_at == issued
    assert effective_session_expiry(sessions[0]).timestamp() == payload['exp']


def test_legacy_cutoff_preserves_an_earlier_expiry_and_does_not_slide_each_day():
    created = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
    activation_cutoff = datetime(2026, 10, 28, tzinfo=timezone.utc)
    session = AuthSession(created_at=created, expires_at=created + timedelta(days=7),
                          daily_expires_at=activation_cutoff)
    assert effective_session_expiry(session) == activation_cutoff
    session.expires_at = activation_cutoff - timedelta(hours=1)
    assert effective_session_expiry(session) == session.expires_at


def test_overlapping_older_api_cannot_create_an_unlimited_session_after_migration():
    created = datetime(2026, 10, 27, 23, 59, 59)  # SQLite's naive UTC round trip.
    session = AuthSession(created_at=created, expires_at=created + timedelta(days=7))
    assert effective_session_expiry(session) == datetime(2026, 10, 28, tzinfo=timezone.utc)


def test_api_refuses_a_legacy_long_jwt_at_the_daily_cutoff_and_returns_deadline_before_it(setup, monkeypatch):
    client, factory, ids = setup
    # A genuinely signed legacy token still has a future cryptographic expiry.
    now = datetime.now(timezone.utc)
    deadline = next_daily_session_expiry(now)
    sid = uuid.uuid4()
    with factory() as db:
        user = db.get(Usuario, ids['Sol'][0])
        db.add(AuthSession(id=sid, user_id=user.id, created_at=now-timedelta(days=2),
                           expires_at=now+timedelta(days=5), daily_expires_at=deadline))
        token = jwt.encode({'sub': str(user.id), 'sid': str(sid), 'ver': user.auth_version,
                            'iat': now-timedelta(days=2), 'exp': now+timedelta(days=5)},
                           settings.SECRET_KEY, algorithm='HS256')
        db.commit()
    headers = {'Authorization': 'Bearer '+token}
    monkeypatch.setattr(dependencies, 'now', lambda: deadline-timedelta(seconds=1))
    response = client.get('/api/auth/me', headers=headers)
    assert response.status_code == 200, response.text
    assert datetime.fromisoformat(response.json()['session_expires_at'].replace('Z', '+00:00')) == deadline
    monkeypatch.setattr(dependencies, 'now', lambda: deadline)
    assert client.get('/api/auth/me', headers=headers).status_code == 401
    monkeypatch.setattr(dependencies, 'now', lambda: deadline+timedelta(hours=25))
    assert client.get('/api/auth/me', headers=headers).status_code == 401


def test_normal_login_exposes_the_persisted_deadline_without_exposing_token_contents(setup):
    client, factory, _ = setup
    response = client.get('/api/auth/me', headers=login(client, 'Junior'))
    with factory() as db:
        session = db.query(AuthSession).one()
        assert response.status_code == 200
        assert datetime.fromisoformat(response.json()['session_expires_at'].replace('Z', '+00:00')) == effective_session_expiry(session)
    assert 'access_token' not in response.json() and 'daily_expires_at' not in response.json()
