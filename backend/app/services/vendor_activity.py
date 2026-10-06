"""Persistent seller identity, projected BI reads and linked calendar records."""
from sqlalchemy import extract
from ..models.vendedor import Vendedor
from ..models.usuario import Usuario
from ..models.folga import Folga
from ..models.sales_bi import SalesBIWorkbook
from .access_policy import own_sales
from .sales_bi import build_overview, private_workbooks
from .sales_bi_parser import seller_name
from .user_audit import record


def reconcile_vendors(db):
    result = {'vendors_linked': 0, 'vendor_reviews': []}
    rows = db.query(Vendedor).order_by(Vendedor.id).with_for_update().all()
    used = {row.sales_seller for row in rows if row.sales_seller}
    known = {name for row in db.query(SalesBIWorkbook).filter_by(active=True) if row.snapshot
             for name in row.snapshot.get('sellers', {})}
    for row in rows:
        if row.sales_seller: continue
        users = db.query(Usuario).filter_by(vendedor_id=row.id).all()
        explicit = {seller_name(user.sales_seller) for user in users if user.sales_seller}
        if len(explicit) > 1:
            result['vendor_reviews'].append(str(row.id)); continue
        name = next(iter(explicit), seller_name(row.nome))
        if not explicit and sum(seller_name(other.nome) == name for other in rows) > 1:
            result['vendor_reviews'].append(str(row.id)); continue
        if not name or name not in known or name in used:
            result['vendor_reviews'].append(str(row.id)); continue
        row.sales_seller = name; used.add(name); result['vendors_linked'] += 1
        if db.info.get('audit_actor'):
            record(db, 'vendor_bi_linked', 'vendedores', entity='vendedores', entity_id=str(row.id),
                   changes={'sales_seller': name})
    db.flush()
    return result


def activity(db, vendor, user, year, month=None):
    # Calendar is operational. Financial data is authorized before projection.
    allowed = not own_sales(user) or bool(user.vendedor_id == vendor.id and user.sales_seller and
                                          user.sales_seller == vendor.sales_seller)
    rows = []
    if allowed and vendor.sales_seller:
        rows = db.query(SalesBIWorkbook).filter_by(active=True).all()
    sales = build_overview(private_workbooks(rows, vendor.sales_seller), year, month,
                           vendor.sales_seller) if allowed and vendor.sales_seller else None
    folgas = db.query(Folga).filter(Folga.vendedor_id == vendor.id, Folga.ativo.is_(True),
                                  extract('year', Folga.data) == year)
    if month: folgas = folgas.filter(extract('month', Folga.data) == month)
    return {'vendor_id': str(vendor.id), 'seller': vendor.sales_seller,
            'sales_access': allowed, 'sales': sales,
            'last_synced_at': max((row.synced_at for row in rows if row.synced_at), default=None),
            'days_off': [{'id': str(row.id), 'date': row.data, 'type': row.tipo.value,
                          'period': row.periodo, 'approved': row.aprovado, 'reason': row.motivo}
                         for row in folgas.order_by(Folga.data.desc(), Folga.id)]}
