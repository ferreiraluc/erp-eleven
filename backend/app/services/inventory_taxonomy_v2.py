"""Catalog aliases v2. Pure rules shared by runtime and its immutable backfill."""
import re
from . import inventory_taxonomy_v1 as v1

FIELDS = v1.FIELDS
text_key = v1.text_key
SIZE_ALIASES = {'P': 'S', 'S': 'S', 'M': 'M', 'G': 'L', 'L': 'L',
                'GG': 'XL', 'XL': 'XL', 'XXL': '2XL', '2XL': '2XL'}


def canonical_size(value):
    if value is None:
        return None
    clean = ' '.join(value.split())
    return SIZE_ALIASES.get(clean.upper(), clean)


def canonical(value, field):
    if field == 'brand' and re.fullmatch(r'(?:dg|d&g|dolce&?gabbana)', re.sub(r'\s+', '', text_key(value))):
        return 'Dolce & Gabbana'
    return v1.canonical(value, field)


def key(value, field):
    return text_key(canonical(value, field))


def vocabulary(values, field):
    return v1.vocabulary([canonical(v, field) for v in values], field)


def normalized_size_name(name, old_size, new_size):
    # Only a standalone suffix matching the previous size; never a model code.
    if old_size and old_size != new_size:
        suffix = ' ' + old_size.strip()
        if name and name.casefold().endswith(suffix.casefold()):
            return name[:-len(suffix)] + ' ' + new_size
    return name
