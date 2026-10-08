"""Deterministic catalog search: combine attributes before SQL pagination.

No model calls or product rewrites. Codes remain literal identifiers; footwear
equivalences use the store's own table, only on items identified as footwear.
"""
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, case, false, func, literal, or_

from ..models.inventory import Item
from .inventory_taxonomy import facet_filters, search_text
from .inventory_footwear_sizes import DG, NUMBER, equivalent_filter, footwear_filter, numeric_size

_ACCENTS = 'áàâãäéèêëíìîïóòôõöúùûüçñ'
_ASCII = 'aaaaaeeeeiiiiooooouuuucn'
_TRANSLATION = str.maketrans(_ACCENTS + _ACCENTS.upper(), _ASCII * 2)
_SIZE = re.compile(r'(?:\d{1,2}(?:[.,]\d{1,2})?|[2-6]xl|xxxs|xxs|xs|s|m|l|xl|xxl|xxxl|ppp|pp|p|g|gg|ggg|xg|xgg|u|unico)\Z')
_MARKER = re.compile(r'\b(?:tamanho|tam\.?|size|talle|numero|n[º°])\s*:?\s+(\S+)')
_CONNECTORS = {'de', 'do', 'da', 'dos', 'das', 'no', 'na'}
_KINDS = (
    ('camiseta', 'camisetas', 't-shirt', 't-shirts', 'tshirt', 'tshirts', 't shirt', 't shirts'),
    ('tenis', 'sneaker', 'sneakers'),
    ('chinelo', 'chinelos', 'slide', 'slides'),
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
        return format(Decimal(value.replace(',', '.')).normalize(), 'f')
    return value


def parse(value):
    text = text_key(search_text(value)).strip()
    # Country labels belong to the size. A separated "Boss" remains a brand
    # filter ("Tênis Boss 41"); compact "41BOSS" explicitly names a scale.
    units = r'(eu/it|us|br|eu|it)'
    text = re.sub(rf'(?<![a-z0-9]){units}\s*({NUMBER})(?![a-z0-9.,])', r'\2\1', text)
    text = re.sub(rf'(?<![a-z0-9])({NUMBER})\s*{units}(?![a-z0-9])', r'\1\2', text)
    text = re.sub(r'\bdolce\s*(?:&\s*)?gabbana\b', 'dg', text)
    sizes = []

    def explicit(match):
        sizes.append(size_key(match[1]))
        return ' '

    text = _MARKER.sub(explicit, text)
    text = re.sub(r'\bt[-\s]?shirts?\b', 't-shirt', text)
    tokens = text.split()
    terms = []
    for token in tokens:
        if _SIZE.fullmatch(token) or numeric_size(token):
            sizes.append(size_key(token))
        elif token not in _CONNECTORS or (len(tokens) == 1 and not sizes):
            terms.append(token)
    return terms, sizes


@dataclass
class CatalogSearch:
    condition: object
    rank: object


def build_search(db, value, *, taxonomy_filter=None, brand_context='', size=None):
    """All words/sizes must match one item; exact codes remain discoverable."""
    terms, sizes = parse(value)
    if size:
        sizes.append(size_key(size))
    if not value.strip() and not sizes:
        return CatalogSearch(True, literal(0))
    normalize = normalizer(db)
    taxonomy_filter = taxonomy_filter or facet_filters(db)
    predicates = []
    ranks = []
    for term in terms:
        kinds = next((group for group in _KINDS if term in group), None)
        if kinds:
            # "calça" must not match "calçados". Known product types use
            # complete words; ordinary model/brand fragments stay searchable.
            pattern = r'(^|[^a-z])(' + '|'.join(re.escape(kind) for kind in kinds) + r')([^a-z]|$)'
            product_type = or_(*(normalize(column).regexp_match(pattern)
                                 for column in (Item.name, Item.category, Item.group_key)))
        else:
            product_type = or_(normalize(Item.name).contains(term, autoescape=True),
                               normalize(Item.group_key).contains(term, autoescape=True),
                               taxonomy_filter(Item.category, term, partial=True))
        predicates.append(or_(
            *(normalize(column).contains(term, autoescape=True)
              for column in (Item.sku_internal, Item.barcode)),
            taxonomy_filter(Item.brand, term, partial=True),
            taxonomy_filter(Item.color, term, partial=True),
            normalize(Item.brand).regexp_match(DG) if term in ('dg', 'd&g') else false(),
            product_type,
        ))
    size_predicates = []
    if sizes:
        # Small vocabulary only; never load photos/products for in-memory filtering.
        stored_sizes = [row[0] for row in db.query(Item.size)
                        .filter(Item.deleted_at.is_(None), Item.size.isnot(None)).distinct()]
        footwear = footwear_filter(normalize)
        for wanted in set(sizes):
            exact = Item.size.in_([raw for raw in stored_sizes if size_key(raw) == wanted])
            equivalents = equivalent_filter(wanted, stored_sizes, normalize,
                                            brand_context or ' '.join(terms))
            if equivalents is None:
                size_predicates.append(exact)
            else:
                matching_shoes, ranked_shoes = equivalents
                # Never let a bare numeric match override the shoe's actual
                # scale. Clothes retain exact size matching, without expansion.
                literal_non_shoes = and_(~footwear, exact)
                size_predicates.append(or_(literal_non_shoes, matching_shoes))
                ranks.extend(ranked_shoes)
                ranks.append((literal_non_shoes, 0))
    predicates.extend(size_predicates)
    structured = and_(*predicates) if predicates else false()
    # A short SKU like "M" or "41" can itself look like a size. Preserve exact
    # identity without allowing arbitrary barcode substrings to satisfy size 41.
    identifier = or_(func.lower(Item.sku_internal) == value.strip().lower(),
                     func.lower(Item.barcode) == value.strip().lower()) if value.strip() else false()
    if size and size_predicates:
        identifier = and_(identifier, *size_predicates)
    rank = case((identifier, -1), *sorted(ranks, key=lambda pair: pair[1]), else_=4)
    return CatalogSearch(or_(structured, identifier), rank)


def search_filter(db, value, *, taxonomy_filter=None, brand_context=''):
    return build_search(db, value, taxonomy_filter=taxonomy_filter, brand_context=brand_context).condition
