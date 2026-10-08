"""Search directory/PDV identities without merging their financial history."""
import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import and_, or_, func

from ..models.cliente import Cliente
from ..models.pdv import PdvCliente
from ..models.address_book import SavedAddress
from .customer_identity import name_key, phone_key
from .user_audit import record


def key(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower())


def normalizer(db):
    if db.bind.dialect.name == 'sqlite':
        # SQLite is supported for local development/tests; PostgreSQL does the
        # same normalization in SQL without requiring an unaccent extension.
        db.connection().connection.driver_connection.create_function('pdv_search_key', 1, key, deterministic=True)
        return func.pdv_search_key
    accents = 'áàâãäéèêëíìîïóòôõöúùûüçñ'
    ascii_letters = 'aaaaaeeeeiiiiooooouuuucn'
    # Translate uppercase too: lower() on a database with C collation only
    # folds ASCII. Matching must not depend on the server locale.
    return lambda value: func.regexp_replace(func.lower(func.translate(func.coalesce(value, ''),
        accents + accents.upper(), ascii_letters * 2)), '[^a-z0-9]', '', 'g')


def search(db, query, limit=20):
    term = key(query)
    if len(term) < 2:
        return {'items': [], 'has_more': False}
    normalize = normalizer(db)
    tokens = name_key(query).split() if not any(c.isdigit() for c in term) else [term]
    phone_terms = {term}
    canonical_phone = phone_key(query)
    if canonical_phone:
        phone_terms.add(canonical_phone)
        if canonical_phone.startswith('595') and len(canonical_phone) == 12:
            phone_terms.add(canonical_phone[3:])
        elif canonical_phone.startswith('55') and len(canonical_phone) in (12, 13):
            phone_terms.add(canonical_phone[2:])
    legacy_cep = normalize(Cliente.endereco).contains(term, autoescape=True) if term.isdigit() and len(term) == 8 else False

    def matches(name, phone, doc):
        # Never interpolate input into SQL or interpret %/_ as wildcards.
        return or_(and_(*(normalize(name).contains(key(t), autoescape=True) for t in tokens)),
                   *(normalize(phone).contains(t, autoescape=True) for t in sorted(phone_terms)),
                   normalize(doc).contains(term, autoescape=True))

    def addresses(customer_id=None, pdv_id=None):
        links = []
        if customer_id is not None: links.append(SavedAddress.cliente_id == customer_id)
        if pdv_id is not None: links.append(SavedAddress.pdv_cliente_id == pdv_id)
        return db.query(SavedAddress).filter(SavedAddress.active.is_(True), SavedAddress.merged_into_id.is_(None),
            SavedAddress.customer_link_review.is_(False), or_(*links))

    def address_match(q):
        return q.filter(or_(normalize(SavedAddress.data['cep'].as_string()).contains(term, autoescape=True),
            matches(SavedAddress.data['nome'].as_string(), SavedAddress.data['telefone'].as_string(),
                    SavedAddress.data['cpf'].as_string()))).exists()

    pdv_query = db.query(PdvCliente).outerjoin(Cliente, Cliente.id == PdvCliente.cadastro_cliente_id).filter(
        PdvCliente.ativo.is_(True), or_(PdvCliente.cadastro_cliente_id.is_(None),
            and_(Cliente.ativo.is_(True), Cliente.merged_into_id.is_(None))),
        or_(matches(PdvCliente.nome, PdvCliente.telefone, PdvCliente.doc),
            matches(Cliente.nome, Cliente.telefone, Cliente.cpf),
            legacy_cep,
            address_match(addresses(PdvCliente.cadastro_cliente_id, PdvCliente.id))))
    # A directory record already linked to PDV appears only as its PDV identity.
    main_query = db.query(Cliente).filter(Cliente.ativo.is_(True), Cliente.merged_into_id.is_(None),
        ~db.query(PdvCliente.id).filter(PdvCliente.cadastro_cliente_id == Cliente.id).exists(),
        or_(matches(Cliente.nome, Cliente.telefone, Cliente.cpf), legacy_cep, address_match(addresses(Cliente.id))))
    rows = [('pdv', c) for c in pdv_query.order_by(PdvCliente.nome, PdvCliente.id).limit(limit + 1)]
    rows += [('cadastro', c) for c in main_query.order_by(Cliente.nome, Cliente.id).limit(limit + 1)]
    rows.sort(key=lambda pair: (key(pair[1].nome) != term, name_key(pair[1].nome), pair[0], str(pair[1].id)))
    selected = rows[:limit]
    pdv_ids = [c.id for source, c in selected if source == 'pdv']
    main_ids = [c.id if source == 'cadastro' else c.cadastro_cliente_id for source, c in selected]
    # Batch address hints instead of one query per result. Only confirmed links
    # may supply another person's telephone/document/postal code for lookup.
    hints = db.query(SavedAddress.cliente_id, SavedAddress.pdv_cliente_id, SavedAddress.data).filter(
        SavedAddress.active.is_(True), SavedAddress.merged_into_id.is_(None), SavedAddress.customer_link_review.is_(False),
        or_(SavedAddress.cliente_id.in_([i for i in main_ids if i]), SavedAddress.pdv_cliente_id.in_(pdv_ids))).all() if selected else []
    items = []
    for source, customer in selected:
        main_id = customer.id if source == 'cadastro' else customer.cadastro_cliente_id
        ceps = sorted({str(data.get('cep')).strip() for cid, pid, data in hints if data.get('cep') and
                       ((main_id and cid == main_id) or (source == 'pdv' and pid == customer.id))})
        items.append({'source': source, 'id': customer.id, 'nome': customer.nome,
                      'doc': customer.cpf if source == 'cadastro' else customer.doc,
                      'telefone': customer.telefone, 'ceps': ceps})
    return {'items': items, 'has_more': len(rows) > limit}


def select(db, selection, user):
    if selection.source == 'pdv':
        customer = db.get(PdvCliente, selection.id)
        if not customer or not customer.ativo:
            raise HTTPException(409, 'Cliente não encontrado ou inativo. Busque novamente.')
        if customer.cadastro_cliente_id:
            main = db.get(Cliente, customer.cadastro_cliente_id)
            if not main or not main.ativo or main.merged_into_id:
                raise HTTPException(409, 'O cadastro do cliente mudou. Busque novamente.')
        return customer
    # Serialize repeated clicks and concurrent salespeople selecting the same
    # directory customer. Merely searching never creates or updates records.
    main = db.query(Cliente).filter(Cliente.id == selection.id).populate_existing().with_for_update().first()
    if not main or not main.ativo or main.merged_into_id:
        raise HTTPException(409, 'O cadastro do cliente mudou. Busque novamente.')
    existing = db.query(PdvCliente).filter(PdvCliente.cadastro_cliente_id == main.id).order_by(PdvCliente.id).all()
    if existing:
        if len(existing) != 1 or not existing[0].ativo:
            raise HTTPException(409, 'Há cadastros PDV distintos ou inativos para este cliente. Selecione o cadastro PDV na busca.')
        return existing[0]
    normalize = normalizer(db)
    identifiers = []
    if main.cpf and len(key(main.cpf)) >= 6: identifiers.append(normalize(PdvCliente.doc) == key(main.cpf))
    # Full telephone only, and always corroborated by the full name below.
    if main.telefone and len(key(main.telefone)) >= 8:
        identifiers.append(normalize(PdvCliente.telefone).in_([key(main.telefone), phone_key(main.telefone)]))
    candidates = db.query(PdvCliente).filter(or_(*identifiers)).order_by(PdvCliente.id).with_for_update().all() if identifiers else []
    if candidates:
        compatible = [c for c in candidates if c.ativo and not c.cadastro_cliente_id and
            name_key(c.nome) == name_key(main.nome) and
            not (c.doc and main.cpf and key(c.doc) != key(main.cpf))]
        if len(candidates) != 1 or len(compatible) != 1:
            raise HTTPException(409, 'Já existe cadastro PDV com esses contatos. Confira e selecione-o na busca antes de vender.')
        customer = compatible[0]
        customer.cadastro_cliente_id = main.id
    else:
        customer = PdvCliente(nome=main.nome, doc=main.cpf, telefone=main.telefone, email=main.email,
                              cadastro_cliente_id=main.id, created_by=user.id)
        db.add(customer)
    db.flush()
    record(db, 'pdv_customer_linked', 'pdv', entity='pdv_clientes', entity_id=str(customer.id),
           changes={'cadastro_cliente_id': str(main.id)})
    return customer
