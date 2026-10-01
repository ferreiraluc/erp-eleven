"""Individual Excel rows share BI permissions; URL filters never grant access."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import require_role
from ...models.sales_bi import SalesBIWorkbook
from ...services.access_policy import own_sales
from ...services.sales_bi_entries import build_entries

router = APIRouter()


@router.get('/entries')
def entries(year: int | None = Query(None, ge=2000, le=2100), month: int | None = Query(None, ge=1, le=12),
            seller: str | None = Query(None, max_length=100), currency: str | None = Query(None, pattern='^(USD|BRL|PYG|EUR)$'),
            day: date | None = None, search: str | None = Query(None, max_length=120),
            offset: int = Query(0, ge=0, le=500000), limit: int = Query(50, ge=1, le=100),
            user=Depends(require_role(['ADMIN', 'GERENTE'])), db: Session = Depends(get_db)):
    private = own_sales(user)
    if private:
        if not getattr(user, 'sales_seller', None):
            raise HTTPException(403, 'Seu vendedor ainda não foi vinculado às planilhas.')
        seller = user.sales_seller
    rows = db.query(SalesBIWorkbook).filter_by(active=True)
    if year:
        rows = rows.filter(SalesBIWorkbook.year == year)
    if month:
        rows = rows.filter(SalesBIWorkbook.month == month)
    result = build_entries(rows.all(), year=year, month=month, seller=seller, currency=currency,
                           day=day.isoformat() if day else None, search=search, offset=offset, limit=limit, private=private)
    result['access'] = {'scope': 'own' if private else 'all', 'seller': seller if private else None}
    return result
