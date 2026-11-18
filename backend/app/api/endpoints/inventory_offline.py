from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_active_user
from ...models.usuario import Usuario
from ...services.inventory_offline import catalog_page

router = APIRouter()


@router.get('/offline-catalog')
def offline_catalog(response: Response, after_id: UUID | None = None,
                    limit: int = Query(500, ge=1, le=500),
                    db: Session = Depends(get_db),
                    current_user: Usuario = Depends(get_current_active_user)):
    # Persistence is explicit, isolated and limited in the app; proxies/browser
    # HTTP caches must never retain authenticated stock responses themselves.
    response.headers['Cache-Control'] = 'no-store'
    return catalog_page(db, current_user, after_id, limit)
