"""Typed identity documents. Numbers in different namespaces are unrelated."""
import re
import unicodedata


DOCUMENT_COUNTRIES = {'CPF': 'BR', 'CNPJ': 'BR', 'RG': 'BR', 'CI': 'PY', 'RUC': 'PY'}


def normalized_number(value):
    value = unicodedata.normalize('NFKD', str(value or '')).upper()
    return ''.join(char for char in value if char.isascii() and char.isalnum())


def normalize_document(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump()
    if not isinstance(value, dict):
        return None
    kind = str(value.get('tipo') or '').strip().upper()
    country = str(value.get('pais') or '').strip().upper()
    number = normalized_number(value.get('numero'))
    issuer = normalized_number(value.get('emissor'))
    if kind not in DOCUMENT_COUNTRIES or country != DOCUMENT_COUNTRIES[kind]:
        return None
    if not 3 <= len(number) <= 24:
        return None
    if kind in {'CPF', 'CNPJ'} and (not number.isdigit() or
            len(number) != (11 if kind == 'CPF' else 14) or len(set(number)) == 1):
        return None
    document = {'tipo': kind, 'pais': country, 'numero': number}
    if issuer:
        document['emissor'] = issuer[:20]
    return document


def legacy_document(value, country='BR'):
    """Only the legacy Brazilian CPF field has an established namespace."""
    number = re.sub(r'\D', '', str(value or ''))
    if country != 'BR' or len(number) not in (11, 14):
        return None
    return normalize_document({'tipo': 'CPF' if len(number) == 11 else 'CNPJ',
                               'pais': 'BR', 'numero': number})


def document_identity(document):
    return document['pais'], document['tipo'], document.get('emissor', ''), document['numero']


def unique_documents(values):
    found = {}
    for value in values:
        document = normalize_document(value)
        if document:
            found[document_identity(document)] = document
    return list(found.values())


def customer_documents(customer):
    values = list(getattr(customer, 'documentos', None) or [])
    legacy = legacy_document(getattr(customer, 'cpf', None))
    if legacy:
        values.append(legacy)
    return unique_documents(values)


def input_documents(data):
    values = list(data.get('documentos') or [])
    kind = data.get('documento_tipo') or data.get('doc_tipo')
    if kind:
        values.append({'tipo': kind, 'pais': data.get('doc_pais') or data.get('pais') or
                       DOCUMENT_COUNTRIES.get(kind), 'numero': data.get('doc') or data.get('cpf'),
                       'emissor': data.get('documento_emissor')})
    elif 'cpf' in data:
        legacy = legacy_document(data.get('cpf'), data.get('pais', 'BR'))
        if legacy:
            values.append(legacy)
    return unique_documents(values)


def documents_overlap(before, after):
    usable = lambda doc: doc['tipo'] != 'RG' or bool(doc.get('emissor'))
    return bool({document_identity(doc) for doc in before if usable(doc)} &
                {document_identity(doc) for doc in after if usable(doc)})


def documents_conflict(before, after):
    """A changed known number in one namespace requires explicit review."""
    namespaces = lambda docs: {(d['pais'], d['tipo'], d.get('emissor', '')) for d in docs}
    for namespace in namespaces(before) & namespaces(after):
        values = lambda docs: {d['numero'] for d in docs
            if (d['pais'], d['tipo'], d.get('emissor', '')) == namespace}
        if values(before).isdisjoint(values(after)):
            return True
    return False
