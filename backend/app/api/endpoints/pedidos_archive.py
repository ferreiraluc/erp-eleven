from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_active_user
from ...models.usuario import Usuario
from ...schemas.pedido_archive import ArchiveOrders
from ...services import order_archive

router = APIRouter()


@router.get('/arquivo/preview')
def preview_order_archive(db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    return order_archive.preview(db, user)


@router.post('/arquivo/confirm')
def archive_orders(body: ArchiveOrders, db: Session = Depends(get_db), user: Usuario = Depends(get_current_active_user)):
    try:
        result = order_archive.confirm(db, user, body)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
