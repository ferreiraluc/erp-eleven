"""Strict comparison of structured Brazilian addresses with labeled free text.

This only supplements existing identity evidence. Unknown fragments and missing
unit numbers fail closed, so a city, postal code or similar name cannot merge people.
"""
import re
import unicodedata


def _key(value):
    raw = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(
        char for char in raw if not unicodedata.combining(char))).split())


_STATES = dict(zip(
    ('acre|alagoas|amapa|amazonas|bahia|ceara|distrito federal|espirito santo|goias|maranhao|'
     'mato grosso|mato grosso do sul|minas gerais|para|paraiba|parana|pernambuco|piaui|'
     'rio de janeiro|rio grande do norte|rio grande do sul|rondonia|roraima|santa catarina|'
     'sao paulo|sergipe|tocantins').split('|'),
    'ac al ap am ba ce df es go ma mt ms mg pa pb pr pe pi rj rn rs ro rr sc sp se to'.split()))


def _street(value):
    key = re.sub(r'^(?:endereco|logradouro|direccion)\s+', '', _key(value))
    key = re.sub(r'^av\s+', 'avenida ', key)
    return re.sub(r'^r\s+', 'rua ', key)


def _unit(value):
    return re.sub(r'\b(?:apto|apt|ap)\s+(?=\d)', 'apartamento ', _key(value))


def same_structured_address(free_text, data, known_name):
    """Require street + house + CEP and all supplied unit/location details."""
    if _key(data.get('pais') or 'BR') not in {'br', 'brasil', 'brazil'}:
        return False
    street, number = _street(data.get('endereco')), _key(data.get('numero'))
    cep = re.sub(r'\D', '', str(data.get('cep') or ''))
    if not re.match(r'^(?:rua|avenida|alameda|travessa|estrada|rodovia)\s+\S', street):
        return False
    if not re.fullmatch(r'\d+[a-z]?', number) or len(cep) != 8 or len(set(cep)) == 1:
        return False
    expected = {
        'bairro': _key(data.get('bairro')), 'cidade': _key(data.get('cidade')),
        'estado': _key(data.get('estado')), 'complemento': _unit(data.get('complemento')),
    }
    expected['estado'] = _STATES.get(expected['estado'], expected['estado'])
    seen = set()
    text = re.sub(r'(?<!\d)(\d{5})[-\s]+(\d{3})(?!\d)', r'\1\2', str(free_text or ''))
    for fragment in re.split(r'[,;\n\r]', text):
        value = _key(fragment)
        if not value:
            continue
        if value == _key(known_name) or value in {'br', 'brasil', 'brazil'}:
            continue
        if _street(value) == street:
            seen.add('street')
            continue
        if _street(value) in {f'{street} {number}', f'{street} numero {number}', f'{street} n {number}'}:
            seen.update(('street', 'number'))
            continue
        if re.sub(r'^(?:numero|nro|n)\s+', '', value) == number:
            seen.add('number')
            continue
        if re.sub(r'^cep\s+', '', value).replace(' ', '') == cep:
            seen.add('cep')
            continue
        recognized = False
        for field, wanted in expected.items():
            supplied = re.sub(rf'^{field}\s+', '', value)
            if field == 'estado':
                supplied = re.sub(r'^uf\s+', '', supplied)
                supplied = _STATES.get(supplied, supplied)
            if field == 'complemento':
                supplied = _unit(supplied)
            if wanted and supplied == wanted:
                seen.add(field)
                recognized = True
                break
        if not recognized:
            return False
    required = {'street', 'number', 'cep'}
    if expected['complemento']:
        required.add('complemento')
    return required.issubset(seen)
