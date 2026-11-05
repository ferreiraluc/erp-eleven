"""Operational printing does not grant purchasing or ERP write permissions."""
from uuid import UUID

from ..config import settings
from ..models.assistant import AssistantAction, AssistantMessage
from .assistant_channels import authorized_identity

PRINT_ACTION_KINDS = frozenset(("impressao", "arquivo_imprimir", "frete_imprimir"))
PRINT_AUTHORIZATION_ERROR = "A autorização do solicitante mudou. Peça uma nova impressão com um usuário autorizado."


def may_print(db, message, identity):
    """Recheck the linked employee and conversation, independently of can_register."""
    if not message or not message.should_reply or not identity or not identity.active or identity.user_id != message.user_id:
        return False
    if identity.channel != message.channel or identity.external_id != message.sender_id:
        return False
    current = authorized_identity(db, message.channel, message.sender_id)
    if not current or current.id != identity.id or current.user_id != message.user_id:
        return False
    if message.channel == "telegram":
        return bool(settings.TELEGRAM_GROUP_ID and
                    message.conversation_id.split(":")[0] == settings.TELEGRAM_GROUP_ID)
    if message.channel == "whatsapp_web":
        from .assistant_whatsapp_bridge import conversation_allowed
        return conversation_allowed(db, message.conversation_id, message.sender_id)
    return message.channel == "whatsapp" and message.conversation_id == message.sender_id


def _source_authorized(db, source, user_id):
    if not source or source.user_id != user_id or not source.should_reply:
        return False
    return may_print(db, source, authorized_identity(db, source.channel, source.sender_id))


def bot_print_job_authorized(db, job):
    """Revalidate bot jobs at dispatch/download; frontend jobs retain their policy.

    An accepted print may wait while an employee, phone or group is revoked.
    Do not let that queued document bypass the current bot authorization.
    """
    if job.source not in ("bot", "bot_pdf_ephemeral", "superfrete"):
        return True
    action = db.get(AssistantAction, job.request_key) if job.request_key else None
    if action:
        if (action.kind not in PRINT_ACTION_KINDS or action.user_id != job.user_id
                or action.status != "executed" or action.result_id != job.id):
            return False
        return _source_authorized(db, db.get(AssistantMessage, action.source_message_id), job.user_id)
    if job.source != "superfrete":
        return False
    # Automatic printing after a paid label uses a deterministic queue key rather
    # than the action ID. A frontend order has no originating assistant message.
    from ..models.address_book import FreightOrder
    try:
        key = UUID(str((job.snapshot or {}).get("freight_id")))
    except (ValueError, TypeError):
        return False
    order = db.get(FreightOrder, key)
    if not order or order.user_id != job.user_id:
        return False
    source = db.get(AssistantMessage, order.request_key)
    return source is None or _source_authorized(db, source, job.user_id)
