"""One reusable address, with immutable freight/print records for every use."""
from fastapi import HTTPException
from sqlalchemy import text
from ..models.address_book import SavedAddress
from ..models.assistant import utcnow
from .address_identity import fingerprint, digits


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
    before, after = digits(row.data.get('cpf')), digits(data.get('cpf'))
    if before and after and len(set(before))>1 and len(set(after))>1 and before!=after:
        raise HTTPException(409,'Já existe esse destinatário e endereço com outro CPF/CNPJ. Confira o documento no cadastro antes de continuar.')
    linked = (row.cliente_id, row.pdv_cliente_id)
    incoming = (cliente_id,pdv_cliente_id)
    if any(linked) and any(incoming) and linked != incoming:
        raise HTTPException(409,'Esse endereço já está vinculado a outro cadastro de cliente. Confira o vínculo antes de continuar.')


def save_or_reuse(db, data, user_id, *, label=None, cliente_id=None, pdv_cliente_id=None, active=True):
    lock_addresses(db)
    key = fingerprint(data)
    row = db.query(SavedAddress).filter_by(dedup_key=key,merged_into_id=None).with_for_update().first() if key else None
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
        db.flush()
        return row, True
    row=SavedAddress(label=label or data.get('nome') or 'Endereço',data=data,created_by=user_id,
        cliente_id=cliente_id,pdv_cliente_id=pdv_cliente_id,active=active,dedup_key=key)
    db.add(row);db.flush()
    return row, False


def edit_address(db, key, body):
    lock_addresses(db)
    original=db.get(SavedAddress,key)
    if original and original.merged_into_id:
        raise HTTPException(409,'Este endereço foi consolidado. Atualize a agenda antes de editar.')
    row=db.query(SavedAddress).filter_by(id=key).with_for_update().first()
    if not row:raise HTTPException(404,'Endereço não encontrado.')
    if row.version!=body.version:raise HTTPException(409,'Endereço alterado por outra pessoa. Atualize antes de salvar.')
    new_key=fingerprint(body.data.model_dump())
    same=db.query(SavedAddress).filter(SavedAddress.id!=key,SavedAddress.dedup_key==new_key,SavedAddress.merged_into_id.is_(None)).with_for_update().first() if new_key else None
    if same:
        compatible(same,body.data.model_dump(),body.cliente_id,body.pdv_cliente_id)
        # Keep the old ID and its historical links as a redirect, never erase snapshots.
        row.merged_into_id=same.id;row.dedup_key=None;row.active=False;row.version+=1
        db.flush()
        target,_=save_or_reuse(db,body.data.model_dump(),row.created_by,label=body.label,
            cliente_id=body.cliente_id,pdv_cliente_id=body.pdv_cliente_id,active=body.active)
        return target, True
    for attr in ('label','cliente_id','pdv_cliente_id','active'):setattr(row,attr,getattr(body,attr))
    row.data=body.data.model_dump();row.dedup_key=new_key;row.version+=1;row.updated_at=utcnow()
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
