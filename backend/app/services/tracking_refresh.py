"""Apply provider results only to the exact parcel version that was consulted.

Network calls precede write locks. Every caller locks parent orders before parcels,
in a stable order, and commits parcel/order changes in one transaction.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..config import settings
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento, RastreamentoStatus
from .rastreamento_sync import RastreamentoSyncService


@dataclass(frozen=True)
class TrackingVersion:
    id: UUID
    code: str
    order_id: UUID | None
    last_update: datetime | None
    updated_at: datetime | None
    status: str

    @classmethod
    def capture(cls, row):
        return cls(row.id, row.codigo_rastreio, row.pedido_id, row.ultima_atualizacao, row.updated_at, row.status)

    def matches(self, row):
        return bool(row and row.ativo and self == self.capture(row))


def apply_provider_results(db, results):
    """Returns (changed rows, skipped codes). Does not commit or contact a provider."""
    if not results:
        return [], []
    parents = sorted({version.order_id for version, *_ in results if version.order_id}, key=str)
    with db.no_autoflush:
        if parents:
            db.query(Pedido.id).filter(Pedido.id.in_(parents)).order_by(Pedido.id).with_for_update().all()
        ids = [version.id for version, *_ in results]
        locked = {row.id: row for row in db.query(Rastreamento).filter(Rastreamento.id.in_(ids))
                  .order_by(Rastreamento.id).populate_existing().with_for_update().all()}
    changed, skipped = [], []
    for version, events, meta, inferred in results:
        row = locked.get(version.id)
        if not version.matches(row):
            skipped.append(version.code)
            continue
        row.historico_eventos, row.rastreio_info, row.status = events, meta, inferred
        row.ultima_atualizacao = settings.now()
        changed.append(row)
    db.flush()
    synced_orders = set()
    for row in changed:
        if row.pedido_id and row.pedido_id not in synced_orders:
            RastreamentoSyncService.sincronizar_rastreamento_com_pedido(db, row)
            synced_orders.add(row.pedido_id)
    return changed, skipped


def refresh_active(db):
    from .wonca_service import parse_tracking
    rows = db.query(Rastreamento).filter(Rastreamento.ativo.is_(True),
                                         Rastreamento.status != RastreamentoStatus.ENTREGUE).all()
    # Snapshot all versions before external calls; later responses never overwrite
    # an intervening edit, archive, relink or newer provider update.
    versions = [TrackingVersion.capture(row) for row in rows]
    results, errors = [], []
    for version in versions:
        try:
            events, meta, inferred = parse_tracking(version.code)
            results.append((version, events, meta, inferred))
        except Exception as exc:
            errors.append(f'{version.code}: {exc}')
    changed, skipped = apply_provider_results(db, results)
    return {'updated': len(changed), 'errors': errors, 'skipped': skipped}
