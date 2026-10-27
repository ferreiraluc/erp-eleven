"""Leased daily diagnostics; only quality history, audit and inbox are written."""
from dataclasses import dataclass
from datetime import timedelta
import uuid
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, text

from ..database import SessionLocal
from ..models.access import now
from ..models.system_quality import QualityConfig, QualityRun
from ..models.usuario import Usuario, UsuarioRole
from . import quality_checks, quality_summary
from .notifications import emit_notification
from .access_policy import is_owner
from .user_audit import record
from .user_sessions import aware

BRT = ZoneInfo('America/Sao_Paulo')
LEASE = timedelta(minutes=3)
MAX_RUN_ATTEMPTS = 3
MANUAL_SCANS_PER_DAY = 3
WARNING_KEYS = {'inventory_balance', 'inventory_limits', 'sale_avulso_without_reason',
                'print_uncertain', 'print_failed', 'print_stale', 'printer_offline',
                'bi_sync_problem', 'worker_problem'}
LABELS = {
    'inventory_missing_metadata': 'Produtos com informações a conferir',
    'inventory_balance': 'Saldos com totais diferentes por local',
    'inventory_limits': 'Limites de estoque a conferir',
    'sale_avulso_without_reason': 'Vendas com avulsos sem motivo informado',
    'print_uncertain': 'Impressões com envio incerto', 'print_failed': 'Impressões com falha',
    'print_stale': 'Trabalhos de impressão aguardando conferência',
    'printer_offline': 'Impressoras sem contato recente', 'bi_sync_problem': 'Sincronização BI a conferir',
    'worker_problem': 'Processos sem progresso recente',
    'customer_duplicate_candidate': 'Possíveis clientes duplicados para revisão',
    'address_duplicate_candidate': 'Possíveis endereços duplicados para revisão',
    'address_link_review': 'Vínculos de endereços aguardando revisão',
}


@dataclass(frozen=True)
class QualityClaim:
    id: uuid.UUID
    token: str
    ai_enabled: bool
    ai_attempted: bool


def ensure_config(db, moment=None):
    moment = moment or now()
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': 865422627183})
    row = db.get(QualityConfig, 1)
    if row is None:
        local = moment.astimezone(BRT)
        # Installing at night schedules tomorrow. No report or old broadcast is
        # run as a side effect of deploying the code or opening the dashboard.
        first_day = local.date() + (timedelta(days=1) if local.strftime('%H:%M') >= '08:30' else timedelta())
        row = QualityConfig(id=1, enabled=True, ai_enabled=True, local_time='08:30', first_run_on=first_day)
        db.add(row)
        db.flush()
    return row


def claim_run(db, moment=None):
    moment = moment or now()
    config = ensure_config(db, moment)
    local = moment.astimezone(BRT)
    _retire_stale_runs(db, moment)
    if not config.enabled:
        return None
    manual = db.query(QualityRun).filter(QualityRun.kind == 'manual', QualityRun.created_at >= moment - timedelta(days=1),
        QualityRun.attempts < MAX_RUN_ATTEMPTS, or_(QualityRun.status == 'queued', and_(QualityRun.status == 'running',
        QualityRun.lease_until <= moment))).order_by(QualityRun.created_at, QualityRun.id).with_for_update(skip_locked=True).first()
    if manual:
        return _claim_row(db, manual, config, moment)
    if local.date() < config.first_run_on or local.strftime('%H:%M') < config.local_time:
        return None
    row = db.query(QualityRun).filter_by(run_day=local.date(), kind='daily').with_for_update().one_or_none()
    if row:
        if row.status in ('completed', 'partial') or row.attempts >= MAX_RUN_ATTEMPTS:
            return None
        if row.lease_until and aware(row.lease_until) > moment:
            return None
    else:
        row = QualityRun(id=uuid.uuid5(uuid.NAMESPACE_URL, 'erp-eleven/quality/daily/' + local.date().isoformat()),
                         run_day=local.date(), kind='daily', attempts=1, started_at=moment)
        db.add(row)
    return _claim_row(db, row, config, moment)


def _owner_ids(db):
    return [uid for (uid,) in db.query(Usuario.id).filter(Usuario.ativo.is_(True), Usuario.role == UsuarioRole.ADMIN,
                                                        func.lower(Usuario.email) == 'lucas@eleven.com').all()]


def _terminal_failure(db, row, moment, category):
    if row.status not in ('queued', 'running'):
        return
    row.status, row.finished_at, row.error_category = 'failed', moment, category
    row.lease_token, row.lease_until = None, None
    owners = _owner_ids(db)
    if owners:
        body = ('A conferência atingiu o limite de tentativas e foi encerrada.' if category == 'retry_budget_exhausted'
                else 'O prazo para concluir esta conferência expirou e ela foi encerrada.')
        emit_notification(db, title='A conferência do sistema não foi concluída',
            body=body + ' Abra o relatório para conferir. Nenhuma venda, saldo, cadastro ou impressão foi alterado.',
            user_ids=owners, category='reminder', severity='warning', action_path='/auditoria?quality_run=' + str(row.id),
            dedupe_key='quality-failed:' + str(row.id), entity_type='quality_run', entity_id=str(row.id))
    record(db, 'quality_review_failed', 'auditoria', entity='quality_runs', entity_id=str(row.id),
        actor_name='Sistema', source='system', changes={'status': 'failed', 'attempts': row.attempts, 'error_category': category})


def _retire_stale_runs(db, moment):
    """Terminate our abandoned reports, never a live lease or business record."""
    local_day = moment.astimezone(BRT).date()
    expired_lease = or_(QualityRun.lease_until.is_(None), QualityRun.lease_until <= moment)
    exhausted = and_(QualityRun.attempts >= MAX_RUN_ATTEMPTS, expired_lease)
    old_manual = and_(QualityRun.kind == 'manual', QualityRun.created_at < moment - timedelta(days=1), expired_lease)
    previous_daily = and_(QualityRun.kind == 'daily', QualityRun.run_day < local_day, expired_lease)
    rows = db.query(QualityRun).filter(QualityRun.status.in_(('queued', 'running')),
        or_(exhausted, old_manual, previous_daily)).order_by(QualityRun.created_at, QualityRun.id)\
        .populate_existing().with_for_update(skip_locked=True).limit(25).all()
    for row in rows:
        _terminal_failure(db, row, moment, 'retry_budget_exhausted' if row.attempts >= MAX_RUN_ATTEMPTS else 'request_expired')
    if rows:
        db.flush()


def _claim_row(db, row, config, moment):
    if row.status == 'queued':
        row.started_at = moment
    if row.status in ('running', 'failed') and row.lease_token:
        row.attempts += 1
    token = str(uuid.uuid4())
    row.status, row.lease_token, row.lease_until = 'running', token, moment + LEASE
    db.flush()
    return QualityClaim(row.id, token, config.ai_enabled, row.ai_attempted)


def limits():
    return {'scans_per_day': 1, 'manual_scans_per_day': MANUAL_SCANS_PER_DAY, **quality_checks.LIMITS,
            'max_findings': quality_checks.MAX_FINDINGS, 'max_provider_calls_per_day': 2,
            'max_output_tokens_per_call': quality_summary.MAX_OUTPUT_TOKENS,
            'max_input_bytes': quality_summary.MAX_INPUT_BYTES}


def enqueue_manual_run(db, *, request_id, requested_by, moment=None):
    moment = moment or now()
    owner = db.get(Usuario, requested_by)
    if not owner or not owner.ativo or not is_owner(owner):
        raise HTTPException(403, 'Acesso exclusivo do administrador Lucas.')
    config = ensure_config(db, moment)
    _retire_stale_runs(db, moment)
    existing = db.query(QualityRun).filter_by(request_id=request_id).first()
    if existing:
        if existing.requested_by != requested_by:
            raise HTTPException(409, 'A solicitação já pertence a outra conta.')
        return existing
    if not config.enabled:
        raise HTTPException(409, 'A conferência do sistema está pausada nas configurações.')
    if db.query(QualityRun.id).filter(QualityRun.kind == 'manual', QualityRun.created_at >= moment - timedelta(days=1),
                                    QualityRun.status.in_(('queued', 'running'))).first():
        raise HTTPException(409, 'Já existe uma conferência manual aguardando ou em andamento.')
    day = moment.astimezone(BRT).date()
    count = db.query(QualityRun).filter_by(kind='manual', run_day=day, requested_by=requested_by).count()
    if count >= MANUAL_SCANS_PER_DAY:
        raise HTTPException(429, 'Limite de três conferências manuais por dia atingido.')
    row = QualityRun(id=uuid.uuid4(), request_id=request_id, requested_by=requested_by, run_day=day,
                     kind='manual', status='queued', attempts=1, started_at=moment, created_at=moment)
    db.add(row)
    db.flush()
    return row


def _owned(db, claim):
    return db.query(QualityRun).filter_by(id=claim.id, status='running', lease_token=claim.token).with_for_update().one_or_none()


def _save_report(db, claim, report, moment):
    row = _owned(db, claim)
    if not row:
        return False
    row.counters, row.coverage, row.findings = report['counters'], report['coverage'], report['findings']
    row.lease_until = moment + LEASE
    # Reserve the entire two-call budget durably BEFORE contacting providers. A
    # timeout/crash can never cause another paid attempt for this report.
    config = db.query(QualityConfig).filter_by(id=1).populate_existing().with_for_update().one()
    day = moment.astimezone(BRT).date()
    day_available = config.ai_reserved_on is None or day > config.ai_reserved_on
    allowed = claim.ai_enabled and config.ai_enabled and not row.ai_attempted and day_available
    if allowed:
        row.ai_attempted, row.ai_status = True, 'reserved'
        config.ai_reserved_on = day
    else:
        row.ai_status = ('already_attempted' if row.ai_attempted else 'disabled' if not config.ai_enabled
                         else 'budget_exhausted' if not day_available else 'disabled')
    return allowed


def deterministic_summary(counters, coverage):
    lines = ['Conferência do ERP Eleven.']
    if counters:
        lines.extend(f'{LABELS[key]}: {count}.' for key, count in counters.items() if key in LABELS and count > 0)
    else:
        lines.append('Nenhuma nova pendência encontrada nos dados analisados.')
    incomplete = sum(not value.get('complete', False) for value in coverage.values())
    if incomplete:
        lines.append(f'{incomplete} verificação(ões) incompleta(s); confira a cobertura no relatório.')
    lines.append('Cobertura limitada a dados recentes e filas ativas. Nenhuma venda, saldo, cadastro ou impressão foi alterado.')
    return '\n'.join(lines)[:1500]


def complete_run(db, claim, report, assistant, moment=None):
    moment = moment or now()
    row = _owned(db, claim)
    if not row:
        return False
    row.counters, row.coverage, row.findings = report['counters'], report['coverage'], report['findings']
    row.summary = deterministic_summary(row.counters, row.coverage)
    row.ai_summary, row.ai_status = assistant.text, assistant.status
    row.provider, row.provider_calls = assistant.provider, assistant.calls
    row.input_tokens, row.output_tokens = assistant.input_tokens, assistant.output_tokens
    row.finished_at, row.lease_token, row.lease_until = moment, None, None
    row.status = 'completed' if all(value.get('complete') for value in row.coverage.values()) else 'partial'
    owners = _owner_ids(db)
    if owners:
        body = row.summary
        if row.ai_summary:
            body += '\n\nLeitura assistida por IA (sugestão):\n' + row.ai_summary
        # Findings are a bounded preview. An earlier group of informational
        # findings cannot hide a later warning counted in the inspected data.
        warning = any(row.counters.get(key, 0) > 0 for key in WARNING_KEYS) or any(
            value.get('error') for value in row.coverage.values())
        title = 'Conferência diária do sistema' if row.kind == 'daily' else 'Conferência manual do sistema'
        emit_notification(db, title=title + ' · ' + row.run_day.strftime('%d/%m'),
            body=body[:2000], category='reminder', severity='warning' if warning else 'info', user_ids=owners,
            action_path='/auditoria?quality_run=' + str(row.id), dedupe_key='quality-daily:' + str(row.id),
            entity_type='quality_run', entity_id=str(row.id))
    record(db, 'quality_review_completed', 'auditoria', entity='quality_runs', entity_id=str(row.id),
        actor_name='Sistema', source='system', changes={'status': row.status, 'counts': row.counters,
        'checked': {key: value.get('checked', 0) for key, value in row.coverage.items()}, 'ai_status': row.ai_status})
    db.flush()
    return True


def run_once(stop=None, *, session_factory=SessionLocal, health_provider=None, moment=None, summarizer=quality_summary.summarize):
    moment = moment or now()
    if stop and stop.is_set():
        return False
    with session_factory() as db:
        claim = claim_run(db, moment)
        db.commit()
    if claim is None:
        return False
    health = health_provider() if health_provider else {}
    report = quality_checks.collect(session_factory, moment, health)
    with session_factory() as db:
        # The query window belongs to the claim, but a paid-call reservation
        # belongs to the actual current BRT day, including checks across midnight.
        call_ai = _save_report(db, claim, report, now())
        skipped = db.get(QualityRun, claim.id).ai_status
        db.commit()
    if stop and stop.is_set():
        call_ai = False
    # No database session or transaction remains open across a paid/network call.
    assistant = summarizer(report['counters'], report['coverage']) if call_ai else quality_summary.QualitySummary(skipped)
    with session_factory() as db:
        result = complete_run(db, claim, report, assistant)
        db.commit()
    return result
