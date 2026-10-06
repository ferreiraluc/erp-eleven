"""One reusable address, with immutable freight/print records for every use."""
from fastapi import HTTPException
from sqlalchemy import text
from ..models.address_book import SavedAddress
from ..models.assistant import utcnow
from .address_identity import fingerprint, digits, matches_optional_district, matches_known_variants


def lock_addresses(db):
    # Consistent lock order also serializes concurrent bot/frontend submissions.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(711005)'))


def resolve_address(db, key):
    row = db.get(SavedAddress,key) if key else None
    seen = set()
    while row and row.merged_into_id:
        if row.id in seen:raise HTTPException(409,'Vínculo de endereço inválido. Confira o cadastro.')
        seen.add(row.id)
        row = db.get(SavedAddress,row.merged_into_id)
    return row


def compatible(row, data, cliente_id=None, pdv_cliente_id=None):
    if str(data.get('pais','')).upper() == 'PY':
        # RUC/C.I may contain letters. Equal numeric parts do not establish
        # the same document, and repeated digits are not Brazilian placeholders.
        document = lambda value: ''.join(c for c in str(value or '').casefold() if c.isalnum())
        before, after = document(row.data.get('cpf')), document(data.get('cpf'))
        if before and after and before != after:
            raise HTTPException(409,'Já existe esse destinatário e endereço com outro RUC/C.I. Confira o documento no cadastro antes de continuar.')
    else:
        before, after = digits(row.data.get('cpf')), digits(data.get('cpf'))
        if before and after and len(set(before))>1 and len(set(after))>1 and before!=after:
            raise HTTPException(409,'Já existe esse destinatário e endereço com outro CPF/CNPJ. Confira o documento no cadastro antes de continuar.')
    linked = (row.cliente_id, row.pdv_cliente_id)
    incoming = (cliente_id,pdv_cliente_id)
    if any(linked) and any(incoming) and linked != incoming:
        raise HTTPException(409,'Esse endereço já está vinculado a outro cadastro de cliente. Confira o vínculo antes de continuar.')


def find_equivalent_address(db, data, exclude_id=None):
    key = fingerprint(data)
    roots = db.query(SavedAddress).filter_by(merged_into_id=None)
    if exclude_id is not None:
        roots = roots.filter(SavedAddress.id != exclude_id)
    row = roots.filter_by(dedup_key=key).with_for_update().first() if key else None
    if row:
        return row
    candidates = [row for row in roots.with_for_update() if (
        matches_optional_district(data, row.data) or matches_known_variants(data, row.data))]
    if len(candidates) > 1:
        raise HTTPException(409, 'Há mais de um endereço compatível. Confira os cadastros na agenda antes de continuar.')
    return candidates[0] if candidates else None


def save_or_reuse(db, data, user_id, *, label=None, cliente_id=None, pdv_cliente_id=None, active=True):
    lock_addresses(db)
    key = fingerprint(data)
    row = find_equivalent_address(db, data)
    if row:
        compatible(row,data,cliente_id,pdv_cliente_id)
        changed = False
        enriched = {**row.data}
        for field,value in data.items():
            if value and not enriched.get(field):enriched[field]=value;changed=True
        if not row.cliente_id and not row.pdv_cliente_id and (cliente_id or pdv_cliente_id):
            row.cliente_id,row.pdv_cliente_id=cliente_id,pdv_cliente_id;changed=True
        if active and not row.active:row.active=True;changed=True
        if changed:
            row.data=enriched;row.version+=1;row.updated_at=utcnow()
        from .customer_identity import ensure_customer
        if ensure_customer(db, row) and not changed:
            row.version += 1; row.updated_at=utcnow()
        db.flush()
        return row, True
    row=SavedAddress(label=label or data.get('nome') or 'Endereço',data=data,created_by=user_id,
        cliente_id=cliente_id,pdv_cliente_id=pdv_cliente_id,active=active,dedup_key=key)
    db.add(row);db.flush()
    from .customer_identity import ensure_customer
    ensure_customer(db, row)
    return row, False


def save_print_address(db, data, user_id):
    """Reuse a fuller saved BR address when the printed block omits its district."""
    return save_or_reuse(db, data, user_id)[0]


def edit_address(db, key, body):
    lock_addresses(db)
    original=db.get(SavedAddress,key)
    if original and original.merged_into_id:
        raise HTTPException(409,'Este endereço foi consolidado. Atualize a agenda antes de editar.')
    row=db.query(SavedAddress).filter_by(id=key).with_for_update().first()
    if not row:raise HTTPException(404,'Endereço não encontrado.')
    if row.version!=body.version:raise HTTPException(409,'Endereço alterado por outra pessoa. Atualize antes de salvar.')
    new_key=fingerprint(body.data.model_dump())
    same=find_equivalent_address(db, body.data.model_dump(), exclude_id=row.id)
    if same:
        compatible(same,body.data.model_dump(),body.cliente_id,body.pdv_cliente_id)
        # Keep the old ID and its historical links as a redirect, never erase snapshots.
        row.merged_into_id=same.id;row.dedup_key=None;row.active=False;row.version+=1
        db.flush()
        target,_=save_or_reuse(db,body.data.model_dump(),row.created_by,label=body.label,
            cliente_id=body.cliente_id,pdv_cliente_id=body.pdv_cliente_id,active=body.active)
        return target, True
    if (body.cliente_id or body.pdv_cliente_id) and (body.customer_link_confirmed or
            (row.cliente_id, row.pdv_cliente_id) != (body.cliente_id, body.pdv_cliente_id)):
        row.customer_link_review=False;row.customer_link_reason='manual'
    for attr in ('label','cliente_id','pdv_cliente_id','active'):setattr(row,attr,getattr(body,attr))
    row.data=body.data.model_dump();row.dedup_key=new_key;row.version+=1;row.updated_at=utcnow()
    from .customer_identity import ensure_customer
    ensure_customer(db, row)
    db.flush()
    return row,False


def address_family(db, row):
    """Include historical aliases even after a later consolidation changes the target."""
    family={row.id}
    frontier={row.id}
    while frontier:
        children={key for key, in db.query(SavedAddress.id).filter(SavedAddress.merged_into_id.in_(frontier))}
        frontier=children-family
        family.update(frontier)
    return family
