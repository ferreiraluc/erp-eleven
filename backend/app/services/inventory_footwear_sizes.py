"""The store's footwear equivalences, not a manufacturer's universal size chart.

Confirmed rule for unlabeled shoes: 6–13 (+ half sizes) are US; larger numbers
are BR, except Boss and Dolce & Gabbana. Explicit units always take precedence.
No stock, product sizes or variant identities are rewritten by a search.
"""
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, false, or_

from ..models.inventory import Item
from .inventory_taxonomy_v1 import text_key

OFFSETS = {'US': Decimal(0), 'BR': Decimal(32), 'BOSS': Decimal(33), 'EU': Decimal(34)}
UNITS = r'(?:eu/it|us|br|boss|eu|it)'
NUMBER = r'\d{1,2}(?:[.,]\d{1,2})?'
_NUMBER_SIZE = re.compile(rf'(?:(?P<prefix>{UNITS})\s*)?(?P<number>{NUMBER})\s*(?P<suffix>{UNITS})?\Z')
FOOTWEAR = r'(^|[^a-z])(calcados?|tenis|chinelos?|sandalias?|sapatos?|botas?|mocassim|mocassins|sneakers?|shoes?|slides?|slippers?|loafers?|sandals?)([^a-z]|$)'
BOSS = r'(^|[^a-z])boss([^a-z]|$)'
DG = r'(^|[^a-z])(d\s*&\s*g|dg|dolce\s*(&\s*)?gabbana)([^a-z]|$)'


@dataclass(frozen=True)
class NumericSize:
    number: Decimal
    system: str | None = None


def numeric_size(value):
    value = re.sub(r'^(?:tamanho|tam\.?|size|talle)\s*:?\s*', '', text_key(value))
    match = _NUMBER_SIZE.fullmatch(value)
    if not match:
        return None
    unit = lambda text: 'EU' if text in ('eu', 'it', 'eu/it') else text.upper() if text else None
    prefix, suffix = unit(match['prefix']), unit(match['suffix'])
    if prefix and suffix and prefix != suffix:
        return None
    return NumericSize(Decimal(match['number'].replace(',', '.')), prefix or suffix)


def inferred_system(number, brand=''):
    if Decimal(6) <= number < Decimal(14):
        return 'US'
    if re.search(BOSS, text_key(brand)):
        return 'BOSS'
    if re.search(DG, text_key(brand)):
        return 'EU'
    return 'BR'


def us_size(size, system):
    value = size.number - OFFSETS[system]
    # Only the eight rows explicitly requested by the store. Half sizes belong
    # to their integer row; never extrapolate to children, women or other charts.
    return value if 6 <= value < 14 and value % 1 in (0, Decimal('.5')) else None


def footwear_filter(normalize):
    return or_(*(normalize(column).regexp_match(FOOTWEAR) for column in (Item.name, Item.category)))


def equivalent_filter(wanted, stored_sizes, normalize, brand_context=''):
    """Return matching shoes plus rank clauses, using small size vocabulary only.

    A row contains an integer and its half size. Search 11 favors 11, then the
    corresponding labels, then half sizes; 11.5 favors the half-size labels.
    """
    query_size = numeric_size(wanted)
    if not query_size:
        return None
    query_system = query_size.system or inferred_system(query_size.number, brand_context)
    query_us = us_size(query_size, query_system)
    if query_us is None:
        return None
    boss = normalize(Item.brand).regexp_match(BOSS)
    dg = and_(~boss, normalize(Item.brand).regexp_match(DG))
    footwear = footwear_filter(normalize)
    rank_sizes = {}
    for raw in stored_sizes:
        parsed = numeric_size(raw)
        if not parsed:
            continue
        if parsed.system:
            systems = [(parsed.system, True)]
        elif 6 <= parsed.number < 14:
            systems = [('US', True)]
        else:
            systems = [('BOSS', boss), ('EU', dg), ('BR', and_(~boss, ~dg))]
        for system, brand_rule in systems:
            actual_us = us_size(parsed, system)
            if actual_us is None or int(actual_us) != int(query_us):
                continue
            # Prefer the exact scale/size, then the same equivalent value, then
            # the adjacent half size. All ranking runs before SQL pagination.
            rank = (0 if actual_us == query_us else 2) + (system != query_system)
            key = (rank, system, parsed.system is None and system != 'US')
            if key not in rank_sizes:
                rank_sizes[key] = (brand_rule, [])
            rank_sizes[key][1].append(raw)
    clauses = [(and_(footwear, brand_rule, Item.size.in_(values)), rank)
               for (rank, _, _), (brand_rule, values) in rank_sizes.items()]
    condition = or_(*(clause for clause, _ in clauses)) if clauses else false()
    return condition, clauses
