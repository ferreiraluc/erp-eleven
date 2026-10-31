"""Conservative shipping identity from explicit links and immutable freight data.

These helpers never create customers, move financial accounts or infer a sale.
"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from ..models.cliente import Cliente
from ..models.pdv import PdvCliente
from .address_book import resolve_address
from .customer_documents import customer_documents, documents_conflict, input_documents, unique_documents
from .customer_identity import compatible_name, pdv_identity_data
from .customer_shipping_links import canonical_customers


def _canonical_customer(db, key):
    if not key:
        return None
    try:
        key = key if isinstance(key, UUID) else UUID(str(key))
    except (ValueError, TypeError):
        return None
    # Resolve the persisted alias chain after any lock wait, rather than trusting
    # a cached pre-merge Cliente. Do not refresh/erase pending contact enrichment.
    aliases = canonical_customers()
    principal_id = db.execute(select(aliases.c.canonical_id).where(aliases.c.customer_id == key)).scalar_one_or_none()
    return db.get(Cliente, principal_id) if principal_id else None


def _compatible_identity(identities, data):
    documents = unique_documents(document for row in identities for document in customer_documents(row))
    if documents_conflict(documents, input_documents(data)):
        return False
    return not data.get('nome') or any(compatible_name(data['nome'], row.nome) for row in identities)


def address_customer(db, address, *, recipient_data=None):
    """Resolve a direct or PDV owner while preserving the address's exclusive IDs."""
    try:
        address = resolve_address(db, address.id) if address else None
    except HTTPException:
        return None
    if not address:
        return None
    direct = _canonical_customer(db, address.cliente_id)
    account = db.get(PdvCliente, address.pdv_cliente_id) if address.pdv_cliente_id else None
    linked = _canonical_customer(db, account.cadastro_cliente_id) if account else None
    if (address.cliente_id and not direct) or (address.pdv_cliente_id and not account):
        return None
    if account and account.cadastro_cliente_id and not linked:
        return None
    if direct and linked and direct.id != linked.id:
        return None
    customer = direct or linked
    if not customer:
        return None
    aliases = canonical_customers()
    identities = db.query(Cliente).join(aliases, aliases.c.customer_id == Cliente.id).filter(
        aliases.c.canonical_id == customer.id,
    ).all()
    if not _compatible_identity(identities, address.data):
        return None
    if account and documents_conflict(
            unique_documents(document for row in identities for document in customer_documents(row)),
            input_documents(pdv_identity_data(account))):
        return None
    if recipient_data is not None:
        if not _compatible_identity(identities, recipient_data):
            return None
        # Legacy freight has no captured customer ID. Its recipient must not be
        # assigned through a current address/account with a different document,
        # even when the directory customer has no documents to compare against.
        recipient_documents = input_documents(recipient_data)
        if documents_conflict(input_documents(address.data), recipient_documents):
            return None
        if account and documents_conflict(input_documents(pdv_identity_data(account)), recipient_documents):
            return None
    return customer


def freight_customer(db, freight):
    """An explicit null snapshot stays unresolved; legacy rows use explicit links."""
    payload = freight.payload or {}
    if '_customer_id' in payload:
        return _canonical_customer(db, payload['_customer_id'])
    from ..models.address_book import SavedAddress
    address = db.get(SavedAddress, freight.address_id) if freight.address_id else None
    recipient = payload.get('to') or {}
    return address_customer(db, address, recipient_data={
        'nome': recipient.get('name'), 'cpf': recipient.get('document'), 'pais': 'BR',
    })
