"""Shared persistence and filter rules; never change product identity or balances."""
from sqlalchemy import inspect
from .inventory_taxonomy_v1 import FIELDS, canonical, key, text_key, vocabulary


def clean_product_name(value):
    """Trim redundant whitespace without changing model codes or chosen casing."""
    return ' '.join(value.split()) if value else value


def normalize_pending_items(session, flush_context, instances):
    from ..models.inventory import Item
    pending = [obj for obj in session.new | session.dirty
               if isinstance(obj, Item) and not obj.deleted_at]
    for field in FIELDS:
        changed = [obj for obj in pending if obj in session.new or inspect(obj).attrs[field].history.has_changes()]
        if not changed:
            continue
        column = getattr(Item, field)
        # Only the small vocabulary is loaded; no images, balances or customer data.
        values = [row[0] for row in session.query(column).filter(Item.deleted_at.is_(None)).distinct()]
        labels = vocabulary(values + [getattr(obj, field) for obj in changed], field)
        for obj in changed:
            value = getattr(obj, field)
            setattr(obj, field, labels.get(key(value, field), canonical(value, field)))


def facet_filter(db, column, value, *, partial=False, values=None):
    from ..models.inventory import Item
    field = column.key
    wanted = key(value, field)
    if values is None:
        values = [row[0] for row in db.query(column).filter(Item.deleted_at.is_(None)).distinct() if row[0]]
    def matches(raw):
        candidate = key(raw, field)
        return (wanted in candidate) if partial else (candidate == wanted or
            (field == 'category' and candidate.startswith(wanted + ' > ')))
    return column.in_([raw for raw in values if matches(raw)])


def search_text(value):
    # Resolve a full brand alias before tokenization, including within a longer query.
    import re
    return re.sub(r'\bea7\s+emp[oó]rio\s+armani\b', 'Emporio Armani', value, flags=re.I)


def facet_filters(db):
    """Request-local cache: at most one vocabulary query per field, never stale across writes."""
    from ..models.inventory import Item
    values = {}
    def compare(column, value, *, partial=False):
        if column.key not in values:
            values[column.key] = [row[0] for row in db.query(column).filter(Item.deleted_at.is_(None)).distinct() if row[0]]
        return facet_filter(db, column, value, partial=partial, values=values[column.key])
    return compare
