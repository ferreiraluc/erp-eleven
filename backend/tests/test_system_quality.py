"""Disposable fixtures; all AI calls are mocks and diagnostics never change data."""
from datetime import datetime, timedelta, timezone
import json
from threading import Event
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
import requests
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Usuario, Vendedor
from app.models.usuario import UsuarioRole
from app.models.access import AuditEvent, AuthSession
from app.models.inventory import Item, Supplier
from app.models.cliente import Cliente
from app.models.pdv import PdvCliente, PdvSale, PdvSaleItem
from app.models.printing import PrintDevice, PrintJob
from app.models.address_book import SavedAddress
from app.models.sales_bi import SalesBIConfig
from app.models.notification import Notification, NotificationRecipient, NotificationRevision, NotificationPreference
from app.models.notification_push import NotificationPushSubscription, NotificationPushDelivery
from app.models.system_quality import QualityConfig, QualityRun
from app.services import quality_checks, quality_summary, system_quality

MOMENT = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)  # 09:00 BRT.
MODELS = (Usuario, Vendedor, AuditEvent, AuthSession, Supplier, Item, Cliente, PdvCliente, PdvSale, PdvSaleItem,
          SavedAddress, PrintDevice, PrintJob, SalesBIConfig, Notification, NotificationRecipient, NotificationRevision,
          NotificationPreference, NotificationPushSubscription, NotificationPushDelivery, QualityConfig, QualityRun)


@pytest.fixture
def factory():
    engine = sa.create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in MODELS])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add(Usuario(id=uuid.uuid4(), nome='Lucas', email='lucas@eleven.com', senha_hash='unused', role=UsuarioRole.ADMIN))
        db.add(QualityConfig(id=1, first_run_on=MOMENT.date(), local_time='08:30'))
        db.commit()
    yield factory
    engine.dispose()


def test_installing_at_night_starts_tomorrow_and_has_no_side_effects(factory):
    with factory() as db:
        db.query(QualityConfig).delete()
        config = system_quality.ensure_config(db, datetime(2026, 10, 27, 2, tzinfo=timezone.utc))  # 26/10 23:00 BRT.
        assert config.first_run_on.isoformat() == '2026-10-27'
        assert system_quality.claim_run(db, datetime(2026, 10, 27, 2, tzinfo=timezone.utc)) is None
        assert db.query(QualityRun).count() == 0
        assert db.query(Notification).count() == 0


def test_daily_claim_uses_brazilian_day_and_is_once_only(factory):
    with factory() as db:
        assert system_quality.claim_run(db, MOMENT.replace(hour=11, minute=29)) is None
        first = system_quality.claim_run(db, MOMENT)
        db.commit()
        assert first
        assert system_quality.claim_run(db, MOMENT) is None
        row = db.get(QualityRun, first.id)
        row.status = 'completed'
        row.lease_until = None
        db.commit()
        assert system_quality.claim_run(db, MOMENT + timedelta(hours=10)) is None


def test_expired_claim_can_recover_but_stale_worker_cannot_write(factory):
    with factory() as db:
        first = system_quality.claim_run(db, MOMENT)
        db.commit()
        again = system_quality.claim_run(db, MOMENT + timedelta(minutes=4))
        assert again.id == first.id and again.token != first.token
        report = {'counters': {}, 'findings': [], 'coverage': {'inventory': {'checked': 0, 'complete': True}}}
        assert not system_quality.complete_run(db, first, report, quality_summary.QualitySummary('disabled'))
        assert system_quality.complete_run(db, again, report, quality_summary.QualitySummary('disabled'))
        db.commit()
        assert db.query(Notification).count() == 1


def test_projection_checks_detect_recent_issues_without_modifying_operational_rows(factory):
    ids = [uuid.uuid4() for _ in range(5)]
    with factory() as db:
        db.add(Item(id=ids[0], name='Private client style', sku_internal='TEST-LOCAL', current_stock=4,
                    stock_loja=1, stock_deposito=1, min_stock=5, max_stock=2, sale_price=0,
                    image_data='private-original-image', additional_images=['private-gallery'], updated_at=MOMENT))
        db.add(PdvSale(id=ids[1], created_at=MOMENT, status='completed', notas=' '))
        db.flush()
        db.add(PdvSaleItem(sale_id=ids[1], item_name='Secret item', is_avulso=True, item_id=None, quantity=1, unit_price_gs=10, total_gs=10))
        db.add(PrintDevice(id=ids[2], name='Fixture', token_hash='fixturehash', active=True, last_seen_at=MOMENT - timedelta(hours=1)))
        db.flush()
        db.add(PrintJob(id=ids[3], device_id=ids[2], user_id=db.query(Usuario.id).scalar(), request_key=uuid.uuid4(),
                        pdf=b'private-pdf', sha256='fixture', status='uncertain', created_at=MOMENT - timedelta(minutes=1), expires_at=MOMENT + timedelta(hours=1)))
        db.commit()
    captured = []
    engine = factory.kw['bind']
    def capture(conn, cursor, statement, parameters, context, many): captured.append(statement.lower())
    sa.event.listen(engine, 'before_cursor_execute', capture)
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online', 'sales_bi': 'stalled'})
    sa.event.remove(engine, 'before_cursor_execute', capture)
    assert report['counters']['inventory_balance'] == 1
    assert report['counters']['inventory_limits'] == 1
    assert report['counters']['inventory_missing_metadata'] == 1
    assert report['counters']['sale_avulso_without_reason'] == 1
    assert report['counters']['print_uncertain'] == 1
    assert report['counters']['worker_problem'] == 1
    assert not any(any(secret in sql for secret in ('image_data', 'additional_images', 'print_jobs.pdf', 'snapshot', 'pdv_sales.cliente_nome')) for sql in captured)
    assert 'private' not in json.dumps(report)
    with factory() as db:
        assert db.get(Item, ids[0]).current_stock == 4
        assert db.get(PrintJob, ids[3]).status == 'uncertain'
        assert db.query(PdvSaleItem).count() == 1


def test_large_cohort_is_bounded_and_reports_incomplete(factory):
    with factory() as db:
        for index in range(505):
            db.add(Item(name=f'Fixture {index}', sku_internal=f'LOCAL-{index}', updated_at=MOMENT))
        db.commit()
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online'})
    assert report['coverage']['inventory']['checked'] == 500
    assert not report['coverage']['inventory']['complete']
    assert len(report['findings']) == quality_checks.MAX_FINDINGS
    assert report['counters']['inventory_missing_metadata'] == 500


def test_sales_coverage_counts_inspected_sales_and_valid_avulso_is_not_error(factory):
    with factory() as db:
        for index in range(104):
            sale = PdvSale(id=uuid.uuid4(), created_at=MOMENT - timedelta(minutes=index), status='completed',
                           notas='Venda avulsa previamente conferida' if index == 0 else '')
            db.add(sale); db.flush()
            if index == 0:
                db.add(PdvSaleItem(sale_id=sale.id, item_name='Fixture', is_avulso=True, unit_price_gs=1, total_gs=1))
        db.commit()
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online'})
    assert report['coverage']['sales']['checked'] == 100
    assert report['coverage']['sales']['complete'] is False
    assert report['counters'].get('sale_avulso_without_reason', 0) == 0


def test_one_checker_failure_is_visible_and_does_not_hide_other_checks(factory, monkeypatch):
    def fail(*args): raise RuntimeError('do not expose customer data')
    monkeypatch.setitem(quality_checks.FUNCTIONS, 'inventory', fail)
    report = quality_checks.collect(factory, MOMENT, {'notifications': 'online'})
    assert report['coverage']['inventory']['error'] == 'check_unavailable'
    assert report['coverage']['workers']['complete']
    assert 'customer data' not in json.dumps(report)


def test_aggregate_input_has_no_free_text_ids_personal_data_or_unknown_keys():
    payload = quality_summary.aggregate_payload({'print_stale': 5, 'customer_name': 'Secret Name',
        'worker_problem': 'secret@fixture.local', 'inventory_balance': -3},
        {'inventory': {'complete': True, 'names': ['Private Name']}, 'evil': {'secret': 'password'}})
    assert json.loads(payload) == {'counts': {'print_stale': 5, 'inventory_balance': 0}, 'complete': {'inventory': True}}


def fake_response(value, status=200):
    return SimpleNamespace(status_code=status, content=json.dumps(value).encode(), json=lambda: value)


def test_provider_is_bounded_no_tools_no_retry_and_one_fallback(monkeypatch):
    calls = []
    def post(self, url, **kwargs):
        calls.append((url, kwargs))
        assert 'tools' not in kwargs['json']
        assert kwargs['json']['max_tokens'] == 600
        assert kwargs['json']['thinking'] == {'type': 'disabled'}
        assert kwargs['allow_redirects'] is False and kwargs['timeout'] == (3, 10)
        if 'deepseek' in url:
            raise requests.Timeout('fixture-only-secret')
        return fake_response({'content': [{'type': 'text', 'text': '{"summary":"Confira os trabalhos parados antes de outra cópia."}'}],
                              'usage': {'input_tokens': 35, 'output_tokens': 20}})
    monkeypatch.setattr(requests.Session, 'post', post)
    result = quality_summary.summarize({'print_stale': 2}, {}, deepseek_key='fixture-only', anthropic_key='fixture-only')
    assert result.status == 'fallback' and result.calls == 2 and result.output_tokens == 20
    assert 'fixture' not in result.text
    assert len(calls) == 2


def test_provider_failure_and_missing_keys_leave_deterministic_report(monkeypatch):
    calls = []
    def fail(self, url, **kwargs):
        calls.append(url)
        return fake_response({}, status=503)
    monkeypatch.setattr(requests.Session, 'post', fail)
    assert quality_summary.summarize({}, {}, deepseek_key='', anthropic_key='').status == 'not_configured'
    assert not calls
    result = quality_summary.summarize({}, {}, deepseek_key='fixture', anthropic_key='fixture')
    assert result.status == 'unavailable' and result.calls == 2 and not result.text


@pytest.mark.parametrize('output', ['{"summary":"https://evil.fixture"}', '{"summary":"email@fixture.local"}', '{"summary":"ok","tools":[]}', '[]'])
def test_model_output_is_text_only_and_strict(output):
    with pytest.raises(ValueError): quality_summary._text(output)


def test_complete_daily_run_has_one_lucas_notice_and_network_no_open_database(factory):
    observed = []
    def summarizer(counts, coverage):
        # The provider is mocked; a fresh session sees the committed budget.
        with factory() as db:
            row = db.query(QualityRun).one()
            assert row.ai_attempted and row.ai_status == 'reserved'
        observed.append(True)
        return quality_summary.QualitySummary('not_configured')
    assert system_quality.run_once(session_factory=factory, moment=MOMENT, summarizer=summarizer)
    assert observed == [True]
    assert not system_quality.run_once(session_factory=factory, moment=MOMENT, summarizer=summarizer)
    with factory() as db:
        assert db.query(Notification).count() == 1
        notice = db.query(Notification).one()
        assert notice.category == 'reminder' and notice.action_path.startswith('/auditoria?quality_run=')
        assert db.query(NotificationRecipient).one().user_id == db.query(Usuario).one().id
        assert db.query(AuditEvent).filter_by(action='quality_review_completed').count() == 1
        assert db.query(QualityRun).one().summary


def test_stopped_worker_performs_no_queries_or_provider_calls(factory):
    stop = Event(); stop.set()
    assert not system_quality.run_once(stop, session_factory=lambda: pytest.fail('No database after stop'))


def test_manual_request_retries_are_idempotent_and_cap_three_per_day(factory):
    ids = [uuid.uuid4() for _ in range(4)]
    with factory() as db:
        owner = db.query(Usuario).one()
        for index in range(3):
            row = system_quality.enqueue_manual_run(db, request_id=ids[index], requested_by=owner.id, moment=MOMENT)
            db.commit()
            assert system_quality.enqueue_manual_run(db, request_id=ids[index], requested_by=owner.id, moment=MOMENT).id == row.id
            with pytest.raises(HTTPException) as error:
                system_quality.enqueue_manual_run(db, request_id=ids[3], requested_by=owner.id, moment=MOMENT)
            assert error.value.status_code == 409
            row.status = 'completed'
            db.commit()
        with pytest.raises(HTTPException) as error:
            system_quality.enqueue_manual_run(db, request_id=ids[3], requested_by=owner.id, moment=MOMENT)
        assert error.value.status_code == 429
        assert system_quality.enqueue_manual_run(db, request_id=ids[0], requested_by=owner.id, moment=MOMENT)
        assert db.query(QualityRun).count() == 3


def test_manual_run_is_prioritized_but_global_ai_budget_and_crash_are_preserved(factory):
    report = {'counters': {}, 'findings': [], 'coverage': {'inventory': {'checked': 0, 'complete': True}}}
    with factory() as db:
        daily = system_quality.claim_run(db, MOMENT)
        db.commit()
        assert system_quality._save_report(db, daily, report, MOMENT)
        db.commit()  # Simulate a crash before the provider's response is recorded.
        recovered = system_quality.claim_run(db, MOMENT + timedelta(minutes=4))
        assert recovered.ai_attempted
        assert not system_quality._save_report(db, recovered, report, MOMENT + timedelta(minutes=4))
        assert db.get(QualityRun, recovered.id).ai_status == 'already_attempted'
        system_quality.complete_run(db, recovered, report, quality_summary.QualitySummary('already_attempted'))
        db.commit()
        owner = db.query(Usuario).one()
        manual = system_quality.enqueue_manual_run(db, request_id=uuid.uuid4(), requested_by=owner.id, moment=MOMENT)
        db.commit()
        claim = system_quality.claim_run(db, MOMENT)
        assert claim.id == manual.id
        assert not system_quality._save_report(db, claim, report, MOMENT)
        assert db.get(QualityRun, manual.id).ai_status == 'budget_exhausted'
        assert db.get(QualityConfig, 1).ai_reserved_on == MOMENT.astimezone(system_quality.BRT).date()


@pytest.mark.parametrize('kind', ['daily', 'manual'])
def test_exhausted_report_finishes_once_and_notifies_only_lucas(factory, kind):
    identity = uuid.uuid4()
    with factory() as db:
        db.get(QualityConfig, 1).local_time = '23:59'
        db.add(QualityRun(id=identity, run_day=MOMENT.date(), kind=kind, status='running', attempts=3,
                         lease_token='abandoned-local-claim', lease_until=MOMENT - timedelta(seconds=1),
                         created_at=MOMENT - timedelta(hours=1), started_at=MOMENT - timedelta(hours=1)))
        db.commit()
        assert system_quality.claim_run(db, MOMENT) is None
        db.commit()
        row = db.get(QualityRun, identity)
        assert row.status == 'failed' and system_quality.aware(row.finished_at) == MOMENT
        assert row.error_category == 'retry_budget_exhausted'
        assert row.lease_token is None and row.lease_until is None
        assert system_quality.claim_run(db, MOMENT + timedelta(minutes=1)) is None
        db.commit()
        notice = db.query(Notification).one()
        assert notice.severity == 'warning' and len(notice.body) < 2000
        assert notice.dedupe_key == 'quality-failed:' + str(identity)
        assert 'abandoned-local-claim' not in notice.body
        assert db.query(NotificationRecipient).one().user_id == db.query(Usuario.id).scalar()
        assert db.query(AuditEvent).filter_by(action='quality_review_failed').count() == 1


def test_final_active_lease_is_not_retired_early(factory):
    with factory() as db:
        db.get(QualityConfig, 1).local_time = '23:59'
        row = QualityRun(id=uuid.uuid4(), run_day=MOMENT.date(), kind='manual', status='running', attempts=3,
                         lease_token='last-active-claim', lease_until=MOMENT + timedelta(minutes=1), created_at=MOMENT)
        db.add(row); db.commit()
        assert system_quality.claim_run(db, MOMENT) is None
        assert row.status == 'running' and row.lease_token == 'last-active-claim'
        assert db.query(Notification).count() == 0


def test_failed_manual_frees_active_slot_but_keeps_three_per_day_quota(factory):
    with factory() as db:
        owner = db.query(Usuario).one()
        failed = QualityRun(id=uuid.uuid4(), request_id=uuid.uuid4(), requested_by=owner.id,
                           run_day=MOMENT.date(), kind='manual', status='running', attempts=3,
                           lease_token='spent-claim', lease_until=MOMENT - timedelta(seconds=1), created_at=MOMENT)
        db.add(failed); db.commit()
        for _ in range(2):
            row = system_quality.enqueue_manual_run(db, request_id=uuid.uuid4(), requested_by=owner.id, moment=MOMENT)
            assert failed.status == 'failed'
            row.status = 'completed'
            db.commit()
        with pytest.raises(HTTPException) as error:
            system_quality.enqueue_manual_run(db, request_id=uuid.uuid4(), requested_by=owner.id, moment=MOMENT)
        assert error.value.status_code == 429
        assert db.query(QualityRun).filter_by(kind='manual').count() == 3
        assert db.query(Notification).filter(Notification.dedupe_key.like('quality-failed:%')).count() == 1


def test_warning_severity_uses_counters_beyond_findings_preview_limit(factory):
    with factory() as db:
        claim = system_quality.claim_run(db, MOMENT)
        report = {'counters': {'inventory_missing_metadata': 500, 'sale_avulso_without_reason': 1},
                  'findings': [{'key': 'inventory_missing_metadata', 'severity': 'info', 'entity_type': 'inventory'}] * 100,
                  'coverage': {'inventory': {'checked': 500, 'complete': False}, 'sales': {'checked': 1, 'complete': True}}}
        assert system_quality.complete_run(db, claim, report, quality_summary.QualitySummary('disabled'), MOMENT)
        db.commit()
        assert db.query(Notification).one().severity == 'warning'


def test_ai_reservation_uses_real_time_after_checks_cross_midnight(factory, monkeypatch):
    newer = MOMENT + timedelta(days=1)
    monkeypatch.setattr(system_quality, 'now', lambda: newer)
    def summary(counts, coverage):
        with factory() as db:
            assert db.get(QualityConfig, 1).ai_reserved_on == newer.astimezone(system_quality.BRT).date()
        return quality_summary.QualitySummary('not_configured')
    assert system_quality.run_once(session_factory=factory, moment=MOMENT, summarizer=summary)
