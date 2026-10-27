"""Disposable owner-only API fixtures; no actual diagnostics, AI, payments or prints."""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_active_user
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.access import AuditEvent
from app.models.system_quality import QualityConfig, QualityRun
from app.api.endpoints import system_quality as api
from app.services import quality_checks, quality_summary, system_quality as service

MOMENT = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)
MODELS = (Usuario, Vendedor, AuditEvent, QualityConfig, QualityRun)


@pytest.fixture
def setup(monkeypatch):
    engine = sa.create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in MODELS])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    ids = {}
    with factory() as db:
        for name, role in [('Lucas', UsuarioRole.ADMIN), ('Sol', UsuarioRole.GERENTE), ('OtherAdmin', UsuarioRole.ADMIN)]:
            value = Usuario(id=uuid.uuid4(), nome=name, email=name.lower() + '@eleven.com', senha_hash='unused', role=role, ativo=True)
            db.add(value)
            ids[name] = value.id
        db.commit()
    def forbidden(*args, **kwargs):
        raise AssertionError('API must only queue; diagnostics and providers belong to the worker.')
    monkeypatch.setattr(quality_checks, 'collect', forbidden)
    monkeypatch.setattr(quality_summary, 'summarize', forbidden)
    app = FastAPI()
    app.include_router(api.router, prefix='/api/quality')
    def session():
        with factory() as db:
            yield db
    def current(request: Request):
        with factory() as db:
            value = db.get(Usuario, ids.get(request.headers.get('X-User', 'Sol')))
            if not value:
                raise HTTPException(401)
            return value
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = current
    with TestClient(app) as client:
        yield client, factory, ids
    engine.dispose()


def owner():
    return {'X-User': 'Lucas'}


def config_body(version=1, **values):
    return {'expected_version': version, 'enabled': True, 'ai_enabled': True, 'local_time': '08:30', **values}


def test_lucas_only_even_an_unrecognized_admin_cannot_view_or_queue(setup):
    client, factory, _ = setup
    for name in ['Sol', 'OtherAdmin']:
        headers = {'X-User': name}
        assert client.get('/api/quality/admin', headers=headers).status_code == 403
        assert client.put('/api/quality/config', headers=headers, json=config_body()).status_code == 403
        assert client.post('/api/quality/scan', headers=headers, json={'request_id': str(uuid.uuid4())}).status_code == 403
        assert client.get('/api/quality/admin/runs/' + str(uuid.uuid4()), headers=headers).status_code == 403
    with factory() as db:
        assert db.query(QualityRun).count() == db.query(QualityConfig).count() == 0


def test_admin_read_has_bounded_fixed_limits_and_never_starts_scan(setup):
    client, factory, _ = setup
    response = client.get('/api/quality/admin', headers=owner())
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['config']['local_time'] == '08:30'
    assert value['config']['timezone'] == 'America/Sao_Paulo'
    assert value['latest'] is None and value['runs'] == []
    assert value['limits'] == service.limits()
    assert value['limits']['max_provider_calls_per_day'] == 2
    assert client.get('/api/quality/admin?limit=31', headers=owner()).status_code == 422
    with factory() as db:
        assert db.query(QualityRun).count() == 0


def test_config_is_versioned_validates_schedule_and_preserves_ai_budget(setup, monkeypatch):
    client, factory, ids = setup
    client.get('/api/quality/admin', headers=owner())
    with factory() as db:
        config = db.get(QualityConfig, 1)
        config.ai_reserved_on = MOMENT.date()
        db.commit()
    monkeypatch.setattr(api, 'now', lambda: MOMENT)
    response = client.put('/api/quality/config', headers=owner(), json=config_body(local_time='09:15', ai_enabled=False))
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['version'] == 2 and value['local_time'] == '09:15' and not value['ai_enabled']
    assert value['first_run_on'] == '2026-10-28'  # No late-evening run on Save.
    assert value['ai_reserved_on'] == '2026-10-27'
    assert client.put('/api/quality/config', headers=owner(), json=config_body()).status_code == 409
    for clock in ['24:00', '9:00', '08:99', 'bad']:
        assert client.put('/api/quality/config', headers=owner(), json=config_body(2, local_time=clock)).status_code == 422
    assert client.put('/api/quality/config', headers=owner(), json=config_body(2, max_provider_calls_per_day=100)).status_code == 422
    assert client.put('/api/quality/config', headers=owner(), json=config_body(2, enabled='false')).status_code == 422
    with factory() as db:
        config = db.get(QualityConfig, 1)
        assert config.updated_by == ids['Lucas']
        event = db.query(AuditEvent).one()
        assert event.changes == {'enabled': True, 'ai_enabled': False, 'local_time': '09:15'}
        assert db.query(QualityRun).count() == 0


def test_manual_scan_only_queues_and_replayed_request_id_is_idempotent(setup):
    client, factory, ids = setup
    request_id = str(uuid.uuid4())
    first = client.post('/api/quality/scan', headers=owner(), json={'request_id': request_id})
    assert first.status_code == 202, first.text
    second = client.post('/api/quality/scan', headers=owner(), json={'request_id': request_id})
    assert second.status_code == 202 and second.json()['id'] == first.json()['id']
    assert first.json()['status'] == 'queued' and first.json()['kind'] == 'manual'
    assert first.json()['requested_by'] == str(ids['Lucas'])
    assert client.post('/api/quality/scan', headers=owner(), json={'request_id': str(uuid.uuid4())}).status_code == 409
    assert client.post('/api/quality/scan', headers=owner(), json={'request_id': str(uuid.uuid4()), 'requested_by': str(ids['Sol'])}).status_code == 422
    with factory() as db:
        assert db.query(QualityRun).count() == 1
        row = db.query(QualityRun).one()
        assert row.provider_calls == 0 and not row.ai_attempted
        assert row.findings == []


def test_findings_are_paginated_allowlisted_and_history_cards_omit_them(setup):
    client, factory, _ = setup
    rid = uuid.uuid4()
    identities = [uuid.uuid4() for _ in range(140)]
    with factory() as db:
        db.add(QualityRun(id=rid, run_day=MOMENT.date(), kind='daily', status='completed',
            findings=[{'key': 'inventory_missing_metadata', 'entity_type': 'inventory', 'entity_id': str(identity),
                       'severity': 'info', 'customer_name': 'private field', 'image_data': 'private photo'} for identity in identities],
            counters={'inventory_balance': 2, 'private_free_text': 'Not allowed'},
            coverage={'inventory': {'checked': 500, 'complete': False, 'window': 'last_24_hours', 'unsafe': 'private'}}))
        db.commit()
    admin = client.get('/api/quality/admin', headers=owner()).json()
    assert len(admin['latest']['findings']) == 30 and admin['latest']['findings_total'] == 100
    assert 'findings' not in admin['runs'][0]
    assert admin['latest']['counters'] == {'inventory_balance': 2}
    assert 'private' not in str(admin)
    detail = client.get(f'/api/quality/admin/runs/{rid}?findings_offset=30&findings_limit=10', headers=owner()).json()
    assert [entry['entity_id'] for entry in detail['findings']] == [str(identity) for identity in identities[30:40]]
    assert client.get(f'/api/quality/admin/runs/{rid}?findings_limit=101', headers=owner()).status_code == 422
    assert client.get('/api/quality/admin/runs/' + str(uuid.uuid4()), headers=owner()).status_code == 404


@pytest.fixture
def pg_setup(pg):
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(isolated, tables=[model.__table__ for model in MODELS])
    factory = sessionmaker(bind=isolated, autoflush=False, expire_on_commit=False)
    uid = uuid.uuid4()
    with factory() as db:
        db.add(Usuario(id=uid, nome='Lucas fixture', email='lucas@eleven.com', senha_hash='unused', role=UsuarioRole.ADMIN, ativo=True))
        service.ensure_config(db)
        db.commit()
    try:
        yield factory, uid
    finally:
        isolated.dispose()


def test_postgres_overlapping_config_edits_are_compare_and_swap(pg_setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from types import SimpleNamespace
    from app.schemas.system_quality import QualityConfigUpdate
    factory, uid = pg_setup
    ready = Barrier(2)
    def change(clock):
        with factory() as db:
            ready.wait(timeout=10)
            try:
                response = api.update_config(QualityConfigUpdate(**config_body(local_time=clock)), owner=SimpleNamespace(id=uid), db=db)
                return response['version']
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(change, ['09:00', '10:00']))
    assert sorted(results) == [2, 409]
    with factory() as db:
        assert db.get(QualityConfig, 1).version == 2
        assert db.query(AuditEvent).count() == 1


def test_postgres_same_request_retries_queue_only_one_run(pg_setup):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from types import SimpleNamespace
    from app.schemas.system_quality import QualityScanRequest
    factory, uid = pg_setup
    request_id = uuid.uuid4()
    ready = Barrier(2)
    def request(_):
        with factory() as db:
            ready.wait(timeout=10)
            result = api.request_scan(QualityScanRequest(request_id=request_id), owner=SimpleNamespace(id=uid), db=db)
            return result['id']
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(request, range(2)))
    assert ids[0] == ids[1]
    with factory() as db:
        row = db.query(QualityRun).one()
        assert row.status == 'queued' and row.provider_calls == 0 and not row.ai_attempted


def test_postgres_manual_budget_is_backend_enforced_and_retries_survive_exhaustion(pg_setup):
    from types import SimpleNamespace
    from app.schemas.system_quality import QualityScanRequest
    factory, uid = pg_setup
    first_request = uuid.uuid4()
    with factory() as db:
        for index in range(3):
            result = api.request_scan(QualityScanRequest(request_id=first_request if index == 0 else uuid.uuid4()),
                                      owner=SimpleNamespace(id=uid), db=db)
            db.get(QualityRun, result['id']).status = 'completed'
            db.commit()
        with pytest.raises(HTTPException) as denied:
            api.request_scan(QualityScanRequest(request_id=uuid.uuid4()), owner=SimpleNamespace(id=uid), db=db)
        assert denied.value.status_code == 429
        db.rollback()
        retry = api.request_scan(QualityScanRequest(request_id=first_request), owner=SimpleNamespace(id=uid), db=db)
        assert retry['status'] == 'completed'
        assert db.query(QualityRun).count() == 3


# Reuse the existing disposable-schema fixture; it rejects non-local database URLs.
from test_access_postgres import pg
