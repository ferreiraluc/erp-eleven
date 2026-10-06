"""Custom frontend domains must pass the browser's preflight, without wildcard access."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.parametrize('origin,allowed', [
    ('https://elevenparispy.com',True),
    ('https://www.elevenparispy.com',True),
    ('https://erp-eleven-frontend.onrender.com',True),
    ('https://elevenparispy.com.attacker.example',False),
    ('https://unknown.elevenparispy.com',False),
    ('http://elevenparispy.com',False),
])
def test_login_and_authorized_requests_preflight(origin,allowed):
    # No lifespan, DB access or actual login attempts are needed.
    client=TestClient(app)
    for path,method,headers in [('/api/auth/login','POST','content-type'),('/api/auth/me','GET','authorization,content-type')]:
        r=client.options(path,headers={'Origin':origin,'Access-Control-Request-Method':method,
                                     'Access-Control-Request-Headers':headers})
        assert r.status_code==(200 if allowed else 400)
        assert r.headers.get('access-control-allow-origin')==(origin if allowed else None)
