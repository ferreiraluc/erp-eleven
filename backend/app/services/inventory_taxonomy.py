"""Shared persistence and filter rules; never change product identity or balances."""
from sqlalchemy import inspect
from .inventory_taxonomy_v2 import FIELDS, canonical, key as legacy_key, text_key, vocabulary, canonical_size, normalized_size_name
from .inventory_colors import color_key, color_search_text


def key(value, field):
    return color_key(value) if field == 'color' else legacy_key(value, field)


def clean_product_name(value):
    """Trim redundant whitespace without changing model codes or chosen casing."""
    return ' '.join(value.split()) if value else value


def normalize_pending_items(session, flush_context, instances):
    from ..models.inventory import Item
    pending = [obj for obj in session.new | session.dirty
               if isinstance(obj, Item) and not obj.deleted_at]
    for obj in pending:
        if obj in session.new or inspect(obj).attrs.size.history.has_changes():
            old = obj.size
            obj.size = canonical_size(old)
            obj.name = normalized_size_name(obj.name, old, obj.size)
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
        if partial and field == 'color':
            return wanted in color_search_text(raw)
        return (wanted in candidate) if partial else (candidate == wanted or
            (field == 'category' and candidate.startswith(wanted + ' > ')))
    return column.in_([raw for raw in values if matches(raw)])


def search_text(value):
    # Resolve a full brand alias before tokenization, including within a longer query.
    import re
    return re.sub(r'\bea7\s+emp[oó]rio\s+armani\b', 'Emporio Armani', value, flags=re.I)


class FacetFilters:
    """Request-local vocabulary, shared by filters and spelling suggestions."""

    def __init__(self, db):
        self.db = db
        self.values = {}

    def values_for(self, column):
        from ..models.inventory import Item
        if column.key not in self.values:
            self.values[column.key] = [row[0] for row in self.db.query(column)
                .filter(Item.deleted_at.is_(None)).distinct() if row[0]]
        return self.values[column.key]

    def __call__(self, column, value, *, partial=False):
        return facet_filter(self.db, column, value, partial=partial, values=self.values_for(column))

    def words(self):
        import re
        from ..models.inventory import Item
        return {word for field in FIELDS for raw in self.values_for(getattr(Item, field))
                for word in re.findall(r'[a-z]+', key(raw, field)) if len(word) >= 4}


def facet_filters(db):
    """At most one vocabulary query per field; never stale across writes."""
    return FacetFilters(db)
