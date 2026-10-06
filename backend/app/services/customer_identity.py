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


def find_customer(db, data):
    name = name_key(data.get('nome'))
    phone = phone_key(data.get('telefone'), data.get('pais'))
    doc = document_key(data.get('cpf'), data.get('pais', 'BR'))
    customers = db.query(Cliente).all()
    named = [c for c in customers if name and name_key(c.nome) == name]
    same_person = lambda c: bool(name and (name_key(c.nome) == name or set(name.split()).issubset(name_key(c.nome).split())))
    documented = [c for c in customers if doc and document_key(c.cpf) == doc]
    if documented and not any(same_person(c) for c in documented):
        return None, 'document_name_conflict', documented
    strong = [c for c in customers if compatible_person(c, data) and (
        (doc and document_key(c.cpf) == doc and same_person(c)) or
        (phone and phone_key(c.telefone) == phone and name and
         (name_key(c.nome) == name or set(name.split()).issubset(name_key(c.nome).split()))))]
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


def match_recipient(db, name, phone=None, email=None):
    customer, reason, _ = find_customer(db, {'nome': name, 'telefone': phone, 'email': email})
    return customer if customer and customer.ativo else None
