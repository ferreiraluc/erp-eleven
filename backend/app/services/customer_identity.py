"""Conservative customer resolution for confirmed address operations.

No fuzzy joins, no overwrite of explicit links, no mutation of historical payloads.
The caller owns the transaction and the shared address lock.
"""
import re
import unicodedata
from ..models.cliente import Cliente
from .user_audit import record
from .customer_documents import (customer_documents, input_documents, documents_overlap,
                                 documents_conflict, unique_documents, legacy_document)


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


def document_conflicts(customer, data):
    return documents_conflict(customer_documents(customer), input_documents(data))


def compatible_person(customer, data):
    return not document_conflicts(customer, data)


def email_key(value):
    value = str(value or '').strip().casefold()
    return value if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value) else ''


def address_key(value):
    """Full location evidence, never a city/CEP/name alone."""
    value = re.sub(r'(?<!\d)(\d{5})[-\s]+(\d{3})(?!\d)', r'\1\2', str(value or ''))
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


def corroboration(customer, data, *, documents=None):
    """Return corroborated evidence; surname, street or postal code alone is insufficient."""
    before = customer_documents(customer) if documents is None else documents
    after = input_documents(data)
    if documents_conflict(before, after):
        return None
    if documents_overlap(before, after):
        return 'document'
    phone, old_phone = phone_key(data.get('telefone'), data.get('pais')), phone_key(customer.telefone)
    email, old_email = email_key(data.get('email')), email_key(customer.email)
    if (phone and old_phone and phone != old_phone) or (email and old_email and email != old_email):
        return None
    if phone and phone == old_phone:
        return 'name_phone'
    if email and email == old_email:
        return 'name_email'
    location = address_key(data.get('endereco_livre') or address_text(data)) if (
        data.get('endereco_livre') or data.get('endereco')) else ''
    if location and location == address_key(customer.endereco):
        return 'name_address'
    return None


def compatible_name(incoming, known):
    left, right = name_key(incoming).split(), name_key(known).split()
    if not full_name(incoming) or not full_name(known):
        return False
    # Extra middle names may be absent. A shared surname alone cannot choose a person.
    return left == right or (left[0] == right[0] and left[-1] == right[-1] and
                             (set(left).issubset(right) or set(right).issubset(left)))


def customer_identity_groups(customers):
    by_id = {customer.id: customer for customer in customers}
    roots = {customer.id: customer for customer in customers if not customer.merged_into_id}
    groups = {key: [customer] for key, customer in roots.items()}
    for alias in customers:
        row, seen = alias, set()
        while row and row.merged_into_id and row.id not in seen:
            seen.add(row.id)
            row = by_id.get(row.merged_into_id)
        if alias.merged_into_id and row and row.id in groups:
            groups[row.id].append(alias)
    return roots, groups


def find_customer(db, data, *, customers=None, exclude_id=None):
    name = name_key(data.get('nome'))
    after = input_documents(data)
    customers = db.query(Cliente).populate_existing().all() if customers is None else customers
    roots, groups = customer_identity_groups(customers)
    if exclude_id is not None:
        roots.pop(exclude_id, None)
    names = {key: {name_key(row.nome) for row in groups[key]} for key in roots}
    documents = {key: unique_documents(doc for row in groups[key] for doc in customer_documents(row)) for key in roots}
    compatible_names = {key for key in roots if any(compatible_name(name, known) for known in names[key])}
    named = [customer for key, customer in roots.items() if name and name in names[key]]
    documented = [customer for key, customer in roots.items() if documents_overlap(documents[key], after)]
    # Typed documents are preserved on historical aliases and are not a unique
    # database column. A number shared by two unconfirmed principals (or a payload
    # combining one person's CI with another's RUC) cannot silently choose one by
    # name. Confirmed aliases have already collapsed into a single root above.
    if len(documented) > 1:
        return None, 'ambiguous', documented
    if documented and documented[0].id not in compatible_names:
        return None, 'document_name_conflict', documented
    corroborated = []
    for key in compatible_names:
        customer = roots[key]
        # Contacts and addresses on confirmed aliases remain valid identity evidence,
        # without replacing the principal's current details or historic snapshots.
        reasons = [corroboration(row, data, documents=documents[key]) for row in groups[key]]
        reason = next((value for value in reasons if value), None)
        if reason:
            corroborated.append((customer, reason))
    if len(corroborated) == 1:
        return corroborated[0][0], corroborated[0][1], []
    if len(corroborated) > 1:
        return None, 'ambiguous', [customer for customer, _ in corroborated]
    if named or compatible_names:
        return None, 'conflicting_or_unconfirmed_name', named or [roots[key] for key in compatible_names]
    return None, 'new_customer' if full_name(name) else 'missing_or_short_name', []


def address_text(data):
    return ', '.join(str(data.get(k) or '').strip() for k in
                     ('endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep', 'pais') if data.get(k))


def enrich_customer_documents(customer, data):
    before, after = customer_documents(customer), input_documents(data)
    if documents_conflict(before, after):
        return False
    merged = unique_documents([*(getattr(customer, 'documentos', None) or []), *after])
    if merged != (customer.documentos or []):
        customer.documentos = merged
        return True
    return False


def ensure_customer(db, row):
    """Resolve confirmed address input without creating a permanent ambiguous person."""
    if row.cliente_id:
        customer = db.get(Cliente, row.cliente_id)
        if customer:
            if document_conflicts(customer, row.data):
                changed = not row.customer_link_review or row.customer_link_reason != 'document_conflict'
                row.customer_link_review = True
                row.customer_link_reason = 'document_conflict'
                return changed
            enrich_customer_documents(customer, row.data)
        return False
    if row.pdv_cliente_id:
        from ..models.pdv import PdvCliente
        account = db.get(PdvCliente, row.pdv_cliente_id)
        if account:
            ensure_pdv_customer(db, account)
        return False
    data = row.data
    customer, reason, candidates = find_customer(db, data)
    created = False
    if customer is None and (candidates or not full_name(data.get('nome'))):
        changed = not row.customer_link_review or row.customer_link_reason != reason
        row.customer_link_review = True
        row.customer_link_reason = reason
        db.flush()
        return changed
    if customer is None:
        legacy = legacy_document(data.get('cpf'), data.get('pais', 'BR')) if not data.get('documento_tipo') or data.get('documento_tipo') in {'CPF', 'CNPJ'} else None
        customer = Cliente(nome=data['nome'], telefone=phone_key(data.get('telefone'), data.get('pais')) or None,
            email=data.get('email') or None, cpf=legacy['numero'] if legacy else None,
            documentos=input_documents(data), endereco=address_text(data) or None, ativo=True)
        db.add(customer)
        db.flush()
        created = True
    else:
        if not customer.telefone:
            customer.telefone = phone_key(data.get('telefone'), data.get('pais')) or None
        if not customer.email:
            customer.email = data.get('email') or None
        if not customer.endereco:
            customer.endereco = address_text(data) or None
        enrich_customer_documents(customer, data)
    row.cliente_id = customer.id
    row.customer_link_review = not customer.ativo
    row.customer_link_reason = reason
    db.flush()
    if db.info.get('audit_actor'):
        record(db, 'customer_auto_created' if created else 'customer_auto_linked', 'clientes',
            entity='saved_addresses', entity_id=str(row.id), changes={'cliente_id': str(customer.id),
                'reason': reason, 'review': row.customer_link_review})
    return True


def pdv_identity_data(row):
    return {'nome': row.nome, 'telefone': row.telefone, 'email': row.email,
            'doc': row.doc, 'doc_tipo': row.doc_tipo, 'doc_pais': row.doc_pais}


def ensure_pdv_customer(db, row):
    """Add the canonical directory link; never merge PDV accounts, sales or credit."""
    if row.cadastro_cliente_id:
        customer = db.get(Cliente, row.cadastro_cliente_id)
        return bool(customer and enrich_customer_documents(customer, pdv_identity_data(row)))
    if not row.ativo or not full_name(row.nome):
        return False
    from .address_book import lock_addresses
    lock_addresses(db)
    data = pdv_identity_data(row)
    customer, reason, candidates = find_customer(db, data)
    if customer is None and candidates:
        return False
    created = customer is None
    if customer is None:
        documents = input_documents(data)
        legacy = next((doc['numero'] for doc in documents if doc['tipo'] in {'CPF', 'CNPJ'}), None)
        customer = Cliente(nome=row.nome, telefone=row.telefone, email=row.email,
            cpf=legacy, documentos=documents, ativo=True)
        db.add(customer)
        db.flush()
    if not customer.ativo:
        return False
    enrich_customer_documents(customer, data)
    row.cadastro_cliente_id = customer.id
    if db.info.get('audit_actor'):
        record(db, 'customer_auto_created' if created else 'pdv_customer_auto_linked', 'clientes',
            entity='pdv_clientes', entity_id=str(row.id), changes={'cadastro_cliente_id': str(customer.id), 'reason': reason})
    return True


def match_recipient(db, name, phone=None, email=None, *, address=None, customers=None):
    customer, reason, _ = find_customer(db, {'nome': name, 'telefone': phone, 'email': email,
        'endereco_livre': address}, customers=customers)
    return customer if customer and customer.ativo else None
