"""Read-only operation grouping. Raw audit records and their filters remain intact."""
import uuid
from sqlalchemy import case, cast, func, literal, or_, select, String
from ..models.access import AuditEvent

EVENT_FIELDS = ('id', 'occurred_at', 'user_id', 'actor_name', 'source', 'action',
                'module', 'entity', 'entity_id', 'request_id', 'route', 'method', 'status_code', 'changes')
ORDER_ACTIONS = ('order_reserve', 'order_edit', 'order_payment', 'order_conditional_dispatch',
                 'order_conditional_return', 'order_refund', 'order_cancel', 'order_checkout', 'orders_archived')


def event_view(row):
    return {key: getattr(row, key) for key in EVENT_FIELDS}


def scope(db, since, user_id=None, module=None, action=None):
    # Old records have no safe relationship snapshot. A unique sale in the exact
    # same request is evidence; proximity in time or the operator's name is not.
    anchors = (select(AuditEvent.request_id.label('request_id'), func.min(AuditEvent.entity_id).label('sale_id'))
               .where(AuditEvent.occurred_at >= since, AuditEvent.entity == 'pdv_sales',
                      AuditEvent.entity_id.isnot(None), AuditEvent.request_id.isnot(None),
                      AuditEvent.request_id != '', AuditEvent.action.notin_(('read', 'request')))
               .group_by(AuditEvent.request_id)
               .having(func.count(func.distinct(AuditEvent.entity_id)) == 1).subquery())
    sale_id = func.coalesce(func.nullif(AuditEvent.changes['_context']['sale_id'].as_string(), ''),
                           case((AuditEvent.entity == 'pdv_sales', AuditEvent.entity_id)), anchors.c.sale_id)
    group_key = case((sale_id.isnot(None), literal('pdv_sale:') + sale_id),
                     (func.nullif(AuditEvent.request_id, '').isnot(None), literal('request:') + AuditEvent.request_id),
                     else_=literal('event:') + cast(AuditEvent.id, String)).label('group_key')
    # Classify every movement in the filtered group, not only the three visible
    # examples. Unknown or deleted history must not masquerade as a transfer.
    movement_kind = case((AuditEvent.entity == 'stock_movements', case(
        (AuditEvent.action == 'create', func.coalesce(
            AuditEvent.changes['_context']['movement']['movement_type'].as_string(),
            AuditEvent.changes['movement_type']['after'].as_string(), 'unknown')),
        else_='unknown'))).label('movement_kind')
    statement = (select(AuditEvent.id, AuditEvent.occurred_at, AuditEvent.user_id, AuditEvent.actor_name,
                        AuditEvent.action, AuditEvent.module, AuditEvent.entity, group_key, movement_kind)
                 .outerjoin(anchors, anchors.c.request_id == AuditEvent.request_id)
                 .where(AuditEvent.occurred_at >= since, AuditEvent.action.notin_(('read', 'request'))))
    if user_id: statement = statement.where(AuditEvent.user_id == user_id)
    if module: statement = statement.where(AuditEvent.module == module)
    if action: statement = statement.where(AuditEvent.action == action)
    return statement.cte('audit_scope')


def grouped(db, scoped, offset, limit):
    groups = (select(scoped.c.group_key, func.count().label('event_count'),
                     func.min(scoped.c.occurred_at).label('first_at'), func.max(scoped.c.occurred_at).label('last_at'),
                     func.min(scoped.c.module).label('module'), func.min(scoped.c.actor_name).label('actor_name'),
                     func.count(func.distinct(func.coalesce(scoped.c.module, ''))).label('module_count'),
                     func.count(func.distinct(func.coalesce(scoped.c.entity, ''))).label('entity_count'),
                     func.count(func.distinct(scoped.c.action)).label('action_count'),
                     func.max(case((scoped.c.module == 'inventory', 1), else_=0)).label('has_inventory'),
                     func.min(scoped.c.movement_kind).label('first_movement_kind'),
                     func.max(scoped.c.movement_kind).label('last_movement_kind'),
                     func.count(func.distinct(func.coalesce(cast(scoped.c.user_id, String), 'system'))).label('actor_count'))
              .group_by(scoped.c.group_key))
    total = db.execute(select(func.count()).select_from(groups.subquery())).scalar_one()
    rows = db.execute(groups.order_by(func.max(scoped.c.occurred_at).desc(), scoped.c.group_key).offset(offset).limit(limit)).all()
    if not rows:
        return total, []
    keys = [row.group_key for row in rows]
    # Bound samples per operation instead of materializing a bulk mutation's
    # potentially thousands of rows. Full details have their own pagination.
    # Keep one semantic anchor independently of stock-first samples. Otherwise
    # a sale with many items hides its seller/value, and a product's initial
    # stock can hide the fact that it was a new registration.
    summary_priority = case((scoped.c.entity == 'pdv_sales', 0),
                            (scoped.c.action.in_(ORDER_ACTIONS), 1),
                            ((scoped.c.entity == 'inventory_items') & (scoped.c.action == 'create'), 2),
                            (scoped.c.entity == 'stock_movements', 3), else_=4)
    ranked = (select(scoped.c.id, scoped.c.group_key,
                     func.row_number().over(partition_by=scoped.c.group_key, order_by=(
                         case((scoped.c.entity == 'stock_movements', 0), else_=1),
                         scoped.c.occurred_at.desc(), scoped.c.id.desc())).label('rank'),
                     func.row_number().over(partition_by=scoped.c.group_key, order_by=(
                         summary_priority, scoped.c.occurred_at.desc(),
                         case((scoped.c.action.in_(('create', 'update', 'delete')), 1), else_=0),
                         scoped.c.id.desc())).label('summary_rank'))
              .where(scoped.c.group_key.in_(keys)).subquery())
    samples = db.execute(select(AuditEvent, ranked.c.group_key, ranked.c.rank, ranked.c.summary_rank)
                         .join(ranked, ranked.c.id == AuditEvent.id)
                         .where(or_(ranked.c.rank <= 3, ranked.c.summary_rank == 1))
                         .order_by(ranked.c.group_key, ranked.c.rank)).all()
    by_group, summaries = {}, {}
    for event, key, rank, summary_rank in samples:
        view = event_view(event)
        if rank <= 3:
            by_group.setdefault(key, []).append(view)
        if summary_rank == 1:
            summaries[key] = view
    result = []
    for row in rows:
        sale = row.group_key.split(':', 1)[1] if row.group_key.startswith('pdv_sale:') else None
        try: sale = str(uuid.UUID(sale)) if sale else None
        except ValueError: sale = None
        sample = by_group.get(row.group_key, [])
        kind = 'sale' if sale else 'stock' if row.has_inventory else 'operation'
        movement_kind = row.first_movement_kind if row.first_movement_kind == row.last_movement_kind else None
        if movement_kind not in ('entry', 'exit', 'transfer', 'adjustment'):
            movement_kind = None
        result.append({'key': row.group_key, 'kind': kind, 'sale_id': sale,
                       'sale_code': uuid.UUID(sale).hex[:10].upper() if sale else None,
                       'event_count': row.event_count, 'first_at': row.first_at, 'last_at': row.last_at,
                       'module': 'pdv' if sale else row.module, 'actor_name': row.actor_name,
                       'actor_count': row.actor_count, 'samples': sample,
                       'summary_event': summaries.get(row.group_key), 'entity_count': row.entity_count,
                       'action_count': row.action_count, 'module_count': row.module_count,
                       'movement_kind': movement_kind})
    return total, result


def details(db, scoped, key, offset, limit):
    ids = select(scoped.c.id).where(scoped.c.group_key == key)
    events = db.query(AuditEvent).filter(AuditEvent.id.in_(ids))
    total = events.count()
    rows = events.order_by(AuditEvent.occurred_at, AuditEvent.id).offset(offset).limit(limit).all()
    return {'key': key, 'total': total, 'offset': offset, 'limit': limit, 'events': [event_view(row) for row in rows]}


def operations_by_user(db, scoped):
    return dict(db.execute(select(scoped.c.user_id, func.count(func.distinct(scoped.c.group_key)))
                           .where(scoped.c.action.notin_(('login', 'logout', 'login_failed')))
                           .group_by(scoped.c.user_id)).all())
