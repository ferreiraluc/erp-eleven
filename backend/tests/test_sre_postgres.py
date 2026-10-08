from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import threading
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from app.database import Base
from app.models.operations import LoginThrottle,ScheduledRun
from app.models.access import now
from app.services.login_throttle import login_limit
from app.services.scheduled_tracking import run_daily
from test_access_postgres import pg,upgrade


def isolated(pg):
    engine,schema=pg
    target=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    with target.begin() as connection:upgrade(connection,'b4c5d6e7f8a9_operational_safety.py')
    return target,sessionmaker(bind=target)


def test_shared_throttle_survives_connections_and_concurrent_attempts(pg):
    engine,factory=isolated(pg);at=now()
    try:
        def attempt(_):
            with factory() as db:
                try:login_limit(db,'fixture@example.com','127.0.0.1',at=at);return 200
                except HTTPException as exc:return exc.status_code
        with ThreadPoolExecutor(max_workers=6) as pool:out=list(pool.map(attempt,range(20)))
        assert out.count(200)==12 and out.count(429)==8
        with factory() as db:
            assert db.query(LoginThrottle).count()==3
            login_limit(db,'fixture@example.com','127.0.0.1',at=at+timedelta(seconds=601))
    finally:engine.dispose()


def test_tracking_scheduler_runs_once_across_overlapping_instances(pg):
    engine,factory=isolated(pg);started=threading.Event();release=threading.Event();calls=[]
    def refresh(db):
        calls.append(1);started.set();assert release.wait(5)
        return {'updated':1,'errors':[],'skipped':[]}
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(run_daily,factory,refresh);assert started.wait(3)
            assert run_daily(factory,refresh) is None
            release.set();assert first.result(timeout=5)['updated']==1
        assert run_daily(factory,refresh) is None and len(calls)==1
        with factory() as db:assert db.query(ScheduledRun).count()==1
    finally:release.set();engine.dispose()
