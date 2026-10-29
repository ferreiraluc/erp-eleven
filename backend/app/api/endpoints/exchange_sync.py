"""Lucas controls automated Jebai/Venta quotes; no fetch on dashboard reads."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_owner
from ...models.exchange_sync import ExchangeSync
from ...services import bonanza_rates
from ...services.user_audit import bind_actor,record

router=APIRouter()


class Configuration(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool


def state(db):
    config=db.get(ExchangeSync,'bonanza')
    return {'enabled':bool(config and config.enabled),'branch':'Jebai','column':'Venta','interval_hours':6,
        'last_attempt':config.last_attempt if config else None,'last_success':config.last_success if config else None,
        'source_at':config.source_at if config else None,'last_error':config.last_error if config else None,
        'source_url':'https://www.bonanzacambios.com.py/?suc=2'}


@router.get('')
def get_config(db:Session=Depends(get_db),user=Depends(require_owner)):
    return state(db)


@router.put('')
def configure(body:Configuration,db:Session=Depends(get_db),user=Depends(require_owner)):
    bonanza_rates.lock_rates(db)
    config=db.get(ExchangeSync,'bonanza',populate_existing=True)
    if not config:
        config=ExchangeSync(id='bonanza');db.add(config)
    was_enabled=config.enabled
    config.enabled=body.enabled
    db.flush()
    if body.enabled and not was_enabled: bonanza_rates.sync(db,force=True)
    bind_actor(db,user)
    record(db,'exchange_sync_configured','exchange-rates',entity='exchange_sync',entity_id='bonanza',changes={'enabled':body.enabled,'branch':'Jebai','column':'Venta','interval_hours':6})
    db.commit()
    return state(db)
