"""Regression: synchronous authentication must never freeze the ASGI loop."""
import asyncio
import threading
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import Depends, FastAPI

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user


def test_slow_auth_database_does_not_block_unrelated_requests():
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    class SlowDatabase:
        def get(self, model, key):
            entered.set()
            release.wait(timeout=2)
            finished.set()
            return None

    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: SlowDatabase()

    @app.get('/protected')
    def protected(user=Depends(get_current_user)):
        return {'ok': True}

    @app.get('/probe')
    async def probe():
        return {'ok': True}

    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': str(uuid.uuid4()), 'sid': str(uuid.uuid4()), 'ver': 1,
                        'iat': now, 'exp': now + timedelta(minutes=1)}, settings.SECRET_KEY, algorithm='HS256')

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            auth = asyncio.create_task(client.get('/protected', headers={'Authorization': 'Bearer ' + token}))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                result = await asyncio.wait_for(client.get('/probe'), timeout=0.5)
                assert result.status_code == 200
                assert not finished.is_set(), 'Authentication blocked the event loop until DB timeout'
            finally:
                release.set()
                response = await auth
            assert response.status_code == 401

    asyncio.run(run())
