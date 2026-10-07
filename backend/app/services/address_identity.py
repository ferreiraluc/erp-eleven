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


def matches_optional_district(left, right):
    """A missing district can be enriched when a complete BR location agrees."""
    if normalized(left.get('bairro')) and normalized(right.get('bairro')):
        return False
    if len(digits(left.get('cep'))) != 8 or len(digits(right.get('cep'))) != 8:
        return False
    return print_matches_saved(left, right) or print_matches_saved(right, left)


def matches_known_variants(left, right):
    """Recognize limited BR spelling variants without changing stored identities.

    An avenue abbreviation or optional Jardim prefix is only evidence when the
    complete recipient/location/CEP agrees. Callers must reject multiple matches
    and separately validate documents and customer links.
    """
    if normalized(left.get('pais')) != 'br' or normalized(right.get('pais')) != 'br':
        return False
    for key in ('nome', 'cidade', 'estado'):
        if not normalized(left.get(key)) or normalized(left.get(key)) != normalized(right.get(key)):
            return False
    postcode = digits(left.get('cep'))
    if len(postcode) != 8 or postcode != digits(right.get('cep')):
        return False
    numbers = [normalized(data.get('numero')) for data in (left, right)]
    # A numbered street ("Avenida 25") is not proof of a house number. At least
    # one structured number must anchor this additional equivalence; a legacy
    # print may embed the same number in its street text instead.
    if not any(digits(number) for number in numbers) or (all(numbers) and numbers[0] != numbers[1]):
        return False

    street = _br_location(left, right)
    if not street or not any(char.isdigit() for char in street) or street != _br_location(right, left):
        return False
    before, after = normalized(left.get('bairro')), normalized(right.get('bairro'))
    if before == after:
        return True
    if not before or not after:
        # The existing rule permits an absent district only for one complete
        # location. Avenue spelling must not turn an otherwise equal BR address
        # into a second record when the bot omits its district.
        return True
    core = lambda value: re.sub(r'^(?:jardim|jd)\s+', '', value)
    return bool(core(before)) and core(before) == core(after)


def _br_location(data, reference):
    """Compare fields with a legacy street block without duplicating its suffix.

    Only remove a whole suffix corroborated by a structured field. Never strip
    arbitrary digits (Rua 25), guess a missing apartment or modify saved data.
    """
    def part(value):
        value = normalized(value)
        value = re.sub(r'^(?:av)\s+', 'avenida ', value)
        value = re.sub(r'^r\s+', 'rua ', value)
        return re.sub(r'\b(?:apartamento|apto|apt|ap)\s+(?=[0-9])', 'apartamento ', value)

    street = part(data.get('endereco'))
    if not street:
        return ''
    parts = {}
    for field in ('complemento', 'numero'):
        own = part(data.get(field))
        suffix = own or part(reference.get(field))
        stem = street[:-len(suffix)].strip() if suffix and street.endswith(' ' + suffix) else ''
        if stem and stem not in {'rua', 'avenida', 'travessa', 'estrada', 'rodovia'}:
            street = stem
            parts[field] = suffix
        else:
            parts[field] = own
    return ' '.join(value for value in (street, parts['numero'], parts['complemento']) if value)


def matches_paraguay_phone(left, right):
    """A PY phone's local/DDI spelling does not create another destination."""
    from .customer_identity import full_name, phone_key

    if any(normalized(data.get('pais')) != 'py' for data in (left, right)):
        return False
    if not full_name(left.get('nome')) or not normalized(left.get('cidade')):
        return False
    for field in ('nome', 'endereco', 'numero', 'bairro', 'complemento', 'cidade', 'estado', 'cep'):
        if normalized(left.get(field)) != normalized(right.get(field)):
            return False
    before, after = (data.get('telefone') for data in (left, right))
    if not before or not after:
        return True  # Only a unique otherwise identical destination can be reused.
    phone = phone_key(before, 'PY')
    return bool(phone) and phone == phone_key(after, 'PY')


def equivalent(left, right):
    """Shared location comparison; callers still validate document/customer IDs."""
    key = fingerprint(left)
    return bool(key and key == fingerprint(right)) or matches_optional_district(left, right) or matches_known_variants(left, right) or matches_paraguay_phone(left, right)
