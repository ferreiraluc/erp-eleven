"""Delivery authorization regressions: disposable SQLite and a fake provider only."""
import json
import uuid
from datetime import date, timedelta

import pytest

from test_assistant import incoming, setup
from test_access_postgres import pg
from app import assistant_worker as worker
from app.api.endpoints import user_admin
from app.database import Base
from app.models import Usuario, Vendedor, Venda
from app.models.access import AuditEvent, AuthSession
from app.models.address_book import FreightOrder
from app.models.assistant import AssistantDelivery, AssistantIdentity, AssistantMessage, utcnow
from app.models.usuario import UsuarioRole
from app.models.venda import MoedaTipo, PagamentoMetodo
from app.services.assistant_queries import SalesArgs, query_sales
from app.services.assistant_channels import DeliveryError


@pytest.fixture
def financial_queue(setup, monkeypatch):
    factory, _, uid = setup
    with factory() as db:
        Base.metadata.create_all(db.bind, tables=[AuditEvent.__table__, AuthSession.__table__, FreightOrder.__table__])
        actor = db.get(Usuario, uid)
        actor.role = UsuarioRole.GERENTE
        actor.sales_scope = "all"
        actor.sales_seller = "Fixture Own"
        own = Vendedor(nome="Fixture Own", usuario_id=uid)
        other = Vendedor(nome="PRIVATE_OTHER_SELLER")
        db.add_all([own, other])
        db.flush()
        actor.vendedor_id = own.id
        for seller, amount in ((own, 10), (other, 999)):
            db.add(Venda(vendedor_id=seller.id, data_venda=date(2026, 10, 1),
                         moeda=MoedaTipo.R_DOLLAR, valor_bruto=amount, valor_liquido=amount,
                         metodo_pagamento=PagamentoMetodo.PIX_POWER))
        db.commit()

    def financial_reply(db, message, identity):
        # Only the language-model wording is replaced. The financial query and
        # inbox-to-outbox path are the production functions.
        return json.dumps(query_sales(db, SalesArgs(origem="vendas"), message.user_id))

    monkeypatch.setattr(worker, "respond", financial_reply)
    sent = []
    monkeypatch.setattr(worker, "send_delivery", lambda delivery: sent.append(delivery.text) or "fake-accepted")
    return factory, uid, sent


def queue_reply(factory, uid, channel):
    with factory() as db:
        message = incoming(db, uid, "Consulte as vendas operacionais", channel=channel)
        # The originating request predates permission changes, even if generation
        # and delivery complete after a long model call or a provider retry.
        message.created_at = utcnow() - timedelta(minutes=2)
        db.commit()
    assert worker.process_inbox()
    with factory() as db:
        row = db.query(AssistantDelivery).one()
        assert row.status == "pending"
        assert "PRIVATE_OTHER_SELLER" in row.text
        return row.id


def restrict_user(factory, uid):
    with factory() as db:
        actor = db.get(Usuario, uid)
        user_admin.update_user(uid, user_admin.UserAccess(
            nome=actor.nome, ativo=True, sales_scope="own", sales_seller=actor.sales_seller,
            vendedor_id=actor.vendedor_id,
        ), db=db, owner=actor)
        # Current queries already obey the new scope. Only the queued old result
        # can still expose the other seller's data.
        current = query_sales(db, SalesArgs(origem="vendas"), uid)
        assert "PRIVATE_OTHER_SELLER" not in json.dumps(current)


@pytest.mark.parametrize("channel", ["telegram", "whatsapp"])
def test_old_financial_reply_is_not_sent_after_access_is_restricted(financial_queue, channel):
    factory, uid, sent = financial_queue
    queue_reply(factory, uid, channel)
    restrict_user(factory, uid)
    assert worker.process_outbox()
    assert sent == [], "The provider received financial data no longer permitted for this user"


@pytest.mark.parametrize("channel", ["telegram", "whatsapp"])
def test_origin_time_matters_even_when_delivery_is_newer_than_access_change(financial_queue, channel):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, channel)
    restrict_user(factory, uid)
    with factory() as db:
        cutoff = db.query(AuditEvent).filter_by(action="access_changed").one().occurred_at
        # Simulate generation completing after the restriction; a guard based
        # only on delivery.created_at would incorrectly accept this older request.
        db.get(AssistantDelivery, key).created_at = cutoff + timedelta(seconds=1)
        assert db.query(AssistantMessage).one().created_at < cutoff
        db.commit()
    assert worker.process_outbox()
    assert sent == [], "A new outbox timestamp must not authorize an old financial response"


@pytest.mark.parametrize("channel", ["telegram", "whatsapp"])
@pytest.mark.parametrize("change", ["inactive_user", "inactive_identity", "reassigned_identity"])
def test_queued_reply_requires_its_original_active_identity(financial_queue, channel, change):
    factory, uid, sent = financial_queue
    queue_reply(factory, uid, channel)
    with factory() as db:
        identity = db.query(AssistantIdentity).filter_by(channel=channel, user_id=uid).one()
        if change == "inactive_user":
            db.get(Usuario, uid).ativo = False
        elif change == "inactive_identity":
            identity.active = False
        else:
            other = Usuario(nome="Replacement", email="replacement@example.test", senha_hash="unused", role=UsuarioRole.GERENTE)
            db.add(other)
            db.flush()
            identity.user_id = other.id
        db.commit()
    assert worker.process_outbox()
    assert sent == [], "The Telegram reply outlived the identity that authorized it"


def test_group_broadcast_does_not_require_a_user_identity(financial_queue):
    factory, uid, sent = financial_queue
    with factory() as db:
        db.get(Usuario, uid).ativo = False
        db.add(AssistantDelivery(event_key="tracking:-100123:fixture", channel="telegram",
                                destination="-100123", text="Operational tracking broadcast", user_id=None))
        db.commit()
    assert worker.process_outbox()
    assert sent == ["Operational tracking broadcast"]


def test_already_authorized_label_pdf_is_not_a_financial_summary(financial_queue):
    factory, uid, sent = financial_queue
    with factory() as db:
        order = FreightOrder(request_key=uuid.uuid4(), user_id=uid, environment="sandbox", state="released",
                             payload={}, rates=[], notify_channel="telegram", notify_destination="-100123")
        db.add(order)
        db.flush()
        db.add(AssistantDelivery(event_key="freight-pdf:" + str(order.id), channel="telegram",
                                destination="-100123", text="Already authorized operational label",
                                user_id=uid, document_pdf=b"%PDF-fake-no-print-no-provider"))
        db.commit()
    restrict_user(factory, uid)
    assert worker.process_outbox()
    assert sent == ["Already authorized operational label"]


@pytest.mark.parametrize("channel", ["telegram", "whatsapp"])
def test_new_personal_reply_after_restriction_is_delivered(financial_queue, channel):
    factory, uid, sent = financial_queue
    restrict_user(factory, uid)
    with factory() as db:
        incoming(db, uid, "Minhas vendas operacionais", channel=channel)
        db.commit()
    assert worker.process_inbox() and worker.process_outbox()
    assert len(sent) == 1 and "Fixture Own" in sent[0]
    assert "PRIVATE_OTHER_SELLER" not in sent[0]


@pytest.mark.parametrize("channel", ["telegram", "whatsapp"])
def test_password_version_change_alone_does_not_revoke_the_bot_reply(financial_queue, channel):
    factory, uid, sent = financial_queue
    queue_reply(factory, uid, channel)
    with factory() as db:
        db.get(Usuario, uid).auth_version += 1
        db.add(AuditEvent(action="password_changed", module="conta", entity="usuarios", entity_id=str(uid)))
        db.commit()
    assert worker.process_outbox()
    assert len(sent) == 1


@pytest.mark.parametrize("change", ["missing", "user", "channel", "topic", "sender", "status"])
def test_reply_requires_exact_persisted_source(financial_queue, change):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        source = db.query(AssistantMessage).one()
        if change == "missing":
            db.get(AssistantDelivery, key).event_key = "reply:" + str(uuid.uuid4())
        elif change == "user":
            other = Usuario(nome="Another", email="another@example.test", senha_hash="unused")
            db.add(other)
            db.flush()
            source.user_id = other.id
        elif change == "channel":
            source.channel = "whatsapp"
        elif change == "topic":
            source.conversation_id = "-100123:42"
        elif change == "sender":
            source.sender_id = "999"
        else:
            source.status = "failed"
        db.commit()
    assert worker.process_outbox()
    assert sent == []
    with factory() as db:
        row = db.get(AssistantDelivery, key)
        assert row.status == "cancelled" and row.attempts == 0 and row.provider_id is None


def test_another_valid_identity_does_not_authorize_a_reply_from_revoked_sender(financial_queue):
    factory, uid, sent = financial_queue
    queue_reply(factory, uid, "telegram")
    with factory() as db:
        db.query(AssistantIdentity).filter_by(channel="telegram", external_id="123").one().active = False
        db.add(AssistantIdentity(channel="telegram", external_id="456", user_id=uid, active=True))
        db.commit()
    assert worker.process_outbox()
    assert sent == []


def test_retry_rechecks_access_before_second_provider_attempt(financial_queue, monkeypatch):
    factory, uid, _ = financial_queue
    key = queue_reply(factory, uid, "telegram")
    attempts = []
    def limited(delivery):
        attempts.append(delivery.id)
        raise DeliveryError("fixture_429", retryable=True)
    monkeypatch.setattr(worker, "send_delivery", limited)
    assert worker.process_outbox()
    restrict_user(factory, uid)
    with factory() as db:
        db.get(AssistantDelivery, key).available_at = utcnow()
        db.commit()
    assert worker.process_outbox()
    assert attempts == [key]
    with factory() as db:
        row = db.get(AssistantDelivery, key)
        assert row.status == "cancelled" and row.attempts == 1
        assert row.error_code == "delivery_access_changed"


def test_rejection_cancels_all_unsent_parts_but_preserves_send_evidence(financial_queue):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        parent = db.get(AssistantDelivery, key)
        previous = parent.id
        for index, status in enumerate(("pending", "pending", "accepted", "uncertain", "sending"), start=1):
            part = AssistantDelivery(event_key=parent.event_key + f":{index}", user_id=uid,
                channel="telegram", destination=parent.destination, text=f"Part {index}",
                status=status, depends_on_id=previous, available_at=utcnow() + timedelta(hours=1))
            db.add(part)
            db.flush()
            previous = part.id
        db.get(Usuario, uid).ativo = False
        db.commit()
    assert worker.process_outbox()
    assert sent == []
    with factory() as db:
        rows = db.query(AssistantDelivery).order_by(AssistantDelivery.created_at).all()
        assert [row.status for row in rows] == ["cancelled", "cancelled", "cancelled", "accepted", "uncertain", "sending"]
        assert all(row.error_code == "delivery_dependency_unavailable" for row in rows[1:3])


@pytest.mark.parametrize("parent_status", ["cancelled", "expired", "failed"])
def test_existing_orphan_parts_are_retired_without_sending(financial_queue, parent_status):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        parent = db.get(AssistantDelivery, key)
        parent.status = parent_status
        db.add(AssistantDelivery(event_key=parent.event_key + ":1", user_id=uid, channel=parent.channel,
            destination=parent.destination, text="Old pending child", depends_on_id=parent.id))
        db.commit()
    assert worker.process_outbox()
    assert not worker.process_outbox()
    assert sent == []
    with factory() as db:
        assert db.query(AssistantDelivery).filter_by(depends_on_id=key).one().status == "cancelled"


def test_uncertain_parent_never_authorizes_or_repeats_dependent_messages(financial_queue):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        parent = db.get(AssistantDelivery, key)
        parent.status = "uncertain"
        db.add(AssistantDelivery(event_key=parent.event_key + ":1", user_id=uid, channel=parent.channel,
            destination=parent.destination, text="Needs send review", depends_on_id=parent.id))
        db.commit()
    assert not worker.process_outbox()
    assert sent == []


def test_access_is_rechecked_between_parts_without_changing_accepted_evidence(financial_queue):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        parent = db.get(AssistantDelivery, key)
        db.add(AssistantDelivery(event_key=parent.event_key + ":1", user_id=uid, channel=parent.channel,
            destination=parent.destination, text="Second old financial part", depends_on_id=parent.id))
        db.commit()
    assert worker.process_outbox()
    restrict_user(factory, uid)
    assert worker.process_outbox()
    assert len(sent) == 1
    with factory() as db:
        assert db.get(AssistantDelivery, key).status == "accepted"
        assert db.query(AssistantDelivery).filter_by(depends_on_id=key).one().status == "cancelled"


def test_expired_telegram_notification_has_channel_neutral_reason(financial_queue):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        db.get(AssistantDelivery, key).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert worker.process_outbox()
    assert sent == []
    with factory() as db:
        assert db.get(AssistantDelivery, key).error_code == "delivery_expired"


@pytest.mark.parametrize("change", ["unknown_event", "wrong_group", "missing_author"])
def test_unsupported_or_redirected_deliveries_are_not_sent(financial_queue, change):
    factory, uid, sent = financial_queue
    key = queue_reply(factory, uid, "telegram")
    with factory() as db:
        row = db.get(AssistantDelivery, key)
        if change == "unknown_event": row.event_key = "unclassified:" + str(uuid.uuid4())
        elif change == "wrong_group": row.destination = "-100999"
        else: row.user_id = None
        db.commit()
    assert worker.process_outbox()
    assert sent == []


@pytest.mark.parametrize("changed", [False, True])
def test_freight_recovery_requires_order_destination_and_current_state(financial_queue, changed):
    factory, uid, sent = financial_queue
    with factory() as db:
        source = incoming(db, uid, "Emitir etiqueta", channel="telegram")
        source.status = "done"
        order = FreightOrder(request_key=source.id, user_id=uid, environment="sandbox",
            state="released" if changed else "pending", payload={}, rates=[],
            notify_channel="telegram", notify_destination="-100123")
        db.add(order)
        db.flush()
        db.add(AssistantDelivery(event_key=f"freight-recovery:{order.id}:pending", channel="telegram",
            destination="-100123", user_id=uid, text="Operational recovery"))
        db.commit()
    restrict_user(factory, uid)
    assert worker.process_outbox()
    assert sent == ([] if changed else ["Operational recovery"])


@pytest.mark.parametrize("change", ["missing_order", "wrong_owner", "wrong_topic", "inactive_identity", "inactive_user"])
def test_freight_pdf_keeps_operational_authorization_checks(financial_queue, change):
    factory, uid, sent = financial_queue
    with factory() as db:
        order = FreightOrder(request_key=uuid.uuid4(), user_id=uid, environment="sandbox", state="released",
            payload={}, rates=[], notify_channel="telegram", notify_destination="-100123")
        db.add(order)
        db.flush()
        if change == "wrong_owner":
            other = Usuario(nome="Another", email="freight-other@example.test", senha_hash="unused")
            db.add(other)
            db.flush()
            order.user_id = other.id
        elif change == "wrong_topic": order.notify_destination = "-100123:99"
        elif change == "inactive_identity": db.query(AssistantIdentity).filter_by(channel="telegram", user_id=uid).one().active = False
        elif change == "inactive_user": db.get(Usuario, uid).ativo = False
        db.add(AssistantDelivery(event_key="freight-pdf:" + str(uuid.uuid4() if change == "missing_order" else order.id),
            channel="telegram", destination="-100123", user_id=uid, text="Existing PDF", document_pdf=b"%PDF-fixture"))
        db.commit()
    assert worker.process_outbox()
    assert sent == []


@pytest.mark.parametrize("state,kind,allowed", [("uncertain", None, True), ("rejected", None, True),
    ("uncertain", "reconcile", False), ("pending", None, False), ("released", None, False)])
def test_recovery_failure_notification_reflects_terminal_recovery_not_literal_failed_state(financial_queue, state, kind, allowed):
    factory, uid, sent = financial_queue
    with factory() as db:
        order = FreightOrder(request_key=uuid.uuid4(), user_id=uid, environment="sandbox", state=state,
            recovery_kind=kind, payload={}, rates=[], notify_channel="telegram", notify_destination="-100123")
        db.add(order)
        db.flush()
        db.add(AssistantDelivery(event_key=f"freight-recovery:{order.id}:failed", channel="telegram",
            destination="-100123", user_id=uid, text="Recovery needs review"))
        db.commit()
    assert worker.process_outbox()
    assert sent == (["Recovery needs review"] if allowed else [])


@pytest.mark.parametrize("change", ["none", "wrong_topic", "cannot_register", "missing_source"])
def test_recovery_checks_its_selection_message_as_origin(financial_queue, change):
    factory, uid, sent = financial_queue
    with factory() as db:
        original = incoming(db, uid, "Cotar frete", channel="telegram")
        selection = incoming(db, uid, "Preparar frete", channel="telegram")
        original.status = selection.status = "done"
        if change == "wrong_topic": selection.conversation_id = "-100123:3"
        if change == "cannot_register": db.query(AssistantIdentity).filter_by(channel="telegram", user_id=uid).one().can_register = False
        order = FreightOrder(request_key=original.id, user_id=uid, environment="sandbox", state="pending",
            payload={"_recovery_source": str(uuid.uuid4() if change == "missing_source" else selection.id)},
            rates=[], notify_channel="telegram", notify_destination="-100123")
        db.add(order)
        db.flush()
        db.add(AssistantDelivery(event_key=f"freight-recovery:{order.id}:pending", channel="telegram",
            destination="-100123", user_id=uid, text="Pending recovery"))
        db.commit()
    assert worker.process_outbox()
    assert sent == (["Pending recovery"] if change == "none" else [])


def test_postgres_policy_and_recursive_pending_cancellation(pg, monkeypatch):
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app.services.assistant_delivery_policy import delivery_rejection, cancel_pending_dependents
    engine, schema = pg
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(isolated, tables=[m.__table__ for m in
        (Usuario, Vendedor, AssistantIdentity, AssistantMessage, AssistantDelivery, AuditEvent)])
    factory = sessionmaker(bind=isolated, autoflush=False)
    monkeypatch.setattr(settings, "TELEGRAM_GROUP_ID", "-100123")
    try:
        with factory() as db:
            user = Usuario(nome="Fixture", email="outbox-pg@example.test", senha_hash="unused", role=UsuarioRole.GERENTE, sales_scope="own")
            db.add(user)
            db.flush()
            source = incoming(db, user.id, "Old financial request", channel="telegram")
            source.status = "done"
            source.created_at = utcnow() - timedelta(minutes=2)
            db.add(AssistantIdentity(channel="telegram", external_id="123", user_id=user.id, active=True))
            db.add(AuditEvent(action="access_changed", module="usuarios", entity="usuarios", entity_id=str(user.id)))
            parent_id = None
            ids = []
            for n in range(4):
                row = AssistantDelivery(event_key=f"reply:{source.id}" + (f":{n}" if n else ""), user_id=user.id,
                    channel="telegram", destination="-100123", text=f"Part {n}", depends_on_id=parent_id)
                db.add(row)
                db.flush()
                ids.append(row.id)
                parent_id = row.id
            db.commit()
        with factory() as db:
            first = db.get(AssistantDelivery, ids[0])
            assert delivery_rejection(db, first) == "delivery_access_changed"
            first.status = "cancelled"
            cancel_pending_dependents(db, first.id)
            db.commit()
            assert db.query(AssistantDelivery).filter_by(status="cancelled").count() == 4
    finally:
        isolated.dispose()
