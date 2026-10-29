"""Deterministic catalog search: combine attributes before SQL pagination.

No model calls or product rewrites. Code separators and a limited leading-digit
variant are search aliases, never product identities. Footwear equivalences use
the store's own table, only on items identified as footwear.
"""
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, case, false, func, literal, or_

from ..models.inventory import Item
from .inventory_taxonomy import facet_filters, search_text, canonical_size
from .inventory_footwear_sizes import DG, NUMBER, equivalent_filter, footwear_filter, numeric_size

_ACCENTS = 'áàâãäéèêëíìîïóòôõöúùûüçñ'
_ASCII = 'aaaaaeeeeiiiiooooouuuucn'
_TRANSLATION = str.maketrans(_ACCENTS + _ACCENTS.upper(), _ASCII * 2)
_SIZE = re.compile(r'(?:\d{1,2}(?:[.,]\d{1,2})?|[2-6]xl|xxxs|xxs|xs|s|m|l|xl|xxl|xxxl|ppp|pp|p|g|gg|ggg|xg|xgg|u|unico)\Z')
_MARKER = re.compile(r'\b(?:tamanho|tam\.?|size|talle|numero|n[º°])\s*:?\s+(\S+)')
_CONNECTORS = {'de', 'do', 'da', 'dos', 'das', 'no', 'na'}
_KINDS = (
    ('camiseta', 'camisetas', 't-shirt', 't-shirts', 'tshirt', 'tshirts', 't shirt', 't shirts', 'tsirt', 't-sirt', 'tshrit', 'camseta', 'camsetas'),
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
    return canonical_size(value).lower()


def one_typo(a, b):
    """One insertion/deletion/substitution or adjacent swap, not arbitrary similarity."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        differences = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return len(differences) <= 1 or (len(differences) == 2
            and differences[1] == differences[0] + 1
            and a[differences[0]:differences[1] + 1] == b[differences[0]:differences[1] + 1][::-1])
    short, long = sorted((a, b), key=len)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


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
    # "Y 26" is a model, not size 26. Short clothing sizes/brand DG and
    # country scales stay independent ("M 40", "DG 40", "US 11").
    def join_code(match):
        letters, digits = match[1], match[2]
        if _SIZE.fullmatch(letters) or letters in {'dg', 'us', 'br', 'eu', 'it'}:
            return match[0]
        if len(letters) > 1 and len(digits) < 3:
            return match[0]
        return letters + digits

    text = re.sub(r'(?<![a-z0-9])([a-z]{1,3})(?:\s+|\s*[-_./]\s*)(\d{2,})(?![a-z0-9.,])', join_code, text)
    tokens = text.split()
    terms = []
    for token in tokens:
        if _SIZE.fullmatch(token) or numeric_size(token):
            sizes.append(size_key(token))
        elif token not in _CONNECTORS or (len(tokens) == 1 and not sizes):
            terms.append(token)
    return terms, sizes


def code_pattern(term):
    """Keep all model digits; allow separators and 8UB102/UB102-style prefixes."""
    if not re.fullmatch(r'[a-z0-9]+(?:[-_./][a-z0-9]+)*', term):
        return None
    if not re.search('[a-z]', term) or not re.search('[0-9]', term):
        return None
    compact = re.sub('[-_./]', '', term)
    # Only a single leading digit before >=2 letters + >=2 digits. A different
    # numeric model suffix (DN0281 vs DN0282) is never corrected by distance.
    core = compact[1:] if re.fullmatch(r'\d[a-z]{2,}\d{2,}', compact) else compact
    prefix = '[0-9]?' if re.fullmatch(r'[a-z]{2,}\d{2,}', core) else ''
    parts = re.findall(r'[a-z]+|\d+', core)
    # Retain explicit numeric separators, e.g. Y-26-09, as separate components.
    if core == compact and re.search('[-_./]', term):
        parts = re.findall(r'[a-z]+|\d+', term)
    pattern = '[-_./ ]*'.join(re.escape(part) for part in parts)
    return r'(^|[^a-z0-9])' + prefix + pattern + r'([^a-z0-9]|$)'


def spelling_variants(term, vocabulary):
    if not term.isalpha() or not 4 <= len(term) <= 40:
        return [term]
    # Existing words/fragments have intentional meanings (camisa != camiseta).
    if any(term in word for word in vocabulary):
        return [term]
    candidates = sorted((word for word in vocabulary if one_typo(term, word)),
                        key=lambda word: (abs(len(word) - len(term)), word))
    return [term, *candidates[:8]]


def code_typo_pattern(term):
    """One mistyped model letter, with digits and complete token boundaries intact."""
    compact = re.sub(r'[-_./]', '', term)
    if not re.fullmatch(r'[a-z0-9]{5,24}', compact) or not re.search(r'\d', compact) or len(re.findall('[a-z]', compact)) < 2:
        return None
    variants = []
    for index, letter in enumerate(compact):
        if letter.isalpha():
            variants.append('[-_./ ]*'.join('[a-z]' if i == index else re.escape(c) for i, c in enumerate(compact)))
    return r'(^|[^a-z0-9])(?:' + '|'.join(variants) + r')([^a-z0-9]|$)'


@dataclass
class CatalogSearch:
    condition: object
    rank: object


def build_search(db, value, *, taxonomy_filter=None, brand_context='', size=None):
    """Words/sizes must match one item; shared model codes can suggest related items."""
    if re.fullmatch(r'INV-[A-Z0-9]{6}', value.strip().upper()) and not size:
        # Internal QR codes are exact identities; never fuzzy-match a different item.
        code = value.strip().upper()
        # A bare -1 in ORDER BY is interpreted by PostgreSQL as a column
        # position, so keep the rank as an expression for catalog pagination.
        return CatalogSearch(Item.inventory_code == code,
                             case((Item.inventory_code == code, -1), else_=0))
    terms, sizes = parse(value)
    if size:
        sizes.append(size_key(size))
    if not value.strip() and not sizes:
        return CatalogSearch(True, literal(0))
    normalize = normalizer(db)
    taxonomy_filter = taxonomy_filter or facet_filters(db)
    predicates = []
    code_predicates = []
    strict_predicates = []
    ranks = []
    vocabulary = {word for group in _KINDS for word in group if word.isalpha()}
    if any(term.isalpha() and 4 <= len(term) <= 40 for term in terms):
        vocabulary.update(taxonomy_filter.words())

    def term_filter(term):
        kinds = next((group for group in _KINDS if term in group), None)
        if kinds:
            # "calça" must not match "calçados". Known product types use
            # complete words; ordinary model/brand fragments stay searchable.
            pattern = r'(^|[^a-z])(' + '|'.join(re.escape(kind) for kind in kinds) + r')([^a-z]|$)'
            product_type = or_(*(normalize(column).regexp_match(pattern)
                                 for column in (Item.name, Item.category, Item.group_key, Item.description)))
        else:
            product_type = or_(normalize(Item.name).contains(term, autoescape=True),
                               normalize(Item.group_key).contains(term, autoescape=True),
                               normalize(Item.description).contains(term, autoescape=True),
                               taxonomy_filter(Item.category, term, partial=True))
        return or_(
            *(normalize(column).contains(term, autoescape=True)
              for column in (Item.sku_internal, Item.barcode)),
            taxonomy_filter(Item.brand, term, partial=True),
            taxonomy_filter(Item.color, term, partial=True),
            normalize(Item.brand).regexp_match(DG) if term in ('dg', 'd&g') else false(),
            product_type,
        )

    for term in terms:
        strict = term_filter(term)
        strict_predicates.append(strict)
        pattern = code_pattern(term)
        if pattern:
            typo = code_typo_pattern(term)
            if typo:
                pattern = '(?:' + pattern + '|' + typo + ')'
            code_predicates.append(or_(strict, *(normalize(column).regexp_match(pattern)
                for column in (Item.name, Item.group_key, Item.sku_internal, Item.barcode, Item.description))))
        else:
            predicates.append(or_(*(term_filter(candidate)
                for candidate in spelling_variants(term, vocabulary))))
    if code_predicates:
        predicates.append(or_(*code_predicates))
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
    public_code = value.strip().upper()
    if re.fullmatch(r'[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}', public_code):
        public_code = 'INV-' + public_code
    identifier = or_(func.lower(Item.sku_internal) == value.strip().lower(),
                     Item.inventory_code == public_code,
                     func.lower(Item.barcode) == value.strip().lower()) if value.strip() else false()
    if size and size_predicates:
        identifier = and_(identifier, *size_predicates)
    # Literal matches/all supplied model references precede suggestions, while
    # preserving the existing footwear relevance within each spelling tier.
    spelling_rank = sum(case((condition, 0), else_=10) for condition in strict_predicates)
    size_rank = case(*sorted(ranks, key=lambda pair: pair[1]), else_=4) if ranks else literal(4)
    rank = case((identifier, -1), else_=spelling_rank + size_rank)
    return CatalogSearch(or_(structured, identifier), rank)


def search_filter(db, value, *, taxonomy_filter=None, brand_context=''):
    return build_search(db, value, taxonomy_filter=taxonomy_filter, brand_context=brand_context).condition
