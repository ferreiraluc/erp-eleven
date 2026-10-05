"""Revalidate queued replies without regenerating answers or repeating actions."""
import re
import uuid
from datetime import timezone

from sqlalchemy import select

from ..config import settings
from ..models.assistant import AssistantDelivery, AssistantIdentity, AssistantMessage
from ..models.usuario import Usuario
from .access_policy import sales_context_since
from .assistant_channels import authorized_identity

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_REPLY = re.compile(rf"reply:({_UUID})(?::[0-9]+)?")
_FREIGHT = re.compile(rf"(freight-pdf|freight-printed|freight-pdf-timeout):({_UUID})")
_RECOVERY = re.compile(rf"freight-recovery:({_UUID}):(quoted|pending|failed)")


def _aware(moment):
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _same_identity(db, source, user_id, *, can_register=False):
    identity = authorized_identity(db, source.channel, source.sender_id)
    return bool(identity and identity.user_id == user_id and (not can_register or identity.can_register))


def delivery_rejection(db, delivery):
    """Return a stable reason, or None if this delivery is still authorized.

    Financial scope is checked against the originating request, not the later
    generation/delivery timestamp. Operational notifications have their own
    provenance and must not be classified by searching their text.
    """
    if delivery.channel not in ("telegram", "whatsapp"):
        return "delivery_channel_invalid"
    if delivery.channel == "telegram" and (
        not settings.TELEGRAM_GROUP_ID
        or delivery.destination.split(":")[0] != settings.TELEGRAM_GROUP_ID
    ):
        return "delivery_group_changed"
    if delivery.user_id is None:
        # Existing system broadcasts are internal outbox records, independent of
        # an employee. They may only reach the currently configured whole group.
        if (delivery.channel == "telegram" and delivery.destination == settings.TELEGRAM_GROUP_ID
                and not delivery.event_key.startswith(("reply:", "freight-"))):
            return None
        return "delivery_author_missing"
    user = db.get(Usuario, delivery.user_id)
    if not user or not user.ativo or getattr(user.role, "value", user.role) not in ("ADMIN", "GERENTE", "VENDEDOR"):
        return "delivery_user_inactive"

    reply = _REPLY.fullmatch(delivery.event_key)
    if reply:
        source = db.get(AssistantMessage, uuid.UUID(reply[1]))
        if (not source or source.status != "done" or source.user_id != delivery.user_id
                or source.channel != delivery.channel or source.conversation_id != delivery.destination):
            return "delivery_source_changed"
        if delivery.channel == "whatsapp" and source.sender_id != delivery.destination:
            return "delivery_source_changed"
        if not _same_identity(db, source, delivery.user_id):
            return "delivery_identity_changed"
        cutoff = sales_context_since(db, user)
        if cutoff and _aware(source.created_at) <= _aware(cutoff):
            return "delivery_access_changed"
        return None

    freight, recovery = _FREIGHT.fullmatch(delivery.event_key), _RECOVERY.fullmatch(delivery.event_key)
    if not freight and not recovery:
        return "delivery_source_missing"
    if delivery.channel != "telegram" or getattr(user.role, "value", user.role) not in ("ADMIN", "GERENTE"):
        return "delivery_user_ineligible"
    from ..models.address_book import FreightOrder
    order = db.get(FreightOrder, uuid.UUID(freight[2] if freight else recovery[1]))
    if (not order or order.user_id != delivery.user_id or order.notify_channel != delivery.channel
            or order.notify_destination != delivery.destination):
        return "delivery_source_changed"
    if recovery:
        if recovery[2] == "failed":
            if order.recovery_kind or order.state in ("quoted", "pending", "released", "posted", "delivered"):
                return "delivery_freight_changed"
        elif order.state != recovery[2]:
            return "delivery_freight_changed"
    try:
        source_key = uuid.UUID(str(order.payload["_recovery_source"])) if recovery and order.payload.get("_recovery_source") else order.request_key
    except (TypeError, ValueError):
        return "delivery_source_changed"
    source = db.get(AssistantMessage, source_key)
    if recovery and order.payload.get("_recovery_source") and not source:
        return "delivery_source_changed"
    if source:
        if (source.user_id != delivery.user_id or source.channel != delivery.channel
                or source.conversation_id != delivery.destination
                or not _same_identity(db, source, delivery.user_id, can_register=bool(recovery))):
            return "delivery_identity_changed"
    else:
        # Purchases started in the frontend may not have an originating bot
        # message. Keep the existing linked-employee notification contract.
        identities = db.query(AssistantIdentity.id).filter_by(
            user_id=delivery.user_id, channel="telegram", active=True,
        )
        if recovery:
            identities = identities.filter(AssistantIdentity.can_register.is_(True))
        if not identities.first():
            return "delivery_identity_changed"
    return None


def cancel_pending_dependents(db, delivery_id):
    """Retire unsent dependent parts, preserving accepted/uncertain send evidence."""
    descendants = select(AssistantDelivery.id).where(
        AssistantDelivery.depends_on_id == delivery_id,
    ).cte(name="delivery_descendants", recursive=True)
    descendants = descendants.union(select(AssistantDelivery.id).join(
        descendants, AssistantDelivery.depends_on_id == descendants.c.id,
    ))
    db.query(AssistantDelivery).filter(
        AssistantDelivery.id.in_(select(descendants.c.id)), AssistantDelivery.status == "pending",
    ).update({"status": "cancelled", "error_code": "delivery_dependency_unavailable"}, synchronize_session=False)
