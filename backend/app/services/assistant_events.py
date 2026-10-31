"""Tracking announcements inserted atomically with the existing ERP transaction."""
import uuid
from sqlalchemy import event, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import settings
from ..models.assistant import AssistantDelivery, AssistantWhatsAppBridge, utcnow
from ..models.pedido import Pedido
from ..models.rastreamento import Rastreamento


@event.listens_for(Session, "before_flush")
def tracking_outbox(session, flush_context, instances):
    if not settings.ASSISTANT_ENABLED:
        return
    changed = [obj for obj in list(session.new) + list(session.dirty)
               if isinstance(obj, (Pedido, Rastreamento)) and obj.codigo_rastreio
               and obj not in session.deleted and not (isinstance(obj, Rastreamento) and obj.ativo is False)
               and (obj in session.new or inspect(obj).attrs.codigo_rastreio.history.has_changes())]
    if not changed:
        return
    telegram = bool(settings.ASSISTANT_TELEGRAM_ENABLED and settings.TELEGRAM_GROUP_ID)
    bridge = session.get(AssistantWhatsAppBridge, "primary")
    groups = (bridge.allowed_groups if bridge and bridge.enabled and bridge.notify_tracking else [])
    if not telegram and not groups:
        return
    # Do not emit on updates to status alone or on loading historical shipments.
    for obj in changed:
        code = obj.codigo_rastreio.strip()
        customer = obj.cliente_nome if isinstance(obj, Pedido) else obj.destinatario
        if telegram:
            text = f"Rastreio cadastrado no ERP\nCliente: {customer or 'Não informado'}\nCódigo: {code}"
            key = f"tracking:{settings.TELEGRAM_GROUP_ID}:{code}"
            stmt = insert(AssistantDelivery).values(
                id=uuid.uuid4(), event_key=key, channel="telegram", destination=settings.TELEGRAM_GROUP_ID,
                text=text, status="pending", attempts=0, created_at=utcnow(), available_at=utcnow(),
            ).on_conflict_do_nothing(index_elements=["event_key"])
            session.execute(stmt)
        for group in dict.fromkeys(groups):
            # Notifications are opt-in and remain internal to the current
            # allowlist. Keep the code copyable, before its dependent details.
            key = f"tracking:whatsapp_web:{group}:{code}"
            delivery_id = session.execute(insert(AssistantDelivery).values(
                id=uuid.uuid4(), event_key=key, channel="whatsapp_web", destination=group,
                text=code, status="pending", attempts=0, created_at=utcnow(), available_at=utcnow(),
            ).on_conflict_do_nothing(index_elements=["event_key"]).returning(AssistantDelivery.id)).scalar_one_or_none()
            if delivery_id:
                session.execute(insert(AssistantDelivery).values(
                    id=uuid.uuid4(), event_key=key+":details", channel="whatsapp_web", destination=group,
                    text=f"Rastreio cadastrado no ERP\nCliente: {customer or 'Não informado'}",
                    depends_on_id=delivery_id, status="pending", attempts=0,
                    created_at=utcnow(), available_at=utcnow(),
                ).on_conflict_do_nothing(index_elements=["event_key"]))
