"""Deterministic catalog search: combine attributes before SQL pagination.

No model calls, product rewrites, or shoe-size/country conversions. Codes remain
literal identifiers; a size must match the size field, not a substring of a code.
"""
import re
from decimal import Decimal

from sqlalchemy import and_, false, func, or_

from ..models.inventory import Item
from .inventory_taxonomy import facet_filters, search_text

_ACCENTS = 'áàâãäéèêëíìîïóòôõöúùûüçñ'
_ASCII = 'aaaaaeeeeiiiiooooouuuucn'
_TRANSLATION = str.maketrans(_ACCENTS + _ACCENTS.upper(), _ASCII * 2)
_SIZE = re.compile(r'(?:\d{1,2}(?:[.,]\d{1,2})?|[2-6]xl|xxxs|xxs|xs|s|m|l|xl|xxl|xxxl|ppp|pp|p|g|gg|ggg|xg|xgg|u|unico)\Z')
_MARKER = re.compile(r'\b(?:tamanho|tam\.?|size|talle|numero|n[º°])\s*:?\s+(\S+)')
_CONNECTORS = {'de', 'do', 'da', 'dos', 'das', 'no', 'na'}
_KINDS = (
    ('camiseta', 'camisetas', 't-shirt', 't-shirts', 'tshirt', 'tshirts', 't shirt', 't shirts'),
    ('tenis', 'sneaker', 'sneakers'),
    ('calca', 'calcas'),
    ('camisa', 'camisas'),
)


def text_key(value):
    # Same accent table in PostgreSQL and SQLite, independent of DB collation.
    return (value or '').translate(_TRANSLATION).lower()


def normalizer(db):
    if db.bind.dialect.name == 'sqlite':
        db.connection().connection.driver_connection.create_function(
            'inventory_search_text', 1, text_key, deterministic=True)
        return func.inventory_search_text
    return lambda column: func.lower(func.translate(func.coalesce(column, ''),
        _ACCENTS + _ACCENTS.upper(), _ASCII * 2))


def size_key(value):
    value = re.sub(r'^(?:tamanho|tam\.?|size|talle)\s*:?\s*', '', text_key(value).strip())
    if re.fullmatch(r'\d+(?:[.,]\d+)?', value):
        return str(Decimal(value.replace(',', '.')).normalize())
    return value


def parse(value):
    text = text_key(search_text(value)).strip()
    sizes = []

    def explicit(match):
        sizes.append(size_key(match[1]))
        return ' '

    text = _MARKER.sub(explicit, text)
    text = re.sub(r'\bt[-\s]?shirts?\b', 't-shirt', text)
    tokens = text.split()
    terms = []
    for token in tokens:
        if _SIZE.fullmatch(token):
            sizes.append(size_key(token))
        elif token not in _CONNECTORS or (len(tokens) == 1 and not sizes):
            terms.append(token)
    return terms, sizes


def search_filter(db, value, *, taxonomy_filter=None):
    """All words/sizes must match one item; exact codes remain discoverable."""
    terms, sizes = parse(value)
    if not value.strip():
        return True
    normalize = normalizer(db)
    taxonomy_filter = taxonomy_filter or facet_filters(db)
    predicates = []
    for term in terms:
        kinds = next((group for group in _KINDS if term in group), (term,))
        predicates.append(or_(
            *(normalize(column).contains(term, autoescape=True)
              for column in (Item.name, Item.sku_internal, Item.barcode, Item.group_key)),
            taxonomy_filter(Item.brand, term, partial=True),
            taxonomy_filter(Item.color, term, partial=True),
            *(or_(normalize(Item.name).contains(kind, autoescape=True),
                  taxonomy_filter(Item.category, kind, partial=True)) for kind in kinds),
        ))
    if sizes:
        # Small vocabulary only; never load photos/products for in-memory filtering.
        stored_sizes = [row[0] for row in db.query(Item.size)
                        .filter(Item.deleted_at.is_(None), Item.size.isnot(None)).distinct()]
        predicates.extend(Item.size.in_([raw for raw in stored_sizes if size_key(raw) == wanted])
                          for wanted in set(sizes))
    structured = and_(*predicates) if predicates else false()
    # A short SKU like "M" or "41" can itself look like a size. Preserve exact
    # identity without allowing arbitrary barcode substrings to satisfy size 41.
    return or_(structured, func.lower(Item.sku_internal) == value.strip().lower(),
               func.lower(Item.barcode) == value.strip().lower())
