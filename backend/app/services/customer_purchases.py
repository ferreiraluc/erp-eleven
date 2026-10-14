"""Read-only PDV history through explicit directory links; never merges accounts."""
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from ..config import settings
from ..models.pdv import PdvCliente, PdvSale
from .access_policy import own_sales, sales_query


def customer_purchases(db, customer_id, user, *, page=1, page_size=20):
    query = sales_query(db.query(PdvSale), PdvSale, user, pdv=True).join(
        PdvCliente, PdvCliente.id == PdvSale.cliente_id,
    ).filter(
        PdvCliente.cadastro_cliente_id == customer_id,
        PdvSale.deleted_at.is_(None),
    )
    # The same scoped query supplies counts, summaries and pages. Inactive PDV
    # accounts retain their history; names and documents never create links.
    total = query.count()
    grouped = query.with_entities(
        PdvSale.status, func.count(PdvSale.id),
        func.sum(PdvSale.total_gs), func.sum(PdvSale.refunded_gs),
    ).group_by(PdvSale.status).all()
    zero = Decimal('0.00')
    net = sum(((gross or zero) - (refunds or zero)
               for status, _, gross, refunds in grouped if status != 'cancelled'), zero)
    rows = query.options(
        joinedload(PdvSale.cliente), joinedload(PdvSale.vendedor), selectinload(PdvSale.items),
    ).order_by(PdvSale.created_at.desc(), PdvSale.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        'page': page, 'page_size': page_size, 'total': total,
        'own_sales_only': own_sales(user),
        'summary': {
            'net_gs': net,
            'refunded_gs': sum((refunds or zero for _, _, _, refunds in grouped), zero),
            'cancelled': sum(count for status, count, _, _ in grouped if status == 'cancelled'),
        },
        'items': [{
            'id': sale.id,
            'created_at': sale.created_at if sale.created_at.tzinfo else sale.created_at.replace(tzinfo=settings.tz),
            'account_id': sale.cliente_id, 'account_name': sale.cliente.nome,
            'customer_name': sale.cliente_nome,
            'seller': sale.vendedor.nome if sale.vendedor else None,
            'status': sale.status, 'total_gs': sale.total_gs,
            'refunded_gs': sale.refunded_gs,
            'net_gs': zero if sale.status == 'cancelled' else sale.total_gs - sale.refunded_gs,
            'lines': [{
                'id': line.id, 'name': line.item_name, 'quantity': line.quantity,
                'returned_quantity': line.returned_quantity,
            } for line in sorted(sale.items, key=lambda line: str(line.id))],
        } for sale in rows],
    }
