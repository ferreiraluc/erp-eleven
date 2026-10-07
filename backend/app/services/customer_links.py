"""Explicit customer/order/parcel relationships shared by the API and assistant.

This module never commits and never infers a person's identity from a name.
Callers own the transaction and any user-facing confirmation.
"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.cliente import Cliente
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento


def validate_tracking_links(
    db: Session, *, pedido_id: UUID | None, cliente_id: UUID | None,
    allow_inactive_customer: bool = False,
) -> tuple[Pedido | None, Cliente | None]:
    """Validate IDs and inherit the customer of a selected order, if present."""
    pedido = None
    if pedido_id:
        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
        if not pedido:
            raise HTTPException(404, "Pedido não encontrado.")
        if cliente_id and pedido.cliente_id and cliente_id != pedido.cliente_id:
            raise HTTPException(409, "O pedido e o rastreio pertencem a clientes diferentes. Confira os vínculos.")
        cliente_id = cliente_id or pedido.cliente_id
    cliente = db.get(Cliente, cliente_id) if cliente_id else None
    if cliente and cliente.merged_into_id:
        raise HTTPException(409, 'Este cliente foi unificado. Selecione o cadastro principal.')
    if cliente_id and (not cliente or (not cliente.ativo and not allow_inactive_customer)):
        raise HTTPException(404, "Cliente não encontrado ou inativo.")
    return pedido, cliente


def validate_order_customer(db: Session, pedido: Pedido, cliente_id: UUID | None) -> None:
    """Do not silently move a customer's parcels by changing their order."""
    if not cliente_id:
        return
    conflict = db.query(Rastreamento.id).filter(
        Rastreamento.pedido_id == pedido.id,
        Rastreamento.cliente_id.is_not(None), Rastreamento.cliente_id != cliente_id,
    ).first()
    if conflict:
        raise HTTPException(409, "Há pacotes deste pedido vinculados a outro cliente. Revise os vínculos antes de alterar.")


def inherit_order_customer(db: Session, pedido: Pedido) -> None:
    """Fill missing IDs only. Historical recipient/address snapshots are untouched."""
    if not pedido.cliente_id:
        return
    validate_order_customer(db, pedido, pedido.cliente_id)
    for shipment in db.query(Rastreamento).filter(
        Rastreamento.pedido_id == pedido.id, Rastreamento.cliente_id.is_(None),
    ).all():
        shipment.cliente_id = pedido.cliente_id


def customer_shipments(db: Session, cliente_id: UUID):
    """Legacy parcels inherit their explicit order link; equal names never match."""
    return db.query(Rastreamento).outerjoin(Pedido, Pedido.id == Rastreamento.pedido_id).filter(
        or_(Rastreamento.cliente_id == cliente_id,
            (Rastreamento.cliente_id.is_(None)) & (Pedido.cliente_id == cliente_id)),
    )


def lock_tracking_row(db: Session, tracking_id: UUID) -> Rastreamento | None:
    """Consistent lock order: parent order first, then its parcel.

    A concurrent relink requires a fresh user review rather than locking a new
    parent in the opposite order.
    """
    row = db.get(Rastreamento, tracking_id)
    if row is None:
        return None
    expected_order = row.pedido_id
    if expected_order:
        db.query(Pedido.id).filter(Pedido.id == expected_order).with_for_update().first()
    row = db.query(Rastreamento).filter(Rastreamento.id == tracking_id).populate_existing().with_for_update().first()
    if row and row.pedido_id != expected_order:
        raise HTTPException(409, "O vínculo do rastreio mudou. Atualize os dados antes de continuar.")
    return row
