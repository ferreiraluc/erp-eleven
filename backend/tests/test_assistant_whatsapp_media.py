"""WhatsApp media/operational flows with isolated storage and no external sends."""
import io
import base64
import json
import uuid
from datetime import timedelta

import pytest
from PIL import Image

from test_address_manager import env
from test_assistant import setup
from test_assistant_workflows import pdf_bytes
from test_assistant_queries import shipment
from test_whatsapp_bridge import bridge_env, incoming as bridge_incoming, post as bridge_post
from app.config import settings
from app.database import Base
from app.models.assistant import AssistantAction, AssistantDelivery, AssistantIdentity, AssistantMessage, AssistantWhatsAppBridge, utcnow
from app.models.assistant_whatsapp_media import WhatsAppMedia
from app.models.address_book import FreightOrder
from app.models.printing import PrintJob
from app.services import assistant_documents as documents, assistant_whatsapp_media as media
from app.services import freight_labels, freight_recovery, receipt_tracking, receipt_vision
from app.services.assistant_schedule import confirm_action

GROUP = "120363000000001@g.us"
PHONE = "whatsapp:+5511888888888"


@pytest.fixture
def whatsapp(env):
    factory, client, uid, device = env
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[WhatsAppMedia.__table__, AssistantWhatsAppBridge.__table__])
        db.add(AssistantWhatsAppBridge(id="primary", enabled=True, allowed_groups=[GROUP]))
        db.add(AssistantIdentity(channel="whatsapp_web", external_id=PHONE, user_id=uid, can_register=True))
        db.commit()
    return factory, uid


def message(db, uid, text="Imprima este PDF", *, conversation=GROUP):
    value = AssistantMessage(channel="whatsapp_web", external_id=uuid.uuid4().hex,
        conversation_id=conversation, sender_id=PHONE, user_id=uid, text=text, should_reply=True)
    db.add(value)
    db.flush()
    return value


def identity(db, uid):
    return db.query(AssistantIdentity).filter_by(user_id=uid, channel="whatsapp_web").one()


def attach(db, msg, data=None, mime="application/pdf"):
    msg.attachment = media.ingest_media(db, user_id=msg.user_id, conversation_id=msg.conversation_id,
        message_external_id=msg.external_id, content=data or pdf_bytes(), mime_type=mime)
    db.flush()
    return msg.attachment


def photo_bytes():
    out = io.BytesIO()
    Image.new("RGB", (64, 96), "white").save(out, "PNG")
    return out.getvalue()


def test_storage_reference_binds_author_conversation_expiry_and_hash(whatsapp):
    factory, uid = whatsapp
    with factory() as db:
        msg = message(db, uid)
        payload = pdf_bytes()
        ref = attach(db, msg, payload)
        assert set(ref) == {"provider", "media_id", "kind", "mime_type", "size", "name"}
        assert "base64" not in json.dumps(ref) and "file_id" not in ref
        assert media.read_media(db, ref, user_id=uid, conversation_id=GROUP) == payload
        for user, conversation in ((uuid.uuid4(), GROUP), (uid, "other@g.us")):
            with pytest.raises(ValueError, match="usuário e conversa"):
                media.read_media(db, ref, user_id=user, conversation_id=conversation)
        stored = db.query(WhatsAppMedia).one()
        stored.data = b"tampered"
        db.flush()
        with pytest.raises(ValueError, match="integridade"):
            media.read_media(db, ref, user_id=uid, conversation_id=GROUP)
        stored.expires_at = utcnow() - timedelta(seconds=1)
        db.flush()
        with pytest.raises(ValueError, match="expirou"):
            media.read_media(db, ref, user_id=uid, conversation_id=GROUP)
        assert db.query(WhatsAppMedia).count() == 0


def test_incoming_checks_identity_before_storing_media_and_never_embeds_bytes(bridge_env):
    factory, client, uid, _ = bridge_env
    encoded = base64.b64encode(pdf_bytes()).decode("ascii")
    attachment = {"mime_type": "application/pdf", "data_base64": encoded}
    unauthorized = bridge_incoming(sender_id="whatsapp:+5511777777777",
        conversation_id="5511777777777@s.whatsapp.net", attachment=attachment)
    assert bridge_post(client, "/incoming", unauthorized).json()["status"] == "ignored"
    with factory() as db:
        assert db.query(WhatsAppMedia).count() == 0
    request = bridge_incoming(text="", attachment=attachment)
    assert bridge_post(client, "/incoming", request).json()["status"] == "queued"
    assert bridge_post(client, "/incoming", request).json()["status"] == "duplicate"
    with factory() as db:
        assert db.query(WhatsAppMedia).count() == 1
        stored = db.query(AssistantMessage).one()
        assert stored.user_id == uid and stored.attachment["provider"] == "whatsapp_web"
        assert encoded not in json.dumps(stored.attachment) and encoded not in stored.text


def test_ingestion_deduplicates_validates_bytes_and_enforces_bounded_storage(whatsapp, monkeypatch):
    factory, uid = whatsapp
    with factory() as db:
        msg = message(db, uid)
        payload = pdf_bytes()
        first = attach(db, msg, payload)
        assert attach(db, msg, payload) == first and db.query(WhatsAppMedia).count() == 1
        with pytest.raises(ValueError, match="original"):
            media.ingest_media(db, user_id=uid, conversation_id="other@g.us",
                message_external_id=msg.external_id, content=payload, mime_type="application/pdf")
        monkeypatch.setattr(media, "USER_BYTES", len(payload))
        with pytest.raises(ValueError, match="Limite temporário"):
            attach(db, message(db, uid), payload)
        monkeypatch.setattr(media, "USER_BYTES", 25 * 1024 * 1024)
        monkeypatch.setattr(media, "GLOBAL_BYTES", len(payload))
        with pytest.raises(ValueError, match="Limite temporário"):
            attach(db, message(db, uid), payload)
        for data, mime in ((b"%PDF-fake", "application/pdf"), (b"image", "image/jpeg"),
                           (b"<svg/>", "image/svg+xml"), (b"x" * (media.MAX_BYTES + 1), "application/pdf")):
            with pytest.raises(ValueError):
                attach(db, message(db, uid), data, mime)
        db.query(WhatsAppMedia).update({"expires_at": utcnow() - timedelta(seconds=1)})
        assert attach(db, message(db, uid), payload)
        assert db.query(WhatsAppMedia).count() == 1


def test_photo_normalizes_to_jpeg_and_receipt_discards_bytes_after_preview(whatsapp, monkeypatch):
    factory, uid = whatsapp
    monkeypatch.setattr(receipt_tracking, "extract_receipt", lambda data: [
        receipt_vision.ReceiptObject(codigo="RR473124829BR", destinatario="Maria Teste")])
    with factory() as db:
        msg = message(db, uid, "Cadastre os rastreios deste comprovante")
        attach(db, msg, photo_bytes(), "image/png")
        stored = db.query(WhatsAppMedia).one()
        assert stored.data.startswith(b"\xff\xd8") and stored.mime_type == "image/jpeg"
        result = receipt_tracking.prepare_receipt(db, msg, identity(db, uid), receipt_tracking.ReceiptArgs())
        assert "confirmacao" in result and "RR473124829BR" in result["confirmacao"]
        assert msg.attachment is None and db.query(WhatsAppMedia).count() == 0
        assert db.query(AssistantAction).one().status == "draft"


def test_receipt_cannot_borrow_other_author_or_conversation_media(whatsapp):
    factory, uid = whatsapp
    with factory() as db:
        source = message(db, uid, "Foto")
        attach(db, source, photo_bytes(), "image/png")
        followup = message(db, uid, "Cadastre os rastreios deste comprovante", conversation="other@g.us")
        result = receipt_tracking.prepare_receipt(db, followup, identity(db, uid), receipt_tracking.ReceiptArgs(mensagem_id=source.id))
        assert "erro" in result and db.query(AssistantAction).count() == 0


def test_pdf_print_uses_confirmed_reference_and_download_checks_original_hash(whatsapp):
    factory, uid = whatsapp
    with factory() as db:
        source = message(db, uid)
        payload = pdf_bytes()
        attach(db, source, payload)
        result = documents.prepare_file(db, source, identity(db, uid), documents.FilePrintArgs())
        assert "temporariamente" in result["confirmacao"] and db.query(PrintJob).count() == 0
        action = db.query(AssistantAction).one()
        confirm = message(db, uid, "confirmo")
        assert "PDF encaminhado" in confirm_action(db, confirm, identity(db, uid), action)
        job = db.query(PrintJob).one()
        assert not job.pdf and source.attachment is None and "whatsapp_file" in job.snapshot
        assert documents.ephemeral_pdf(job) == payload
        assert "Nenhuma alteração" in confirm_action(db, confirm, identity(db, uid), action)
        assert db.query(PrintJob).count() == 1
        job.sha256 = "bad-hash"
        with pytest.raises(ValueError, match="diferente"):
            documents.ephemeral_pdf(job)
        job.sha256 = db.query(WhatsAppMedia).one().sha256
        job.snapshot = {**job.snapshot, "conversation_id": "other@g.us"}
        with pytest.raises(ValueError, match="Origem"):
            documents.ephemeral_pdf(job)


def test_expired_media_does_not_enqueue_print_and_cleanup_runs_when_paused(whatsapp):
    factory, uid = whatsapp
    with factory() as db:
        source = message(db, uid)
        attach(db, source)
        assert "confirmacao" in documents.prepare_file(db, source, identity(db, uid), documents.FilePrintArgs())
        action = db.query(AssistantAction).one()
        stored = db.query(WhatsAppMedia).one()
        stored.expires_at = utcnow() - timedelta(seconds=1)
        db.flush()
        assert "expirou" in confirm_action(db, message(db, uid, "confirmo"), identity(db, uid), action)
        assert db.query(PrintJob).count() == 0
        db.get(AssistantWhatsAppBridge, "primary").enabled = False
        documents.cleanup_documents(db)
        assert db.query(WhatsAppMedia).count() == 0


def test_freight_pdf_and_recovery_stay_in_original_whatsapp_conversation(whatsapp):
    factory, uid = whatsapp
    with factory() as db:
        source = message(db, uid, "Cote um envio")
        row = FreightOrder(request_key=source.id, user_id=uid, environment="sandbox", state="quoted",
            payload={"to": {"name": "Cliente Teste"}, "from": {"name": "Loja Teste"}},
            rates=[{"id": 1, "price": 20, "name": "PAC"}])
        db.add(row)
        db.flush()
        freight_labels.watch_label(db, row, message=source)
        assert row.notify_channel == "whatsapp_web" and row.notify_destination == GROUP
        freight_recovery.notify(db, row, "quoted")
        row.label_pdf = pdf_bytes()
        freight_labels.notify_pdf(db, row, False)
        db.flush()
        deliveries = db.query(AssistantDelivery).all()
        assert len(deliveries) == 2
        assert all(d.channel == "whatsapp_web" and d.destination == GROUP and d.user_id == uid for d in deliveries)
        assert any(d.document_pdf == row.label_pdf for d in deliveries)
        freight_labels.notify_pdf(db, row, False)
        db.flush()
        assert db.query(AssistantDelivery).count() == 2
        db.get(AssistantWhatsAppBridge, "primary").allowed_groups = []
        freight_labels.notify_pdf(db, row, True)
        db.flush()
        assert db.query(AssistantDelivery).count() == 2


def test_tracking_broadcast_is_opt_in_ordered_and_idempotent(whatsapp, monkeypatch):
    factory, uid = whatsapp
    monkeypatch.setattr(settings, "ASSISTANT_TELEGRAM_ENABLED", False)
    with factory() as db:
        shipment(db, "RR473124829BR")
        assert db.query(AssistantDelivery).count() == 0
        bridge = db.get(AssistantWhatsAppBridge, "primary")
        bridge.notify_tracking = True
        db.flush()
        tracked = shipment(db, "RR123456785BR", name="Cliente Teste")
        rows = db.query(AssistantDelivery).filter_by(channel="whatsapp_web").all()
        assert len(rows) == 2
        code = next(row for row in rows if not row.depends_on_id)
        details = next(row for row in rows if row.depends_on_id)
        assert code.text == "RR123456785BR" and details.depends_on_id == code.id
        assert "Cliente Teste" in details.text and details.destination == code.destination == GROUP
        assert all(row.user_id is None and row.event_key.startswith("tracking:whatsapp_web:") for row in rows)
        tracked.status = "ENTREGUE"
        db.flush()
        assert db.query(AssistantDelivery).count() == 2
        tracked.codigo_rastreio = " RR123456785BR "
        db.flush()
        assert db.query(AssistantDelivery).count() == 2
        bridge.enabled = False
        db.flush()
        shipment(db, "RR000000005BR")
        assert db.query(AssistantDelivery).count() == 2
