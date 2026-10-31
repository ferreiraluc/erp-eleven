"""No live WhatsApp/ERP traffic: bridge authorization, journal and queue regressions."""
import hashlib
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_assistant import setup
from app import assistant_worker as worker
from app.api.endpoints import assistant_whatsapp_bridge as api
from app.config import settings
from app.database import get_db
from app.models.assistant import AssistantDelivery, AssistantIdentity, AssistantMessage, AssistantWhatsAppBridge, utcnow
from app.services import assistant_whatsapp_bridge as service

BASE = "/bridge"
TOKEN = "isolated-bridge-token-" + "x" * 40
SENDER = "whatsapp:+5511888888888"
PRIVATE = "5511888888888@s.whatsapp.net"
GROUP = "120363000000000001@g.us"


@pytest.fixture
def bridge_env(setup):
    factory, _, uid = setup
    with factory() as db:
        db.add(AssistantWhatsAppBridge(id="primary", name="Fixture", enabled=True, state="connected",
            allow_private=True, group_mode="mention", allowed_groups=[GROUP],
            token_hash=hashlib.sha256(TOKEN.encode()).hexdigest()))
        db.add(AssistantIdentity(channel="whatsapp_web", external_id=SENDER, user_id=uid, active=True, can_register=True))
        db.commit()
    app = FastAPI()
    app.include_router(api.router, prefix=BASE)
    def session():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = session
    return factory, TestClient(app), uid, app


def post(client, path, data, token=TOKEN):
    return client.post(BASE + path, json=data, headers={"Authorization": "Bearer " + token})


def incoming(**updates):
    return {"message_id": "3A0001", "conversation_id": PRIVATE, "sender_id": SENDER,
            "text": "/ajuda", "timestamp": utcnow().isoformat(), "should_reply": True, **updates}


def queue(factory, uid, destination=PRIVATE):
    with factory() as db:
        source = AssistantMessage(channel="whatsapp_web", external_id=uuid.uuid4().hex,
            conversation_id=destination, sender_id=SENDER, user_id=uid, text="Ajuda", status="done")
        db.add(source)
        db.flush()
        delivery = AssistantDelivery(event_key=f"reply:{source.id}", channel=source.channel,
            destination=destination, user_id=uid, text="Resposta")
        db.add(delivery)
        db.commit()
        return delivery.id


def test_authentication_and_admin_pairing_are_separate(bridge_env):
    factory, client, _, app = bridge_env
    assert post(client, "/incoming", incoming(), "wrong").status_code == 401
    assert client.get(BASE + "/config").status_code in (401, 403)
    assert client.get(BASE + "/pairing", headers={"Authorization": "Bearer " + TOKEN}).status_code in (401, 403)
    response = post(client, "/heartbeat", {"state": "qr", "qr": "isolated-pairing-code"})
    assert response.status_code == 200
    assert "qr" not in response.json()
    assert response.headers["cache-control"] == "no-store"
    app.dependency_overrides[api.admin.dependency] = lambda: object()
    pair = client.get(BASE + "/pairing")
    assert pair.status_code == 200
    assert pair.json()["qr_image"].startswith("data:image/png;base64,")
    assert "isolated-pairing-code" not in client.get(BASE + "/config").text
    with factory() as db:
        db.get(AssistantWhatsAppBridge, "primary").pairing_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get(BASE + "/pairing").json()["qr_image"] is None
    with factory() as db:
        assert db.get(AssistantWhatsAppBridge, "primary").pairing_qr is None


def test_incoming_authorization_dedup_and_lid_rejection(bridge_env):
    factory, client, _, _ = bridge_env
    for _ in range(2):
        response = post(client, "/incoming", incoming())
        assert response.status_code == 200
        assert response.json()["status"] in ("queued", "duplicate")
    for event in (
        incoming(sender_id="whatsapp:+5511777777777"),
        incoming(conversation_id="5511777777777@s.whatsapp.net"),
        incoming(conversation_id="123456789@lid"),
        incoming(conversation_id="120363000000000099@g.us"),
        incoming(conversation_id=GROUP, should_reply=False),
        incoming(timestamp=(utcnow() - timedelta(hours=25)).isoformat()),
        incoming(timestamp=(utcnow() + timedelta(hours=1)).isoformat()),
    ):
        assert post(client, "/incoming", event).json()["status"] == "ignored"
    assert post(client, "/incoming", incoming(conversation_id=GROUP)).json()["status"] == "queued"
    with factory() as db:
        assert db.query(AssistantMessage).count() == 2
        assert len({row.external_id for row in db.query(AssistantMessage)}) == 2


def test_pause_preserves_queued_messages_and_twilio_identity_does_not_grant_web_access(bridge_env):
    factory, client, _, _ = bridge_env
    with factory() as db:
        db.query(AssistantIdentity).filter_by(channel="whatsapp_web").one().active = False
        db.commit()
    assert post(client, "/incoming", incoming()).json()["status"] == "ignored"
    assert post(client, "/heartbeat", {"state": "connected"}).json()["allowed_senders"] == []
    with factory() as db:
        db.get(AssistantWhatsAppBridge, "primary").enabled = False
        db.commit()
    assert post(client, "/incoming", incoming()).json()["status"] == "paused"


def test_claim_is_recoverable_and_send_requires_one_start(bridge_env):
    factory, client, uid, _ = bridge_env
    key = queue(factory, uid)
    claim = {"claim_key": str(uuid.uuid4())}
    first = post(client, "/claim", claim).json()["delivery"]
    assert first["id"] == str(key) and first["status"] == "claimed"
    assert post(client, "/claim", claim).json()["delivery"] == first
    assert post(client, "/claim", {"claim_key": str(uuid.uuid4())}).json()["delivery"] is None
    assert post(client, f"/deliveries/{key}/ack", {**claim, "status": "accepted", "provider_id": "3ATEST"}).status_code == 409
    assert post(client, f"/deliveries/{key}/start", claim).json()["can_send"] is True
    assert post(client, f"/deliveries/{key}/start", claim).json()["can_send"] is False
    assert worker.process_outbox() is False  # Twilio/Telegram sender never touches bridge claims.
    for _ in range(2):
        result = post(client, f"/deliveries/{key}/ack", {**claim, "status": "accepted", "provider_id": "3ATEST"})
        assert result.status_code == 200 and result.json()["status"] == "accepted"
    assert post(client, f"/deliveries/{key}/ack", {**claim, "status": "accepted", "provider_id": "OTHER"}).status_code == 409


def test_start_rechecks_identity_and_group_after_claim(bridge_env):
    factory, client, uid, _ = bridge_env
    key = queue(factory, uid, GROUP)
    claim = {"claim_key": str(uuid.uuid4())}
    assert post(client, "/claim", claim).json()["delivery"]
    with factory() as db:
        db.get(AssistantWhatsAppBridge, "primary").allowed_groups = []
        db.commit()
    result = post(client, f"/deliveries/{key}/start", claim).json()
    assert result["can_send"] is False and result["status"] == "cancelled"
    key = queue(factory, uid)
    claim = {"claim_key": str(uuid.uuid4())}
    assert post(client, "/claim", claim).json()["delivery"]
    with factory() as db:
        db.query(AssistantIdentity).filter_by(channel="whatsapp_web").one().active = False
        db.commit()
    assert post(client, f"/deliveries/{key}/start", claim).json()["status"] == "cancelled"


def test_uncertain_send_never_repeats_or_releases_dependent_part(bridge_env):
    factory, client, uid, _ = bridge_env
    key = queue(factory, uid)
    with factory() as db:
        parent = db.get(AssistantDelivery, key)
        db.add(AssistantDelivery(event_key=parent.event_key + ":1", channel=parent.channel,
            destination=PRIVATE, user_id=uid, text="Segunda parte", depends_on_id=key))
        db.commit()
    claim = {"claim_key": str(uuid.uuid4())}
    post(client, "/claim", claim)
    post(client, f"/deliveries/{key}/start", claim)
    assert post(client, f"/deliveries/{key}/ack", {**claim, "status": "uncertain", "error_code": "agent_interrupted"}).json()["status"] == "uncertain"
    assert post(client, f"/deliveries/{key}/start", claim).json()["can_send"] is False
    assert post(client, "/claim", {"claim_key": str(uuid.uuid4())}).json()["delivery"] is None
    assert post(client, f"/deliveries/{key}/ack", {**claim, "status": "failed"}).json()["status"] == "uncertain"


def test_worker_uses_existing_assistant_for_web_and_retains_confirmations(bridge_env, monkeypatch):
    factory, client, _, _ = bridge_env
    from app.services.assistant_controls import InteractiveReply
    code = "a:" + uuid.uuid4().hex
    monkeypatch.setattr(worker, "respond", lambda *a: InteractiveReply("Prévia", [[{"text": "Confirmar", "callback_data": code}]]))
    assert post(client, "/incoming", incoming()).json()["status"] == "queued"
    assert worker.process_inbox()
    response = post(client, "/claim", {"claim_key": str(uuid.uuid4())}).json()["delivery"]
    assert "/eleven /acao " + code in response["text"]
    assert response["reply_markup"]


@pytest.mark.parametrize("callback,command", [
    ("a:" + "1" * 32, "/acao a:" + "1" * 32),
    ("c:" + "2" * 32, "/acao c:" + "2" * 32),
    ("v:" + "3" * 32, "/acao v:" + "3" * 32),
    ("q:" + "4" * 32 + ":2", "/servico " + "4" * 32 + ":2"),
    ("p:8", "/previas 8"),
])
def test_every_choice_explicitly_addresses_the_bot_in_mention_only_groups(callback, command):
    delivery = AssistantDelivery(text="Prévia", reply_markup={"inline_keyboard": [[
        {"text": "Escolher", "callback_data": callback},
        {"text": "Inválida", "callback_data": "/arbitrary"},
    ]]})
    assert service._plain_controls(delivery) == (
        "Prévia\n\nEnvie o comando da opção desejada:\nEscolher: /eleven " + command
    )


def test_malformed_payload_does_not_reflect_attachment_or_accept_unknown_fields(bridge_env):
    _, client, _, _ = bridge_env
    result = post(client, "/incoming", incoming(attachment={"mime_type": "secret", "data_base64": "PRIVATE_CONTENT"}))
    assert result.status_code == 422 and "PRIVATE_CONTENT" not in result.text
    assert post(client, "/incoming", incoming(fromMe=True)).status_code == 422


def test_configuration_and_token_rotation_are_admin_only_and_no_store(bridge_env):
    factory, client, _, app = bridge_env
    app.dependency_overrides[api.admin.dependency] = lambda: object()
    result = client.put(BASE + "/config", json={"name": "ERP", "enabled": True, "allowed_groups": [GROUP], "notify_tracking": True})
    assert result.status_code == 200 and result.json()["notify_tracking"] is True
    assert result.json()["credential_configured"] is True
    response = client.post(BASE + "/credential")
    token = response.json()["token"]
    assert response.headers["cache-control"] == "no-store"
    assert token not in client.get(BASE + "/config").text
    with factory() as db:
        assert db.get(AssistantWhatsAppBridge, "primary").token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert post(client, "/heartbeat", {"state": "connected"}).status_code == 401
    assert post(client, "/heartbeat", {"state": "connected"}, token).status_code == 200


@pytest.mark.parametrize("started", [False, True])
def test_rotating_lost_agent_releases_only_unsent_claims(bridge_env, started):
    factory, client, uid, app = bridge_env
    app.dependency_overrides[api.admin.dependency] = lambda: object()
    key = queue(factory, uid)
    claim = {"claim_key": str(uuid.uuid4())}
    post(client, "/claim", claim)
    if started:
        post(client, f"/deliveries/{key}/start", claim)
    token = client.post(BASE + "/credential").json()["token"]
    assert post(client, f"/deliveries/{key}/start", claim).status_code == 401
    with factory() as db:
        delivery = db.get(AssistantDelivery, key)
        assert delivery.status == ("uncertain" if started else "pending")
        assert bool(delivery.bridge_claim_key) is started
    next_claim = post(client, "/claim", {"claim_key": str(uuid.uuid4())}, token).json()["delivery"]
    assert (next_claim is None) is started


def test_same_pairing_qr_does_not_gain_another_minute_on_heartbeat(bridge_env):
    factory, client, _, _ = bridge_env
    payload = {"state": "qr", "qr": "fixture-qr"}
    post(client, "/heartbeat", payload)
    with factory() as db:
        row = db.get(AssistantWhatsAppBridge, "primary")
        row.pairing_expires_at = utcnow() + timedelta(seconds=10)
        expected = row.pairing_expires_at
        db.commit()
    post(client, "/heartbeat", payload)
    with factory() as db:
        assert service.aware(db.get(AssistantWhatsAppBridge, "primary").pairing_expires_at) == expected
        db.get(AssistantWhatsAppBridge, "primary").pairing_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    post(client, "/heartbeat", payload)
    post(client, "/heartbeat", payload)
    with factory() as db:
        assert db.get(AssistantWhatsAppBridge, "primary").pairing_qr is None


def test_new_pairing_command_preserves_messages_and_generation(bridge_env):
    factory, client, uid, app = bridge_env
    app.dependency_overrides[api.admin.dependency] = lambda: object()
    key = queue(factory, uid)
    claim = {"claim_key": str(uuid.uuid4())}
    post(client, "/claim", claim)
    post(client, f"/deliveries/{key}/start", claim)
    result = client.post(BASE + "/session/reset")
    assert result.status_code == 200 and result.json()["session_generation"] == 1
    assert result.json()["account_phone"] is None
    assert result.json()["credential_configured"] is True
    assert post(client, "/heartbeat", {"state": "starting"}).json()["session_generation"] == 1
    with factory() as db:
        assert db.query(AssistantMessage).count() == 1
        assert db.get(AssistantDelivery, key).status == "uncertain"


def test_paused_or_reset_claim_resumes_only_after_reconnection(bridge_env):
    factory, client, uid, app = bridge_env
    app.dependency_overrides[api.admin.dependency] = lambda: object()
    key = queue(factory, uid)
    claim = {"claim_key": str(uuid.uuid4())}
    post(client, "/claim", claim)
    with factory() as db:
        db.get(AssistantWhatsAppBridge, "primary").enabled = False
        db.commit()
    paused = post(client, f"/deliveries/{key}/start", claim).json()
    assert paused == {"can_send": False, "status": "claimed", "error_code": "channel_paused"}
    with factory() as db:
        db.get(AssistantWhatsAppBridge, "primary").enabled = True
        db.commit()
    assert client.post(BASE + "/session/reset").status_code == 200
    assert post(client, "/claim", claim).json()["delivery"]["claim_key"] == claim["claim_key"]
    assert post(client, f"/deliveries/{key}/start", claim).json() == paused
    post(client, "/heartbeat", {"state": "connected"})
    assert post(client, f"/deliveries/{key}/start", claim).json()["can_send"] is True
    assert post(client, f"/deliveries/{key}/start", claim).json()["can_send"] is False


def test_document_is_fetched_only_by_existing_safe_provider_and_text_is_separate(bridge_env, monkeypatch):
    from app.services.assistant_replies import DocumentReply
    from app.services import superfrete
    factory, client, _, _ = bridge_env
    url = "https://api.superfrete.com/fixture.pdf"
    monkeypatch.setattr(superfrete, "safe_label", lambda value: value if value == url else None)
    monkeypatch.setattr(superfrete, "label_pdf", lambda value: b"%PDF-isolated")
    monkeypatch.setattr(worker, "respond", lambda *args: DocumentReply("Detalhes " * 200, url))
    post(client, "/incoming", incoming())
    assert worker.process_inbox()
    claim = {"claim_key": str(uuid.uuid4())}
    payload = post(client, "/claim", claim).json()["delivery"]
    assert payload["text"] == "Documento do ERP."
    assert payload["document_url"] is None and payload["document_pdf_base64"]
    with factory() as db:
        delivery = db.get(AssistantDelivery, uuid.UUID(payload["id"]))
        parts = db.query(AssistantDelivery).filter(AssistantDelivery.id != delivery.id).all()
        assert sum(len(part.text) for part in parts) >= 1590
        assert any(part.depends_on_id == delivery.id for part in parts)
