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
