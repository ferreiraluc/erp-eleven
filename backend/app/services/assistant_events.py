"""Tracking announcements inserted atomically with the existing ERP transaction."""
import uuid
from sqlalchemy import event, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import settings
from ..models.assistant import AssistantDelivery, utcnow
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento


@event.listens_for(Session, "before_flush")
def tracking_outbox(session, flush_context, instances):
    if not settings.ASSISTANT_ENABLED or not settings.ASSISTANT_TELEGRAM_ENABLED or not settings.TELEGRAM_GROUP_ID:
        return
    # Do not emit on updates to status alone or on loading historical shipments.
    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, (Pedido, Rastreamento)) or not obj.codigo_rastreio:
            continue
        if obj in session.deleted or (isinstance(obj, Rastreamento) and obj.ativo is False):
            continue
        if obj not in session.new and not inspect(obj).attrs.codigo_rastreio.history.has_changes():
            continue
        code = obj.codigo_rastreio.strip()
        customer = obj.cliente_nome if isinstance(obj, Pedido) else obj.destinatario
        text = f"Rastreio cadastrado no ERP\nCliente: {customer or 'Não informado'}\nCódigo: {code}"
        key = f"tracking:{settings.TELEGRAM_GROUP_ID}:{code}"
        stmt = insert(AssistantDelivery).values(
            id=uuid.uuid4(), event_key=key, channel="telegram", destination=settings.TELEGRAM_GROUP_ID,
            text=text, status="pending", attempts=0, created_at=utcnow(), available_at=utcnow(),
        ).on_conflict_do_nothing(index_elements=["event_key"])
        session.execute(stmt)
