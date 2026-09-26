"""Stable address identity shared by imports, the bot, the editor and migrations."""
import hashlib
import json
import re
import unicodedata


def normalized(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold()) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^\w\s]', ' ', value).split())


def digits(value):
    return re.sub(r'\D', '', str(value or ''))


def fingerprint(data):
    country = normalized(data.get('pais'))
    name = normalized(data.get('nome'))
    street = normalized(' '.join(str(data.get(k) or '') for k in ('endereco','numero','bairro','complemento')))
    street = re.sub(r'\b(?:apartamento|apto|apt|ap)\s+(?=[0-9])', 'apartamento ', street)
    city, state, postcode = normalized(data.get('cidade')), normalized(data.get('estado')), digits(data.get('cep'))
    # In Paraguay a city/telephone can be the entire delivery address. Blank or
    # name-only print blocks must never become a shared address for unrelated jobs.
    phone = digits(data.get('telefone')) if not street else ''
    if not name or not any((street, city, postcode, phone)):
        return None
    identity = [country,name,street,city,state,postcode,phone]
    return hashlib.sha256(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def print_matches_saved(printed, saved):
    """A BR print block may omit the district, but never the delivery location.

    Compare the actual street/number/complement as well as name, city and CEP.
    The caller must require a unique candidate; a name alone is never enough.
    """
    if normalized(printed.get('pais')) != 'br' or normalized(saved.get('pais')) != 'br':
        return False
    for key in ('nome', 'cidade', 'estado'):
        if not normalized(printed.get(key)) or normalized(printed.get(key)) != normalized(saved.get(key)):
            return False
    if not digits(printed.get('cep')) or digits(printed.get('cep')) != digits(saved.get('cep')):
        return False
    def street(data, district=True):
        keys = ('endereco', 'numero', 'bairro', 'complemento') if district else ('endereco', 'numero', 'complemento')
        value = normalized(' '.join(str(data.get(k) or '') for k in keys))
        return re.sub(r'\b(?:apartamento|apto|apt|ap)\s+(?=[0-9])', 'apartamento ', value)
    printed_street = street(printed)
    if not printed_street or not any(c.isdigit() for c in printed_street):
        return False
    return printed_street == street(saved) or (
        not printed.get('bairro') and printed_street == street(saved, district=False))
