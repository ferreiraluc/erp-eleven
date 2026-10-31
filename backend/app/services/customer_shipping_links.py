"""Read explicit shipping owners without inferring identity from names or snapshots."""
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from ..models.address_book import SavedAddress
from ..models.cliente import Cliente
from ..models.pdv import PdvCliente


def canonical_customers():
    """Map principals and every confirmed customer alias to the principal ID."""
    customers = select(
        Cliente.id.label('customer_id'), Cliente.id.label('canonical_id'),
    ).where(Cliente.merged_into_id.is_(None)).cte('shipping_customer_aliases', recursive=True)
    alias = aliased(Cliente)
    return customers.union(select(alias.id, customers.c.canonical_id).join(
        customers, alias.merged_into_id == customers.c.customer_id,
    ))


def address_owners(customer_ids=None):
    """Resolve direct/PDV owners, then include confirmed historical address aliases.

    A direct link and a PDV link may coexist in legacy data only when both resolve
    to the same principal. Conflicting or broken identities remain unattributed.
    Address consolidation is explicit: its principal owns the original usages,
    even when an old address still carries its former customer reference.
    """
    customers = canonical_customers()
    direct = customers.alias('shipping_direct_customer')
    account_customer = customers.alias('shipping_account_customer')
    owner = func.coalesce(direct.c.canonical_id, account_customer.c.canonical_id)
    consistent = and_(
        or_(SavedAddress.cliente_id.is_(None), direct.c.canonical_id.is_not(None)),
        or_(SavedAddress.pdv_cliente_id.is_(None), PdvCliente.id.is_not(None)),
        or_(PdvCliente.cadastro_cliente_id.is_(None), account_customer.c.canonical_id.is_not(None)),
        or_(direct.c.canonical_id.is_(None), account_customer.c.canonical_id.is_(None),
            direct.c.canonical_id == account_customer.c.canonical_id),
    )
    roots = select(
        SavedAddress.id.label('address_id'), owner.label('customer_id'),
    ).outerjoin(direct, direct.c.customer_id == SavedAddress.cliente_id).outerjoin(
        PdvCliente, PdvCliente.id == SavedAddress.pdv_cliente_id,
    ).outerjoin(account_customer, account_customer.c.customer_id == PdvCliente.cadastro_cliente_id).where(
        SavedAddress.merged_into_id.is_(None), owner.is_not(None), consistent,
    )
    if customer_ids is not None:
        roots = roots.where(owner.in_(customer_ids))
    owners = roots.cte('customer_address_owners', recursive=True)
    child = aliased(SavedAddress)
    return owners.union(select(child.id, owners.c.customer_id).join(
        owners, child.merged_into_id == owners.c.address_id,
    ))
