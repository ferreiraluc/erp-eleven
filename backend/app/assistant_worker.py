"""Run with: cd backend && python -m app.assistant_worker.

PostgreSQL transaction locks serialize processing; crash before commit rolls back drafts.
Delivery is marked 'sending' before calling a provider. An interrupted send is ambiguous
and is never automatically repeated (review it in the administrator panel).
"""
import logging
import threading
from datetime import timedelta

from sqlalchemy import text, or_, and_
from sqlalchemy.orm import aliased

from .config import settings
from .database import SessionLocal
from .models.assistant import AssistantMessage, AssistantDelivery, utcnow
from .services.assistant_agent import AgentError, respond
from .services.assistant_channels import authorized_identity, send_delivery, DeliveryError, enabled_channels

logger = logging.getLogger("assistant_worker")


def lock_worker(db, key):
    # The SQLite branch is for isolated tests, not production deployment.
    return db.bind.dialect.name != "postgresql" or db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}).scalar()


def process_inbox():
    if not settings.ASSISTANT_ENABLED:
        return False
    with SessionLocal() as db:
        if not lock_worker(db, 711001):
            return False
        previous = aliased(AssistantMessage)
        earlier_pending = db.query(previous.id).filter(
            previous.channel == AssistantMessage.channel,
            previous.conversation_id == AssistantMessage.conversation_id,
            previous.status == "pending",
            or_(previous.created_at < AssistantMessage.created_at,
                and_(previous.created_at == AssistantMessage.created_at, previous.id < AssistantMessage.id)),
        ).exists()
        message = db.query(AssistantMessage).filter(
            AssistantMessage.channel.in_(enabled_channels()),
            AssistantMessage.status == "pending", AssistantMessage.available_at <= utcnow(),
            ~earlier_pending,
        ).order_by(AssistantMessage.created_at, AssistantMessage.id).with_for_update(skip_locked=True).first()
        if not message:
            return False
        identity = authorized_identity(db, message.channel, message.sender_id)
        if not identity or identity.user_id != message.user_id or (
            message.channel == "telegram" and message.conversation_id.split(":")[0] != settings.TELEGRAM_GROUP_ID
        ):
            message.status = "rejected"
            db.commit()
            return True
        try:
            with db.begin_nested():
                answer = respond(db, message, identity)
                message.response = answer
                message.status = "done"
                if answer:
                    db.add(AssistantDelivery(
                        event_key=f"reply:{message.id}", channel=message.channel,
                        destination=message.conversation_id, text=answer, user_id=message.user_id,
                        # Free-form Twilio responses are limited to the customer service window.
                        expires_at=message.created_at + timedelta(hours=23) if message.channel == "whatsapp" else None,
                    ))
                db.flush()
        except Exception as exc:
            # Savepoint rolls back any tool writes from the unsuccessful attempt.
            message.attempts += 1
            message.error_code = str(exc)[:80] if isinstance(exc, AgentError) else "processing_error"
            message.status = "failed" if message.attempts >= 3 else "pending"
            message.available_at = utcnow() + timedelta(seconds=60 * message.attempts)
            logger.warning("inbox_failed id=%s code=%s", message.id, message.error_code)
        db.commit()
        return True


def process_outbox():
    if not settings.ASSISTANT_ENABLED:
        return False
    with SessionLocal() as db:
        if not lock_worker(db, 711002):
            return False
        # A crashed worker may have sent a message but not saved its external ID.
        db.query(AssistantDelivery).filter(
            AssistantDelivery.status == "sending",
            AssistantDelivery.available_at < utcnow() - timedelta(minutes=5),
        ).update({"status": "uncertain", "error_code": "interrupted_send"}, synchronize_session=False)
        delivery = db.query(AssistantDelivery).filter(
            AssistantDelivery.channel.in_(enabled_channels()),
            AssistantDelivery.status == "pending", AssistantDelivery.available_at <= utcnow(),
        ).order_by(AssistantDelivery.created_at).with_for_update(skip_locked=True).first()
        if not delivery:
            db.commit()
            return False
        expires = delivery.expires_at
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=utcnow().tzinfo)
        if expires and expires <= utcnow():
            delivery.status = "expired"
            delivery.error_code = "whatsapp_window_closed"
            db.commit()
            return True
        if delivery.channel == "whatsapp":
            identity = authorized_identity(db, "whatsapp", delivery.destination)
            if not identity or identity.user_id != delivery.user_id:
                delivery.status = "cancelled"
                db.commit()
                return True
        if delivery.channel == "telegram" and delivery.destination.split(":")[0] != settings.TELEGRAM_GROUP_ID:
            delivery.status = "cancelled"
            db.commit()
            return True
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.available_at = utcnow()
        db.commit()
        try:
            delivery.provider_id = send_delivery(delivery)
            delivery.status = "accepted"  # provider accepted; not a claim of delivery/read
            delivery.error_code = None
        except DeliveryError as exc:
            delivery.error_code = exc.code
            delivery.status = "uncertain" if exc.uncertain else (
                "pending" if exc.retryable and delivery.attempts < 3 else "failed")
            delivery.available_at = utcnow() + timedelta(minutes=delivery.attempts)
        except Exception:
            delivery.status = "uncertain"
            delivery.error_code = "send_outcome_unknown"
        db.commit()
        return True


def main(stop_event=None):
    stop_event = stop_event or threading.Event()
    logging.basicConfig(level=logging.INFO)
    logger.info("Assistant worker started; enabled=%s", settings.ASSISTANT_ENABLED)
    while not stop_event.is_set():
        try:
            incoming = process_inbox()
            outgoing = process_outbox()
            if not incoming and not outgoing:
                stop_event.wait(2)
        except KeyboardInterrupt:
            break
        except Exception:
            # Do not log DB connection URLs or provider exception payloads.
            logger.error("Worker iteration failed; check database/configuration")
            stop_event.wait(5)


if __name__ == "__main__":
    main()
