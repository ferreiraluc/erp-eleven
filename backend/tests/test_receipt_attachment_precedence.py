"""Regression for receipt media selection; providers and persistence are isolated."""
import pytest

from test_assistant import setup, telegram_update
from test_address_manager import env

from app.models import Rastreamento
from app.models.assistant import AssistantAction, AssistantMessage
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services import receipt_tracking as receipts
from app.services.receipt_vision import ReceiptObject


def add_media(message, media, prefix):
    if media == "photo":
        message["photo"] = [{"file_id": prefix, "width": 1200, "height": 1800}]
    else:
        mime = {"png": "image/png", "jpg": "image/jpeg", "pdf": "application/pdf"}[media]
        message["document"] = {
            "file_id": prefix, "mime_type": mime, "file_name": "comprovante." + media,
        }


def replied_update(current_media, previous_media, *, previous_sender="123", chat="-100123"):
    update = telegram_update(text="Cadastre os rastreios deste comprovante", update_id=912, chat=chat)
    message = update["message"]
    message["message_thread_id"] = 19
    if current_media:
        add_media(message, current_media, "current-file")
    previous = telegram_update(text="Comprovante anterior", update_id=911,
                               sender=previous_sender, chat=chat)["message"]
    previous["message_thread_id"] = 19
    add_media(previous, previous_media, "previous-file")
    message["reply_to_message"] = previous
    return update


@pytest.fixture
def fake_vision(monkeypatch):
    downloaded = []

    def download(attachment):
        downloaded.append(attachment["file_id"])
        return attachment["file_id"].encode()

    def extract(content):
        return [ReceiptObject(
            codigo="RR123456785BR" if content == b"current-file" else "RR473124829BR",
            destinatario="Comprovante atual" if content == b"current-file" else "Comprovante anterior",
        )]

    def no_text_provider(*args, **kwargs):
        raise AssertionError("A receipt request must not reach the text provider")

    monkeypatch.setattr(receipts, "download_image", download)
    monkeypatch.setattr(receipts, "extract_receipt", extract)
    monkeypatch.setattr(agent, "complete", no_text_provider)
    return downloaded


@pytest.mark.parametrize("current_media", ["photo", "png", "jpg"])
@pytest.mark.parametrize("previous_media", ["photo", "png", "pdf"])
def test_new_receipt_media_takes_precedence_over_replied_attachment(env, fake_vision, current_media, previous_media):
    factory, _, _, _ = env
    update = replied_update(current_media, previous_media)
    with factory() as db:
        assert channels.enqueue_incoming(db, channels.telegram_message(update)) == "queued"
        db.commit()
        received = db.query(AssistantMessage).filter_by(external_id="912").one()
        assert received.conversation_id == "-100123:19"
        identity = channels.authorized_identity(db, received.channel, received.sender_id)
        response = agent.respond(db, received, identity)
        assert "Conferir comprovante" in response
        assert db.query(Rastreamento).count() == 0
        assert fake_vision == ["current-file"]
        action = db.query(AssistantAction).one()
        assert action.payload["objetos"][0]["codigo"] == "RR123456785BR"
        assert action.payload["objetos"][0]["destinatario"] == "Comprovante atual"


@pytest.mark.parametrize("previous_media", ["photo", "png", "pdf"])
def test_current_pdf_remains_a_pdf_when_replying_to_prior_media(setup, previous_media):
    parsed = channels.telegram_message(replied_update("pdf", previous_media))
    assert parsed.attachment["file_id"] == "current-file"
    assert parsed.attachment["mime_type"] == "application/pdf"
    assert parsed.attachment.get("kind") != "image"
    assert parsed.conversation_id == "-100123:19"


@pytest.mark.parametrize("previous_media", ["photo", "png"])
def test_attachment_free_reply_to_own_receipt_still_prepares_original_image(env, fake_vision, previous_media):
    factory, _, _, _ = env
    with factory() as db:
        update = replied_update(None, previous_media)
        assert channels.enqueue_incoming(db, channels.telegram_message(update)) == "queued"
        db.commit()
        received = db.query(AssistantMessage).filter_by(external_id="912").one()
        identity = channels.authorized_identity(db, received.channel, received.sender_id)
        response = agent.respond(db, received, identity)
        assert "Conferir comprovante" in response
        assert fake_vision == ["previous-file"]
        assert db.query(Rastreamento).count() == 0
        assert received.conversation_id == "-100123:19"
        action = db.query(AssistantAction).one()
        assert action.user_id == received.user_id
        assert action.payload["objetos"][0]["codigo"] == "RR473124829BR"


@pytest.mark.parametrize("previous_media", ["photo", "png", "pdf"])
def test_attachment_free_reply_never_inherits_another_persons_media(setup, previous_media):
    parsed = channels.telegram_message(replied_update(None, previous_media, previous_sender="999"))
    assert parsed.attachment is None
    assert parsed.sender_id == "123"
    assert parsed.conversation_id == "-100123:19"


def test_attachment_free_reply_to_own_pdf_keeps_file_printing_contract(setup):
    parsed = channels.telegram_message(replied_update(None, "pdf"))
    assert parsed.attachment["file_id"] == "previous-file"
    assert parsed.attachment["mime_type"] == "application/pdf"


@pytest.mark.parametrize("current_media", [None, "photo", "png", "pdf"])
def test_reply_media_does_not_bypass_configured_group(setup, current_media):
    assert channels.telegram_message(replied_update(current_media, "png", chat="-100999")) is None


@pytest.mark.parametrize("current_media", ["photo", "png"])
def test_new_media_is_owned_by_current_sender_even_when_replying_to_someone_else(setup, current_media):
    parsed = channels.telegram_message(replied_update(current_media, "png", previous_sender="999"))
    assert parsed.attachment["file_id"] == "current-file"
    assert parsed.sender_id == "123"
