"""Authorization is derived from the authenticated user, never a client-side filter."""
from fastapi import HTTPException
from ..models.usuario import UsuarioRole

OWNER_EMAIL = "lucas@eleven.com"


def is_reseller(user):
    return getattr(user, 'access_profile', 'standard') == 'reseller'


# Match registered route templates, not URL prefixes. New endpoints remain
# unavailable to the restricted profile until explicitly reviewed here.
RESELLER_READ_ROUTES = frozenset({
    '/api/auth/me',
    '/api/inventory/search-index', '/api/inventory/suppliers',
    '/api/inventory/items', '/api/inventory/items/distinct-values',
    '/api/inventory/items/barcode/{code}', '/api/inventory/items/{item_id}',
    '/api/inventory/items/thumbnails', '/api/inventory/items/{item_id}/thumbnail',
    '/api/inventory/items/{item_id}/photos', '/api/inventory/items/{item_id}/related',
    '/api/inventory/items/{item_id}/grade-suggestions',
    '/api/inventory/alerts/summary', '/api/inventory/groups',
    '/api/inventory/groups/directory', '/api/inventory/groups/members',
    '/api/inventory/groups/suggestions', '/api/inventory/suggestions',
    '/api/inventory/receiving-lots', '/api/inventory/receiving-lots/{lot_id}/items',
    '/api/exchange-rates/current', '/api/exchange-rates/history',
    '/api/exchange-rates/sales-average/{currency_pair}',
    '/api/notifications/inbox', '/api/notifications/preferences',
    '/api/notifications/push/config', '/api/notifications/push/native/config',
})
RESELLER_ACCOUNT_ACTIONS = frozenset({
    ('POST', '/api/auth/password'), ('POST', '/api/auth/logout'),
    ('POST', '/api/notifications/read-all'),
    ('POST', '/api/notifications/{notification_id}/read'),
    ('POST', '/api/notifications/push/subscribe'),
    ('POST', '/api/notifications/push/native/subscribe'),
    ('POST', '/api/notifications/push/unsubscribe'),
})


def require_profile_route(user, method, route):
    if not is_reseller(user):
        return
    if (method == 'GET' and route in RESELLER_READ_ROUTES) or (method, route) in RESELLER_ACCOUNT_ACTIONS:
        return
    raise HTTPException(403, 'Este perfil permite somente consultar estoque, câmbio e suas notificações.')


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


def orders_query(query, user):
    """Legacy logistics stay shared; commercial orders use the PDV sales scope."""
    from sqlalchemy import or_
    from ..models.pedido import Pedido
    legacy = Pedido.commerce_status.is_(None)
    if (user is None or not user.ativo or
            user.role not in (UsuarioRole.ADMIN, UsuarioRole.GERENTE, UsuarioRole.VENDEDOR)):
        return query.filter(legacy)
    if own_sales(user):
        return query.filter(or_(legacy, Pedido.vendedor_id == user.id))
    return query


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
