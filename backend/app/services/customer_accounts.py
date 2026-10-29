"""Reuse recognized checkout accounts without moving sales or credit balances."""
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError

from ..models.cliente import Cliente
from ..models.pdv import PdvCliente
from ..schemas.pdv import PdvClienteCreate
from .address_book import lock_addresses
from .customer_documents import input_documents, documents_overlap
from .customer_identity import (
    compatible_name, corroboration, document_conflicts, ensure_pdv_customer,
    find_customer, full_name, name_key, pdv_identity_data,
)


def _identity(account):
    return SimpleNamespace(nome=account.nome, telefone=account.telefone, email=account.email,
        cpf=None, documentos=input_documents(pdv_identity_data(account)), endereco=None)


def save_account(db, data, user, existing=None):
    lock_addresses(db)
    if existing is not None:
        existing = db.query(PdvCliente).filter(PdvCliente.id == existing.id).populate_existing().with_for_update().first()
        if not existing:
            raise HTTPException(404, 'Cliente não encontrado.')
    effective = {field: getattr(existing, field) for field in (
        'nome', 'doc', 'doc_tipo', 'doc_pais', 'telefone', 'email', 'tipo', 'limite_fiado_gs', 'notas',
    )} if existing else {}
    effective.update(data)
    try:
        # Re-read first, then validate the complete stored identity. A partial
        # namespace patch cannot bypass validation of the retained document.
        validated = PdvClienteCreate.model_validate(effective).model_dump()
    except ValidationError:
        raise HTTPException(422, 'Confira o nome, documento, país e dados da conta do cliente.')
    if 'ativo' in data and not isinstance(data['ativo'], bool):
        raise HTTPException(422, 'Informe uma situação válida para o cliente.')
    if existing:
        changes = {field: validated[field] for field in data if field in validated}
        if 'ativo' in data:
            changes['ativo'] = data['ativo']
        if 'doc_tipo' in data or 'doc_pais' in data:
            changes['doc_pais'] = validated['doc_pais']
    else:
        changes = validated
    effective = validated
    identity_fields = ('nome', 'doc', 'doc_tipo', 'doc_pais', 'telefone', 'email')
    identity_changed = not existing or any(field in changes and changes[field] != getattr(existing, field)
                                           for field in identity_fields)
    identity = {'nome': effective.get('nome'), 'doc': effective.get('doc'),
        'doc_tipo': effective.get('doc_tipo'), 'doc_pais': effective.get('doc_pais'),
        'telefone': effective.get('telefone'), 'email': effective.get('email')}
    if not full_name(identity['nome']):
        raise HTTPException(422, 'Informe o nome completo do cliente antes de cadastrar uma conta.')
    name = name_key(identity['nome'])
    directory, directory_reason, unresolved = find_customer(db, identity)
    if identity_changed and directory_reason in {'ambiguous', 'document_name_conflict'}:
        # A matching checkout account cannot override conflicting canonical
        # documents. The owner must review those identities before reuse; edits
        # to notes/limits on an already selected account remain independent.
        raise HTTPException(409, 'O documento está associado a cadastros diferentes ou a outro nome. Confira e selecione o cliente correto.')
    accounts = db.query(PdvCliente).order_by(PdvCliente.id).populate_existing().all()
    matches, questionable = [], []
    after = input_documents(identity)
    for account in accounts:
        if existing and account.id == existing.id:
            continue
        person = _identity(account)
        compatible = compatible_name(name, name_key(account.nome))
        direct = compatible and corroboration(person, identity)
        same_directory = directory and account.cadastro_cliente_id == directory.id
        if direct or same_directory:
            matches.append(account)
        elif name_key(account.nome) == name or documents_overlap(person.documentos, after):
            questionable.append(account)
    if len(matches) > 1 and identity_changed:
        raise HTTPException(409, 'Há mais de uma conta desse cliente. Selecione a conta existente; os saldos permanecem separados.')
    if matches and identity_changed:
        account = matches[0]
        if existing or not account.ativo:
            raise HTTPException(409, 'Já existe uma conta com essa identidade. Selecione ou revise o cadastro existente.')
        if account.cadastro_cliente_id:
            main = db.get(Cliente, account.cadastro_cliente_id)
            if (not main or main.merged_into_id or not main.ativo or
                    (directory and directory.id != main.id) or
                    (document_conflicts(main, identity) and not directory)):
                raise HTTPException(409, 'A conta possui vínculo com outro cadastro ou identidade conflitante. Confira o cliente principal.')
        ensure_pdv_customer(db, account)
        return account, True
    if (questionable and identity_changed) or (not existing and unresolved):
        raise HTTPException(409, 'Há um cliente com dados semelhantes ou divergentes. Confira e selecione o cadastro existente antes de criar outro.')
    if existing and existing.cadastro_cliente_id:
        main = db.get(Cliente, existing.cadastro_cliente_id)
        if not main or main.merged_into_id or not main.ativo:
            raise HTTPException(409, 'O cadastro principal mudou. Busque novamente o cliente.')
        if ((document_conflicts(main, identity) and not (directory and directory.id == main.id)) or
                (directory and directory.id != main.id)):
            raise HTTPException(409, 'Os dados pertencem a outra identidade. Confira o cliente principal antes de alterar.')
    if existing and unresolved and identity_changed:
        other_people = [person for person in unresolved if person.id != existing.cadastro_cliente_id]
        if other_people:
            raise HTTPException(409, 'O documento ou nome corresponde a outro cliente. Confira a identidade antes de alterar a conta.')
    if existing is None:
        existing = PdvCliente(created_by=user.id, **changes)
        db.add(existing)
        db.flush()
    else:
        for field, value in changes.items():
            setattr(existing, field, value)
    ensure_pdv_customer(db, existing)
    db.flush()
    return existing, False
