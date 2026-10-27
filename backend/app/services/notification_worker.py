"""Bounded embedded worker: scheduled inbox messages and persistent push outbox."""
import logging

from ..database import SessionLocal
from . import notification_push as push
from .worker_health import beat

logger = logging.getLogger(__name__)


def cycle(stop, session_factory=SessionLocal):
    from .notifications import publish_due_notifications, run_notification_rules
    beat('notifications')
    with session_factory() as db:
        run_notification_rules(db)
        publish_due_notifications(db)
        db.commit()
    # Small batches bound shutdown time and network load. Each claim is committed
    # before contacting the provider; a crash lease is eligible after 90 seconds.
    for _ in range(12):
        if stop.is_set():
            break
        with session_factory() as db:
            claim = push.claim_delivery(db)
            db.commit()
        if claim is None:
            break
        outcome = push.send_claim(claim)
        with session_factory() as db:
            push.finish_delivery(db, claim, outcome)
            db.commit()
        beat('notifications')


def main(stop):
    beat('notifications')
    while not stop.is_set():
        try:
            cycle(stop)
        except Exception as error:
            # Exception strings from push libraries may contain device secrets.
            logger.error("Notification worker cycle failed (%s); durable jobs will be retried.", type(error).__name__)
        stop.wait(5)
