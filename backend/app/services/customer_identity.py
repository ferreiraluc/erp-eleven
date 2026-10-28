"""Conservative customer resolution for confirmed address operations.

No fuzzy joins, no overwrite of explicit links, no mutation of historical payloads.
The caller owns the transaction and the shared address lock.
"""
import re
import unicodedata
from ..models.cliente import Cliente
from .user_audit import record


def name_key(value):
    raw = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in raw if not unicodedata.combining(c))).split())


def full_name(value):
    key = name_key(value)
    return len(key.split()) >= 2 and key not in {'consumidor final', 'cliente final', 'sem nome', 'nao informado', 'cliente a identificar'}


def phone_key(value, country=None):
    value = str(value or '').strip()
    if not re.fullmatch(r'[+\d\s().-]+', value): return ''
    digits = re.sub(r'\D', '', value)
    if digits.startswith('00'): digits = digits[2:]
    if country != 'BR' and len(digits) == 10 and digits.startswith('09'): digits = '595' + digits[1:]
    elif country != 'BR' and len(digits) == 9 and digits.startswith('9'): digits = '595' + digits
    elif country != 'PY' and len(digits) in (10, 11): digits = '55' + digits
    return digits if 10 <= len(digits) <= 15 and len(set(digits)) > 1 else ''


def document_key(value, country='BR'):
    if country != 'BR': return ''  # CPF is not interchangeable with RUC/C.I.
    digits = re.sub(r'\D', '', str(value or ''))
    return digits if len(digits) in (11, 14) and len(set(digits)) > 1 else ''


def compatible_person(customer, data):
    doc, old_doc = document_key(data.get('cpf'), data.get('pais', 'BR')), document_key(customer.cpf)
    # Phones can legitimately change. Different known documents establish conflict.
    return not (doc and old_doc and doc != old_doc)


def email_key(value):
    value = str(value or '').strip().casefold()
    return value if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value) else ''


def address_key(value):
    """Full location evidence, never a city/CEP/name alone."""
    key = name_key(value)
    key = re.sub(r'^av\s+', 'avenida ', key)
    key = re.sub(r'^r\s+', 'rua ', key)
    key = re.sub(r'\b(?:apto|apt|ap)\s+(?=[0-9])', 'apartamento ', key)
    parts = [name_key(part) for part in re.split(r'[,;\n]', str(value or '')) if name_key(part)]
    street = parts[0] if parts else ''
    street = re.sub(r'^av\s+', 'avenida ', street)
    street = re.sub(r'^r\s+', 'rua ', street)
    kind = r'(?:rua|avenida|calle|alameda|travessa|estrada|rodovia|ruta|pasaje|callejon|boulevard|carrera)'
    if not re.match(r'^' + kind + r'\s+\S', street):
        return ''
    # The house number must be anchored to the street. Digits in a city name or
    # in the CEP at the end of a free-form block are not delivery-location proof.
    number = r'(?:nro\s+|numero\s+|n\s+)?\d+[a-z]?'
    separate_number = len(parts) > 1 and re.fullmatch(number, parts[1])
    embedded_number = re.match(r'^' + kind + r'\s+.*[a-z].*\s+\d+[a-z]?$', street)
    return key if separate_number or embedded_number else ''


def corroboration(customer, data):
    """Return strong identity evidence without replacing contacts/snapshots."""
    if not compatible_person(customer, data):
        return None
    phone, old_phone = phone_key(data.get('telefone'), data.get('pais')), phone_key(customer.telefone)
    email, old_email = email_key(data.get('email')), email_key(customer.email)
    # An otherwise matching address cannot choose between conflicting identities.
    if (phone and old_phone and phone != old_phone) or (email and old_email and email != old_email):
        return None
    doc = document_key(data.get('cpf'), data.get('pais', 'BR'))
    if doc and doc == document_key(customer.cpf):
        return 'document'
    if phone and phone == old_phone:
        return 'name_phone'
    if email and email == old_email:
        return 'name_email'
    location = address_key(data.get('endereco_livre') or address_text(data)) if (
        data.get('endereco_livre') or data.get('endereco')) else ''
    if location and location == address_key(customer.endereco):
        return 'name_address'
    return None


def find_customer(db, data, *, customers=None):
    name = name_key(data.get('nome'))
    phone = phone_key(data.get('telefone'), data.get('pais'))
    doc = document_key(data.get('cpf'), data.get('pais', 'BR'))
    customers = db.query(Cliente).populate_existing().all() if customers is None else customers
    by_id = {c.id: c for c in customers}
    names = {c.id: {name_key(c.nome)} for c in customers if not c.merged_into_id}
    # Only explicitly consolidated aliases can supply another known name. Old
    # contacts/documents do not override the identity chosen for the principal.
    for alias in customers:
        row, seen = alias, set()
        while row and row.merged_into_id and row.id not in seen:
            seen.add(row.id)
            row = by_id.get(row.merged_into_id)
        if row and row.id in names:
            names[row.id].add(name_key(alias.nome))
    customers = [c for c in customers if not c.merged_into_id]
    named = [c for c in customers if name and name in names[c.id]]
    same_person = lambda c: bool(name and any(set(name.split()).issubset(n.split()) for n in names[c.id]))
    documented = [c for c in customers if doc and document_key(c.cpf) == doc]
    if documented and not any(same_person(c) for c in documented):
        return None, 'document_name_conflict', documented
    corroborated = [(c, corroboration(c, data)) for c in named if full_name(name)]
    corroborated = [(c, reason) for c, reason in corroborated if reason]
    if len(corroborated) == 1:
        return corroborated[0][0], corroborated[0][1], []
    if len(corroborated) > 1:
        return None, 'ambiguous', [c for c, _ in corroborated]
    strong = [c for c in customers if compatible_person(c, data) and (
        (doc and document_key(c.cpf) == doc and same_person(c)) or
        (phone and phone_key(c.telefone) == phone and same_person(c)))]
    if len(strong) == 1:
        return strong[0], 'document' if doc and document_key(strong[0].cpf) == doc else 'name_phone', []
    if len(strong) > 1: return None, 'ambiguous', strong
    if (len(named) == 1 and full_name(name) and compatible_person(named[0], data)
            and not (phone and phone_key(named[0].telefone) and phone != phone_key(named[0].telefone))):
        return named[0], 'unique_full_name', []
    if named: return None, 'conflicting_or_short_name', named
    return None, 'new_customer' if name else 'missing_name', []


def address_text(data):
    return ', '.join(str(data.get(k) or '').strip() for k in
                     ('endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep', 'pais') if data.get(k))


def ensure_customer(db, row):
    """Every new address belongs to a customer; ambiguous identities stay separate."""
    if row.cliente_id or row.pdv_cliente_id:
        return False
    data = row.data
    customer, reason, candidates = find_customer(db, data)
    created = customer is None
    if customer is None:
        doc = document_key(data.get('cpf'), data.get('pais', 'BR'))
        # A conflicting existing document stays only in the address for review.
        if doc and any(document_key(c.cpf) == doc for c in db.query(Cliente)):
            doc = None
        customer = Cliente(nome=data.get('nome') or 'Cliente a identificar',
                           telefone=phone_key(data.get('telefone'), data.get('pais')) or None,
                           email=data.get('email') or None, cpf=doc or None,
                           endereco=address_text(data) or None, ativo=True)
        db.add(customer); db.flush()
    else:
        # Do not rewrite existing contact details or reactivate archived customers.
        if not customer.telefone: customer.telefone = phone_key(data.get('telefone'), data.get('pais')) or None
        if not customer.email: customer.email = data.get('email') or None
        if not customer.endereco: customer.endereco = address_text(data) or None
    row.cliente_id = customer.id
    row.customer_link_review = bool(candidates) or (created and not full_name(data.get('nome'))) or not customer.ativo
    row.customer_link_reason = reason
    db.flush()
    if db.info.get('audit_actor'):
        record(db, 'customer_auto_created' if created else 'customer_auto_linked', 'clientes',
               entity='saved_addresses', entity_id=str(row.id),
               changes={'cliente_id': str(customer.id), 'reason': reason, 'review': row.customer_link_review})
    return True


def match_recipient(db, name, phone=None, email=None, *, address=None, customers=None):
    customer, reason, _ = find_customer(db, {'nome': name, 'telefone': phone, 'email': email,
        'endereco_livre': address}, customers=customers)
    return customer if customer and customer.ativo else None
