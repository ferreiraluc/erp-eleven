"""Archive a reviewed order list without deleting history or changing stock."""
import hashlib
import hmac
import json

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import load_only

from ..config import settings
from ..models.pedido import Pedido
from ..models.pedido_archive import PedidoArchiveOperation
from .access_policy import is_owner
from .user_audit import bind_actor, record


def _owner(user):
    if not user.ativo or not is_owner(user):
        raise HTTPException(403, 'Somente Lucas pode arquivar a listagem de pedidos.')


def listing_filter(query, listing):
    if listing == 'archived':
        return query.filter(Pedido.archived_at.isnot(None))
    if listing == 'all':
        return query
    return query.filter(Pedido.archived_at.is_(None))


def _rows(db, *, lock=False):
    query = db.query(Pedido).options(load_only(
        Pedido.id, Pedido.numero_pedido, Pedido.cliente_nome, Pedido.commerce_status,
        Pedido.commerce_version, Pedido.updated_at, Pedido.paid_gs,
        Pedido.archived_at, Pedido.archived_by,
    )).filter(Pedido.archived_at.is_(None)).order_by(Pedido.id)
    if lock:
        query = query.populate_existing().with_for_update()
    return query.all()


def _blocked(row):
    # Unknown commercial states must never disappear from the active directory.
    return row.commerce_status not in (None, 'completed', 'cancelled', 'returned') or (
        row.commerce_status in ('cancelled', 'returned') and (row.paid_gs or 0) > 0)


def _summary(row):
    return {key: str(getattr(row, key)) if key == 'id' else getattr(row, key)
            for key in ('id', 'numero_pedido', 'cliente_nome', 'commerce_status')}


def _token(rows):
    states = [(str(row.id), row.updated_at.isoformat() if row.updated_at else None,
               row.commerce_version, row.commerce_status, str(row.paid_gs)) for row in rows]
    snapshot = json.dumps(states, separators=(',', ':'), ensure_ascii=True).encode()
    return hmac.new(settings.SECRET_KEY.encode(), b'order-archive-v1:' + snapshot, hashlib.sha256).hexdigest()


def preview(db, user):
    _owner(user)
    rows = _rows(db)
    blockers = [row for row in rows if _blocked(row)]
    return {'total': len(rows), 'eligible_count': len(rows) - len(blockers),
            'blocked_count': len(blockers), 'allowed': not blockers,
            'plan_token': _token(rows), 'sample': [_summary(row) for row in rows[:50]],
            'blockers': [_summary(row) for row in blockers[:50]]}


def confirm(db, user, body):
    _owner(user)
    if not body.confirm:
        raise HTTPException(422, 'Confirme o arquivamento após conferir os pedidos.')
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    if db.bind.dialect.name == 'postgresql':
        # Serializes absent receipts too; one response lost on the wire is retried.
        key = int.from_bytes(hashlib.sha256(b'order-archive:' + body.request_id.bytes).digest()[:8], 'big', signed=True)
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
    previous = db.get(PedidoArchiveOperation, body.request_id)
    if previous:
        if previous.actor_id != user.id or previous.fingerprint != fingerprint:
            raise HTTPException(409, 'Esta confirmação já foi utilizada em outro arquivamento.')
        return previous.result
    rows = _rows(db, lock=True)
    if len(rows) != body.expected_count or not hmac.compare_digest(_token(rows), body.plan_token):
        raise HTTPException(409, 'Os pedidos mudaram após a prévia. Atualize e confira novamente.')
    if any(_blocked(row) for row in rows):
        raise HTTPException(409, 'Há reservas ou condicionais pendentes. Conclua ou cancele pelo fluxo próprio antes de arquivar a lista.')
    moment = settings.now()
    # Only rows actually reviewed and locked are archived. A concurrent new order
    # stays current; no cutoff date or background cleanup silently hides it.
    ids = [str(row.id) for row in rows]
    for row in rows:
        row.archived_at, row.archived_by = moment, user.id
    bind_actor(db, user, request_id=str(body.request_id))
    db.flush()
    remaining = db.query(Pedido.id).filter(Pedido.archived_at.is_(None)).count()
    result = {'archived_count': len(rows), 'archived_at': moment.isoformat(),
              'remaining_count': remaining, 'history_preserved': True}
    db.add(PedidoArchiveOperation(id=body.request_id, actor_id=user.id, fingerprint=fingerprint,
                                 order_ids=ids, result=result, created_at=moment))
    record(db, 'orders_archived', 'pedidos', entity='pedido_archive_operations', entity_id=str(body.request_id),
           changes={'archived_count': len(rows), 'history_preserved': True, 'remaining_count': remaining})
    db.flush()
    return result
