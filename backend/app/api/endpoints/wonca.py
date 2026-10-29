"""Owner-managed monitoring and a signed, bounded durable webhook inbox."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_owner
from ...models.wonca import WoncaConfig, WoncaSubscription, WoncaEvent
from ...models.rastreamento import Rastreamento, RastreamentoStatus
from ...models.access import now
from ...config import settings
from ...services import wonca_monitoring as monitoring
from ...services.user_audit import record, bind_actor

router = APIRouter()


class MonitoringInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    endpoint_id: UUID
    profile_id: UUID
    interval_hours: Literal[1, 2, 4, 6, 12] = 2
    monitor_days: Literal[30] = 30
    daytime_only: bool = True
    signing_secret: SecretStr | None = None
    enabled: bool = False
    confirm_monitoring: bool = False


def state(db):
    config = db.get(WoncaConfig, 'main')
    counts = dict(db.query(WoncaSubscription.state, func.count()).group_by(WoncaSubscription.state).all())
    return {
        'configured': bool(config and monitoring.secret(config)),
        'enabled': bool(config and config.enabled),
        'api_key_configured': bool(settings.WONCA_API_KEY),
        'endpoint_id': config.endpoint_id if config else '',
        'profile_id': config.profile_id if config else '',
        'interval_hours': config.interval_hours if config else 2,
        'daytime_only': config.daytime_only if config else True,
        'monitor_days': 30, 'subscriptions': counts,
        'pending_events': db.query(WoncaEvent).filter_by(status='pending').count(),
        'failed_events': db.query(WoncaEvent).filter_by(status='failed').count(),
        'failed_subscriptions': db.query(WoncaSubscription).filter(WoncaSubscription.last_error.is_not(None)).count(),
        'open_shipments': db.query(Rastreamento).filter(Rastreamento.ativo.is_(True), Rastreamento.status != RastreamentoStatus.ENTREGUE).count(),
    }


@router.get('/config')
def get_config(db: Session = Depends(get_db), user=Depends(require_owner)):
    return state(db)


@router.put('/config')
def put_config(body: MonitoringInput, db: Session = Depends(get_db), user=Depends(require_owner)):
    if not monitoring.lock(db, 711014):
        raise HTTPException(409, 'O monitoramento está sincronizando. Tente novamente em alguns segundos.')
    current = db.query(WoncaConfig).filter_by(id='main').populate_existing().with_for_update().first()
    incoming_secret = body.signing_secret.get_secret_value().strip() if body.signing_secret else ''
    if incoming_secret and not 16 <= len(incoming_secret) <= 500:
        raise HTTPException(422, 'Confira o signing secret fornecido pela Wonca.')
    changed = current and (current.endpoint_id != str(body.endpoint_id) or current.profile_id != str(body.profile_id))
    if changed and db.query(WoncaSubscription).filter(WoncaSubscription.state.in_(('active', 'pending', 'removing', 'paused'))).first():
        raise HTTPException(409, 'Pause e aguarde o encerramento das inscrições antes de trocar endpoint ou perfil.')
    if not incoming_secret and (not current or changed or not monitoring.secret(current)):
        raise HTTPException(422, 'Informe o signing secret deste endpoint.')
    if body.enabled and (not settings.WONCA_API_KEY or not body.confirm_monitoring):
        raise HTTPException(422, 'Confira a chave de API e confirme o consumo do monitoramento antes de ativar.')
    if changed:
        for subscription in db.query(WoncaSubscription).all():
            subscription.endpoint_id = str(body.endpoint_id)
            subscription.profile_id = str(body.profile_id)
            subscription.remote_id = None
            subscription.retry_at = now()
    if not current:
        current = WoncaConfig(id='main')
        db.add(current)
    current.endpoint_id, current.profile_id = str(body.endpoint_id), str(body.profile_id)
    current.interval_hours, current.monitor_days = body.interval_hours, body.monitor_days
    current.daytime_only = body.daytime_only
    if incoming_secret:
        current.secret_encrypted = monitoring.cipher().encrypt(incoming_secret.encode()).decode()
    current.enabled, current.updated_at = body.enabled, now()
    bind_actor(db, user)
    record(db, 'wonca_monitoring_configured', 'rastreamento', entity='wonca_config', entity_id='main',
           changes={'enabled': body.enabled, 'interval_hours': body.interval_hours, 'monitor_days': 30,
                    'daytime_only': body.daytime_only})
    db.commit()
    return state(db)


@router.post('/webhook', status_code=202)
async def webhook(request: Request, db: Session = Depends(get_db)):
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
        raise HTTPException(415, 'Envie JSON.')
    body, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 262144:
            raise HTTPException(413, 'Evento excede o limite de tamanho.')
        body.append(chunk)
    result = monitoring.receive(db, b''.join(body), request.headers)
    db.commit()
    return result
