from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from ...database import get_db
from ...dependencies import require_role
from ...models.assistant import utcnow
from ...models.sales_bi import SalesBIConfig, SalesBIWorkbook
from ...services.sales_bi import build_overview, sources_status
from ...services.sales_bi_onedrive import validate_url, validate_root, SourceError
from ...services.sales_bi_schedule import next_daily_sync

router = APIRouter()
manager = require_role(['ADMIN', 'GERENTE'])
admin = require_role(['ADMIN'])


class SourceConfig(BaseModel):
    current_url: str = Field(max_length=2500)
    archive_url: str = Field(max_length=2500)
    archive_root: str = Field(max_length=1000)
    current_year: int | None = Field(None, ge=2000, le=2100)
    current_month: int | None = Field(None, ge=1, le=12)
    enabled: bool = True

    @model_validator(mode='after')
    def validate_sources(self):
        try:
            validate_url(self.current_url, share=True)
            validate_url(self.archive_url, share=True)
            self.archive_root = validate_root(self.archive_root)
        except (SourceError, ValueError):
            raise ValueError('Informe links HTTPS do OneDrive e o caminho válido da pasta compartilhada.') from None
        if bool(self.current_year) != bool(self.current_month):
            raise ValueError('Informe ano e mês juntos ou deixe ambos automáticos.')
        return self


@router.get('/overview')
def overview(year: int | None = Query(None, ge=2000, le=2100), month: int | None = Query(None, ge=1, le=12),
             seller: str | None = Query(None, max_length=100), user=Depends(manager), db: Session = Depends(get_db)):
    return build_overview(db.query(SalesBIWorkbook).filter_by(active=True).all(), year, month, seller)


@router.get('/sources')
def sources(user=Depends(manager), db: Session = Depends(get_db)):
    return sources_status(db)


@router.get('/config')
def config(user=Depends(admin), db: Session = Depends(get_db)):
    c = db.get(SalesBIConfig, 1)
    return {name: getattr(c, name) for name in SourceConfig.model_fields} if c else None


@router.put('/config')
def save_config(body: SourceConfig, user=Depends(admin), db: Session = Depends(get_db)):
    c = db.query(SalesBIConfig).filter_by(id=1).with_for_update().first()
    if c and c.lease_until and c.lease_until.replace(tzinfo=None) > utcnow().replace(tzinfo=None):
        raise HTTPException(409, 'Aguarde a leitura em andamento para alterar as fontes.')
    if not c:
        c = SalesBIConfig(id=1)
        db.add(c)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    c.next_sync_at = next_daily_sync(utcnow())
    db.commit()
    return {'saved': True}


@router.post('/sync', status_code=202)
def refresh(user=Depends(manager), db: Session = Depends(get_db)):
    c = db.query(SalesBIConfig).filter_by(id=1).with_for_update().first()
    if not c or not c.enabled:
        raise HTTPException(400, 'Configure e ative as fontes antes de atualizar.')
    if not c.lease_until or c.lease_until.replace(tzinfo=None) <= utcnow().replace(tzinfo=None):
        c.requested_at = utcnow()
        c.next_sync_at = utcnow()
        db.commit()
    return {'queued': True}
