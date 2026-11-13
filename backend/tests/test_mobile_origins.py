"""Exercise real API CORS without starting workers or reading operational data."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize('origin', ['capacitor://localhost', 'https://localhost', 'https://elevenparispy.com'])
def test_bundled_mobile_and_web_origins_can_preflight_but_still_need_auth(origin):
    # No context manager: lifespan/migrations/workers must not run in this test.
    client = TestClient(app)
    preflight = client.options('/api/auth/me', headers={
        'Origin': origin, 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'authorization',
    })
    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == origin
    response = client.get('/api/auth/me', headers={'Origin': origin})
    assert response.status_code == 401
    assert response.headers['access-control-allow-origin'] == origin
    assert response.headers['cache-control'] == 'no-store, private'


@pytest.mark.parametrize('origin', ['https://untrusted.invalid', 'capacitor://attacker', 'http://localhost'])
def test_mobile_support_does_not_allow_arbitrary_origins(origin):
    response = TestClient(app).options('/api/auth/me', headers={
        'Origin': origin, 'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'authorization',
    })
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
