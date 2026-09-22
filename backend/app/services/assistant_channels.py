"""Provider authentication is done before these normalized messages are persisted."""
import re
from dataclasses import dataclass
from datetime import timedelta

import requests
from sqlalchemy.exc import IntegrityError
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

from ..config import settings
from ..models.assistant import AssistantIdentity, AssistantMessage, utcnow
from ..models.usuario import Usuario


@dataclass
class Incoming:
    channel: str
    external_id: str
    conversation_id: str
    sender_id: str
    text: str
    should_reply: bool = True


def enabled_channels():
    return [channel for channel, enabled in (
        ("telegram", settings.ASSISTANT_TELEGRAM_ENABLED),
        ("whatsapp", settings.ASSISTANT_WHATSAPP_ENABLED),
    ) if enabled]


def telegram_message(update):
    message = update.get("message")
    if not isinstance(message, dict) or message.get("sender_chat"):
        return None  # edits, channels, anonymous admins and service updates are not commands
    sender = message.get("from", {})
    chat = message.get("chat", {})
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return None
    if sender.get("is_bot") or not sender.get("id"):
        return None
    if chat.get("type") not in ("group", "supergroup"):
        return None
    if not settings.TELEGRAM_GROUP_ID or str(chat.get("id")) != settings.TELEGRAM_GROUP_ID:
        return None
    content = message.get("text") or message.get("caption") or ""
    if not isinstance(content, str) or len(content) > 6000:
        return None
    if not content:
        if not any(message.get(kind) for kind in ("photo", "audio", "voice", "video", "document", "sticker",
                                                 "video_note", "contact", "location", "venue", "poll")):
            return None  # membership changes, pins and other service events are not user requests
        content = "[Mídia recebida. Leitura de imagem/áudio ainda não habilitada; solicite descrição em texto.]"
    content = content.strip()
    username = settings.TELEGRAM_BOT_USERNAME.lower()
    first = content.split()[0] if content.split() else ""
    if first.startswith("/") and "@" in first and first.split("@", 1)[1].lower() != username:
        return None
    # Every text from an authorized employee in the configured group can address the
    # coordinator, including follow-ups like "e ontem?" and confirmations. Telegram
    # group privacy must separately be disabled for ordinary messages to reach us.
    # Remove only our command suffix, preserving the rest of the user's message.
    if first.startswith("/") and "@" in first:
        content = first.split("@", 1)[0] + content[len(first):]
    conversation = str(chat["id"])
    if message.get("message_thread_id"):
        conversation += ":" + str(message["message_thread_id"])
    if not isinstance(update.get("update_id"), int):
        return None
    return Incoming("telegram", str(update["update_id"]), conversation, str(sender["id"]), content, True)


def twilio_message(form):
    if form.get("AccountSid") != settings.TWILIO_ACCOUNT_SID or form.get("To") != settings.TWILIO_WHATSAPP_FROM:
        return None
    sender = form.get("From", "")
    if not re.fullmatch(r"whatsapp:\+[1-9][0-9]{6,14}", sender):
        return None
    sid = form.get("MessageSid", "")
    if not re.fullmatch(r"SM[0-9a-fA-F]{32}", sid):
        return None
    content = form.get("Body", "")
    if not isinstance(content, str) or len(content) > 6000:
        return None
    if not content:
        content = "[Mídia recebida. Leitura de imagem/áudio ainda não habilitada; solicite descrição em texto.]"
    return Incoming("whatsapp", sid, sender, sender, content)


def authorized_identity(db, channel, external_id):
    return db.query(AssistantIdentity).join(Usuario, Usuario.id == AssistantIdentity.user_id).filter(
        AssistantIdentity.channel == channel, AssistantIdentity.external_id == external_id,
        AssistantIdentity.active.is_(True), Usuario.ativo.is_(True),
        Usuario.role.in_(["ADMIN", "GERENTE", "VENDEDOR"]),
    ).first()


def enqueue_incoming(db, incoming):
    if incoming is None:
        return "ignored"
    if incoming.channel not in enabled_channels():
        return "paused"
    identity = authorized_identity(db, incoming.channel, incoming.sender_id)
    if not identity:
        return "ignored"
    # Serialize quota checks for this identity; concurrent provider retries remain idempotent.
    db.query(Usuario).filter_by(id=identity.user_id).with_for_update().first()
    duplicate = db.query(AssistantMessage.id).filter_by(channel=incoming.channel, external_id=incoming.external_id).first()
    if duplicate:
        return "duplicate"
    count = db.query(AssistantMessage).filter(
        AssistantMessage.user_id == identity.user_id,
        AssistantMessage.created_at >= utcnow() - timedelta(days=1),
    ).count()
    if count >= settings.ASSISTANT_DAILY_MESSAGES:
        return "rate_limited"
    message = AssistantMessage(
        channel=incoming.channel, external_id=incoming.external_id,
        conversation_id=incoming.conversation_id, sender_id=incoming.sender_id,
        user_id=identity.user_id, text=incoming.text, should_reply=incoming.should_reply,
    )
    try:
        with db.begin_nested():
            db.add(message)
            db.flush()
    except IntegrityError:
        return "duplicate"
    return "queued"


class DeliveryError(Exception):
    def __init__(self, code, retryable=False, uncertain=False):
        self.code, self.retryable, self.uncertain = code, retryable, uncertain
        super().__init__(code)


def send_delivery(delivery):
    """Never put exceptions containing tokens, URLs or message bodies into logs."""
    if delivery.channel not in enabled_channels():
        raise DeliveryError("channel_paused")
    try:
        if delivery.channel == "telegram":
            if not settings.TELEGRAM_BOT_TOKEN:
                raise DeliveryError("telegram_not_configured")
            chat, _, thread = delivery.destination.partition(":")
            if chat != settings.TELEGRAM_GROUP_ID:
                raise DeliveryError("group_no_longer_allowed")
            payload = {"chat_id": chat, "text": delivery.text, "link_preview_options": {"is_disabled": True}}
            if thread:
                payload["message_thread_id"] = int(thread)
            method = 'sendMessage'
            if getattr(delivery, 'document_url', None):
                from .superfrete import safe_label
                if not safe_label(delivery.document_url):raise DeliveryError('invalid_document_url')
                method = 'sendDocument'
                payload = {'chat_id':chat,'document':delivery.document_url,'caption':delivery.text[:1024]}
                if thread:payload['message_thread_id']=int(thread)
            result = requests.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
                json=payload, timeout=(5, 25),
            )
            if result.status_code != 200:
                raise DeliveryError(f"telegram_http_{result.status_code}", retryable=result.status_code == 429,
                                    uncertain=result.status_code >= 500)
            body = result.json()
            if not body.get("ok"):
                raise DeliveryError("telegram_rejected")
            return str(body["result"]["message_id"])
        if delivery.channel == "whatsapp":
            if not all((settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_WHATSAPP_FROM)):
                raise DeliveryError("twilio_not_configured")
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN,
                            http_client=TwilioHttpClient(timeout=25, max_retries=0))
            result = client.messages.create(from_=settings.TWILIO_WHATSAPP_FROM, to=delivery.destination, body=delivery.text)
            return result.sid
        raise DeliveryError("unsupported_channel")
    except TwilioRestException as exc:
        raise DeliveryError(f"twilio_{exc.code or exc.status}", retryable=exc.status == 429,
                            uncertain=exc.status >= 500) from None
    except requests.RequestException:
        raise DeliveryError("network_outcome_unknown", uncertain=True) from None
    except (ValueError, KeyError):
        raise DeliveryError("provider_response_unknown", uncertain=True) from None
