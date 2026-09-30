"""On-demand Brazilian postcode lookup. Only the CEP leaves the ERP."""
import re
import time
from collections import OrderedDict
from threading import Lock

import requests
from pydantic import BaseModel, ConfigDict, Field

from .address_identity import normalized

FIELDS = {'endereco': 'logradouro', 'bairro': 'bairro', 'cidade': 'localidade', 'estado': 'uf'}
LABELS = {'endereco': 'rua', 'bairro': 'bairro', 'cidade': 'cidade', 'estado': 'UF'}
_cache = OrderedDict()
_lock = Lock()


class CepArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cep: str = Field(min_length=8, max_length=15)


def lookup_cep(value):
    cep = re.sub(r'[-\s]', '', str(value or ''))
    if not re.fullmatch(r'[0-9]{8}', cep):
        return {'status': 'invalid', 'aviso': 'Informe um CEP com 8 dígitos.'}
    now = time.monotonic()
    with _lock:
        cached = _cache.get(cep)
        if cached and cached[0] > now:
            _cache.move_to_end(cep)
            return {**cached[1], 'data': dict(cached[1].get('data', {}))}
    try:
        with requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=(2, 4), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError('Unavailable')
            body = response.json()
        if not isinstance(body, dict):
            raise ValueError('Invalid response')
        if body.get('erro'):
            result = {'status': 'not_found', 'aviso': 'CEP não encontrado na consulta. Confira os 8 dígitos.'}
        else:
            data = {key: str(body.get(source) or '').strip() for key, source in FIELDS.items()}
            if re.sub(r'\D', '', str(body.get('cep', ''))) != cep or not data['cidade'] or not re.fullmatch(r'[A-Z]{2}', data['estado']):
                raise ValueError('Incomplete response')
            # Ignore provider complement: it describes a CEP segment, not an apartment.
            data['endereco'] = re.split(r'\s+-\s+(?=(?:de |até |ate |lado |todos|ao fim))', data['endereco'], flags=re.I)[0]
            result = {'status': 'found', 'source': 'ViaCEP', 'data': {'cep': cep[:5] + '-' + cep[5:], **data}}
    except (requests.RequestException, ValueError, TypeError):
        result = {'status': 'unavailable', 'aviso': 'Consulta de CEP indisponível. Confira os dados informados; tente consultar novamente depois.'}
    ttl = 30 if result['status'] == 'unavailable' else 3600 if result['status'] == 'not_found' else 86400
    with _lock:
        _cache[cep] = (now + ttl, result)
        _cache.move_to_end(cep)
        while len(_cache) > 512:
            _cache.popitem(last=False)
    return {**result, 'data': dict(result.get('data', {}))}


def comparable(value):
    aliases = {'r': 'rua', 'av': 'avenida', 'trav': 'travessa', 'tv': 'travessa', 'jd': 'jardim', 'dr': 'doutor', 'prof': 'professor'}
    return ' '.join(aliases.get(word, word) for word in normalized(value).split())


def agrees(field, supplied, official):
    left, right = comparable(supplied), comparable(official)
    if left == right:
        return True
    # Older print blocks embed the house number/district in the street string.
    return field == 'endereco' and bool(re.match(r'^' + re.escape(right) + r'\s+(?:\d|s n\b|sem numero\b)', left))


def complete_address(data):
    data = dict(data)
    result = {'data': data, 'status': 'skipped', 'filled': [], 'conflicts': [], 'warnings': []}
    if data.get('pais') != 'BR' or not data.get('cep'):
        return result
    lookup = lookup_cep(data['cep'])
    result['status'] = lookup['status']
    if lookup['status'] != 'found':
        result['warnings'] = [lookup['aviso']]
        return result
    official = lookup['data']
    result['suggestion'] = official
    for key in FIELDS:
        if official.get(key) and data.get(key) and not agrees(key, data[key], official[key]):
            result['conflicts'].append({'field': key, 'provided': data[key], 'suggested': official[key]})
            result['warnings'].append(f"CEP {official['cep']}: {LABELS[key]} informada ‘{data[key]}’; ViaCEP retorna ‘{official[key]}’. Confira antes de confirmar.")
    # Never construct a mixed location from two conflicting addresses.
    if not result['conflicts']:
        for key in FIELDS:
            if not data.get(key) and official.get(key):
                data[key] = official[key]
                result['filled'].append(key)
        data['cep'] = official['cep']
    return result


def street_line(data):
    line = str(data.get('endereco') or '')
    for key in ('numero', 'bairro', 'complemento'):
        value = str(data.get(key) or '')
        if value and not re.search(r'(?<!\w)' + re.escape(normalized(value)) + r'(?!\w)', normalized(line)):
            line = ', '.join(part for part in (line, value) if part)
    return line
