"""Bounded name typo lookup; never fuzzy-match document IDs, codes or addresses."""
from sqlalchemy import and_, false, or_

from .customer_identity import name_key
from .inventory_search import normalizer


def name_tokens(value):
    tokens = list(dict.fromkeys(name_key(value).split()))
    if any(char in value for char in '%_\\') or not tokens or len(tokens) > 8:
        return []
    if not all(token.isalpha() and len(token) <= 30 for token in tokens):
        return []
    return tokens


def word_pattern(token, approximate=False):
    variants = {token}
    if approximate and len(token) >= 4:
        for index in range(len(token)):
            variants.add(token[:index] + token[index + 1:])
            variants.add(token[:index] + '[a-z]' + token[index + 1:])
            if index + 1 < len(token):
                variants.add(token[:index] + token[index:index + 2][::-1] + token[index + 2:])
        for index in range(len(token) + 1):
            variants.add(token[:index] + '[a-z]' + token[index:])
    return '(^|[^a-z0-9])(' + '|'.join(sorted(variants)) + ')([^a-z0-9]|$)'


def name_condition(db, columns, value, *, approximate=False):
    tokens = name_tokens(value)
    if not tokens:
        return false()
    normalize = normalizer(db)
    conditions = []
    for column in columns:
        text = normalize(column)
        if approximate:
            # At most one misspelled component in the entire name. Other tokens
            # must match whole words in this same field, never another person.
            for index, token in enumerate(tokens):
                if len(token) >= 4:
                    conditions.append(and_(*(text.regexp_match(word_pattern(part, position == index))
                                             for position, part in enumerate(tokens))))
        else:
            conditions.append(and_(*(text.regexp_match(word_pattern(token)) for token in tokens)))
    return or_(*conditions) if conditions else false()
