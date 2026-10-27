"""Lucas-only bounded diagnostics history and queue controls, with no provider calls."""
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, defer

from ...database import get_db
from ...dependencies import require_owner
from ...models.access import now
from ...models.system_quality import QualityConfig, QualityRun
from ...schemas.system_quality import QualityConfigUpdate, QualityScanRequest
from ...services import quality_checks, quality_summary, system_quality as service
from ...services.user_audit import record

router = APIRouter()
CHECKERS = set(quality_checks.CHECKERS)
FINDING_KEYS = set(quality_summary.CHECK_KEYS)
ENTITY_TYPES = {'inventory', 'pdv_sale', 'print_job', 'print_device', 'sales_bi', 'customer', 'address',
                'assistant', 'freight_labels', 'sales_bi', 'notifications', 'tracking'}


def _config(row):
    return {'enabled': row.enabled, 'ai_enabled': row.ai_enabled, 'local_time': row.local_time,
            'timezone': 'America/Sao_Paulo', 'first_run_on': row.first_run_on,
            'version': row.version, 'updated_at': row.updated_at, 'ai_reserved_on': row.ai_reserved_on}


def _counters(raw):
    return {key: min(10**9, value) for key, value in (raw or {}).items()
            if key in FINDING_KEYS and type(value) is int and value >= 0} if isinstance(raw, dict) else {}


def _coverage(raw):
    output = {}
    for key, entry in (raw or {}).items() if isinstance(raw, dict) else []:
        if key not in CHECKERS or not isinstance(entry, dict):
            continue
        checked = entry.get('checked', 0)
        safe = {'checked': min(10**9, max(0, checked)) if type(checked) is int else 0,
                'complete': entry.get('complete') is True}
        if entry.get('window') in {'last_24_hours', 'active_jobs_last_7_days', 'active_devices', 'current_state', 'current_process'}:
            safe['window'] = entry['window']
        if entry.get('error') in {'run_query_budget', 'check_unavailable'}:
            safe['error'] = entry['error']
        if entry.get('comparison') == 'changed_cohort_only':
            safe['comparison'] = entry['comparison']
        output[key] = safe
    return output


def _run(row):
    return {**{key: getattr(row, key) for key in ('id', 'run_day', 'kind', 'status', 'created_at',
            'started_at', 'finished_at', 'attempts', 'ai_attempted', 'ai_status', 'provider_calls',
            'input_tokens', 'output_tokens', 'request_id', 'requested_by')},
        'summary': (row.summary or '')[:1500] or None, 'ai_summary': (row.ai_summary or '')[:600] or None,
        'provider': row.provider if row.provider in {'deepseek', 'anthropic'} else None,
        'error_category': 'run_unavailable' if row.error_category else None,
        'counters': _counters(row.counters), 'coverage': _coverage(row.coverage)}


def _reference(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _findings(row, offset=0, limit=30):
    # Reconstruct the allowlisted view rather than returning arbitrary stored JSON.
    # A report contains at most MAX_FINDINGS; even malformed historic data cannot
    # grow the administrative response or leak names, documents or image fields.
    source = row.findings if isinstance(row.findings, list) else []
    safe = []
    for entry in source[:quality_checks.MAX_FINDINGS]:
        if not isinstance(entry, dict) or entry.get('key') not in FINDING_KEYS or entry.get('entity_type') not in ENTITY_TYPES:
            continue
        item = {'key': entry['key'], 'entity_type': entry['entity_type'],
                'severity': 'warning' if entry.get('severity') == 'warning' else 'info'}
        for key in ('entity_id', 'related_id'):
            identity = _reference(entry.get(key))
            if identity:
                item[key] = identity
        safe.append(item)
    return safe[offset:offset + limit], len(safe)


def _detail(row, offset=0, limit=30):
    findings, total = _findings(row, offset, limit)
    return {**_run(row), 'findings': findings, 'findings_total': total,
            'findings_offset': offset, 'findings_limit': limit}


@router.get('/admin')
def admin(offset: int = Query(0, ge=0, le=1000000), limit: int = Query(20, ge=1, le=30),
          owner=Depends(require_owner), db: Session = Depends(get_db)):
    config = service.ensure_config(db)
    db.commit()
    # History cards omit the findings JSON; load references only for the newest
    # report or an explicitly selected report, never every historic report.
    query = db.query(QualityRun)
    total = query.count()
    rows = query.options(defer(QualityRun.findings)).order_by(QualityRun.created_at.desc(), QualityRun.id.desc()).offset(offset).limit(limit).all()
    latest = query.order_by(QualityRun.created_at.desc(), QualityRun.id.desc()).first()
    return {'config': _config(config), 'latest': _detail(latest) if latest else None,
            'runs': [_run(row) for row in rows], 'total': total, 'offset': offset, 'limit': limit,
            'limits': service.limits()}


@router.get('/admin/runs/{run_id}')
def run_detail(run_id: uuid.UUID, findings_offset: int = Query(0, ge=0, le=100),
               findings_limit: int = Query(30, ge=1, le=100), owner=Depends(require_owner), db: Session = Depends(get_db)):
    row = db.get(QualityRun, run_id)
    if not row:
        raise HTTPException(404, 'Conferência não encontrada.')
    return _detail(row, findings_offset, findings_limit)


@router.put('/config')
def update_config(body: QualityConfigUpdate, owner=Depends(require_owner), db: Session = Depends(get_db)):
    service.ensure_config(db)
    config = db.query(QualityConfig).filter_by(id=1).populate_existing().with_for_update().one()
    if config.version != body.expected_version:
        raise HTTPException(409, 'Esta configuração mudou. Recarregue antes de salvar.')
    moment = now()
    if body.enabled and (not config.enabled or config.local_time != body.local_time):
        local = moment.astimezone(service.BRT)
        # Enabling/changing a schedule chooses its next future occurrence, not
        # an immediate diagnostic/paid call as a side effect of saving settings.
        config.first_run_on = local.date() + (timedelta(days=1) if local.strftime('%H:%M') >= body.local_time else timedelta())
    config.enabled, config.ai_enabled, config.local_time = body.enabled, body.ai_enabled, body.local_time
    config.version += 1
    config.updated_at, config.updated_by = moment, owner.id
    record(db, 'quality_config_updated', 'auditoria', entity='quality_config', entity_id='1',
           changes={'enabled': body.enabled, 'ai_enabled': body.ai_enabled, 'local_time': body.local_time})
    db.commit()
    return _config(config)


@router.post('/scan', status_code=202)
def request_scan(body: QualityScanRequest, owner=Depends(require_owner), db: Session = Depends(get_db)):
    run = service.enqueue_manual_run(db, request_id=body.request_id, requested_by=owner.id)
    record(db, 'quality_review_requested', 'auditoria', entity='quality_runs', entity_id=str(run.id),
           changes={'kind': 'manual'})
    db.commit()
    return _run(run)
