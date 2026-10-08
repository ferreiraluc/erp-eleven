"""Versioned, conservative inventory vocabulary. Keep v1 stable for its migration."""
import re
import unicodedata

FIELDS = ('brand', 'category', 'color')


def text_key(value):
    value = unicodedata.normalize('NFKD', value or '')
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).casefold().split())


LABELS = {
    'brand': {'prada': 'Prada', 'emporio armani': 'Emporio Armani',
              'ea7 emporio armani': 'Emporio Armani', 'ea7': 'EA7', 'h&m': 'H&M',
              'dkny': 'DKNY', 'ck': 'CK', 'boss': 'Boss'},
    'category': {'calcados': 'Calçados', 'tenis': 'Tênis', 'acessorios': 'Acessórios',
                 'calcas': 'Calças', 'bones': 'Bonés', 'oculos': 'Óculos'},
    'color': {'bege': 'Bege', 'marrom': 'Marrom'},
}


def canonical(value, field):
    if value is None:
        return None
    clean = ' '.join(value.split())
    if field == 'category':
        return ' > '.join(LABELS[field].get(text_key(part), part.strip().title())
                          for part in re.split(r'\s*>\s*', clean) if part.strip())
    return LABELS.get(field, {}).get(text_key(clean), clean.title())


def key(value, field):
    return text_key(canonical(value, field))


def vocabulary(values, field):
    """One deterministic display label, preferring existing accented spellings."""
    result = {}
    for value in sorted({canonical(v, field) for v in values if v and v.strip()}):
        identity = key(value, field)
        old = result.get(identity)
        score = lambda s: sum(bool(unicodedata.combining(c)) for c in unicodedata.normalize('NFD', s))
        if old is None or score(value) > score(old):
            result[identity] = value
    return result
