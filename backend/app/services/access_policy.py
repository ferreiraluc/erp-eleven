"""Authorization is derived from the authenticated user, never a client-side filter."""
from fastapi import HTTPException
from ..models.usuario import UsuarioRole

OWNER_EMAIL = "lucas@eleven.com"


def is_owner(user):
    return user.email.strip().lower() == OWNER_EMAIL and user.role == UsuarioRole.ADMIN


def own_sales(user):
    return getattr(user, 'sales_scope', 'all') == 'own'


def sales_query(query, model, user, pdv=False):
    if not own_sales(user):
        return query
    seller_id = user.id if pdv else user.vendedor_id
    # An unmapped employee cannot fall back to the full store.
    return query.filter(model.vendedor_id == seller_id) if seller_id else query.filter(False)


def require_all_sales(user):
    if own_sales(user):
        raise HTTPException(403, 'Esta conta pode consultar apenas suas próprias vendas.')


def require_sale_owner(user, seller_id, pdv=False):
    expected = user.id if pdv else user.vendedor_id
    if own_sales(user) and (not expected or seller_id != expected):
        raise HTTPException(404, 'Venda ou vendedor não encontrado.')


def sales_context_since(db, user):
    """Do not replay financial context acquired before a user's access was reduced."""
    if not own_sales(user):
        return None
    from ..models.access import AuditEvent
    return db.query(AuditEvent.occurred_at).filter(
        AuditEvent.entity == 'usuarios', AuditEvent.entity_id == str(user.id),
        AuditEvent.action.in_(['access_changed', 'access_provisioned', 'access_created']),
    ).order_by(AuditEvent.occurred_at.desc()).limit(1).scalar()
