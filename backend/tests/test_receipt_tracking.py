"""Receipt regression tests use SQLite and stubbed providers; no files or messages sent."""
import io
import json
import uuid
from datetime import timedelta

import pytest
from PIL import Image

from test_assistant import incoming, setup, telegram_update
from test_address_manager import env
from app.config import settings
from app.models import Cliente, Pedido, Rastreamento, Usuario
from app.models.assistant import AssistantAction, AssistantMessage, utcnow
from app.models.usuario import UsuarioRole
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services import receipt_tracking as receipts, receipt_vision as vision
from app.services.assistant_schedule import confirm_action

FIRST = "RR473124829BR"
SECOND = "RR123456785BR"


def image_bytes():
    output = io.BytesIO()
    Image.new("RGB", (64, 96), "white").save(output, "PNG")
    return output.getvalue()


def attachment():
    return {"kind": "image", "file_id": "test-receipt", "name": "Imagem recebida", "mime_type": "image/jpeg", "size": 1000}


def identity(db, msg):
    return channels.authorized_identity(db, msg.channel, msg.sender_id)


def photo_message(db, uid, text="Cadastre os rastreios deste comprovante"):
    message = incoming(db, uid, text, channel="telegram")
    message.attachment = attachment()
    db.flush()
    return message


@pytest.fixture
def extracted(monkeypatch):
    items = [vision.ReceiptObject(codigo=FIRST, destinatario="Maria Teste", cidade="Curitiba", uf="PR")]
    monkeypatch.setattr(receipts, "download_image", lambda value: b"image-test")
    monkeypatch.setattr(receipts, "extract_receipt", lambda value: list(items))
    return items


def test_telegram_images_select_largest_and_do_not_copy_another_persons_photo(setup):
    update = telegram_update(text="")
    update["message"]["photo"] = [
        {"file_id": "small", "width": 64, "height": 64},
        {"file_id": "large", "width": 1200, "height": 1400, "file_size": 2000},
    ]
    parsed = channels.telegram_message(update)
    assert parsed.attachment["file_id"] == "large" and parsed.attachment["kind"] == "image"
    assert parsed.text.startswith("[Imagem recebida:")
    own = telegram_update(text="Cadastre os rastreios deste comprovante")
    own["message"]["reply_to_message"] = update["message"]
    assert channels.telegram_message(own).attachment["file_id"] == "large"
    own["message"]["reply_to_message"]["from"]["id"] = 999
    assert channels.telegram_message(own).attachment is None
    update = telegram_update(text="Cadastre este comprovante")
    update["message"]["document"] = {"file_id": "png-document", "mime_type": "image/png", "file_name": "personal-name.png"}
    parsed = channels.telegram_message(update)
    assert parsed.attachment["kind"] == "image" and "personal-name" not in json.dumps(parsed.attachment)


def test_code_validation_never_repairs_or_accepts_unreadable_digits():
    assert vision.tracking_code("rr 473 124 829 br") == FIRST
    for invalid in ("RR473124828BR", "RR47312482?BR", "RR47312482OBR", "RR473124829B", "RR-473124829-BR"):
        with pytest.raises(ValueError):
            vision.tracking_code(invalid)
    assert vision.tracking_code("RR000000005BR") == "RR000000005BR"  # modulus result 11 -> 5
    assert vision.tracking_code("RR000000080BR") == "RR000000080BR"  # modulus result 10 -> 0


def test_ocr_schema_blocks_partial_batches_extra_fields_and_conflicting_duplicates():
    one = {"codigo": FIRST, "destinatario": "Maria Teste"}
    assert len(vision.parse_extraction(json.dumps({"leitura_completa": True, "objetos": [one, one]}))) == 1
    invalid = [
        {"objetos": []},
        {"objetos": [one, {"codigo": "RR47312482?BR"}]},
        {"objetos": [{**one, "cpf": "sensitive-not-supported"}]},
        {"objetos": [one, {**one, "destinatario": "Outro Nome"}]},
        {"objetos": [{**one, "uf": "ZZ"}]},
        {"leitura_completa": False, "objetos": [one]},
    ]
    for data in invalid:
        with pytest.raises(vision.ReceiptError):
            vision.parse_extraction(json.dumps({"leitura_completa": True, **data}))
    with pytest.raises(vision.ReceiptError):
        vision.parse_extraction(json.dumps({"objetos": [one]}))


def test_image_validation_checks_bytes_dimensions_and_animation():
    normalized = vision.validate_image(image_bytes())
    assert normalized.startswith(b"\xff\xd8")
    for data in (b"%PDF-1.5", b"image.jpg", b"x" * (vision.MAX_BYTES + 1)):
        with pytest.raises(vision.ReceiptError):
            vision.validate_image(data)
    tiny = io.BytesIO()
    Image.new("RGB", (8, 8)).save(tiny, "PNG")
    with pytest.raises(vision.ReceiptError):
        vision.validate_image(tiny.getvalue())
    gif = io.BytesIO()
    Image.new("RGB", (64, 64)).save(gif, "GIF")
    with pytest.raises(vision.ReceiptError):
        vision.validate_image(gif.getvalue())


def test_download_rejects_redirect_paths_and_stream_overflow(setup, monkeypatch):
    result = {"file_path": "photos/file_test.jpg", "file_size": 10}
    payload = image_bytes()
    calls = []
    class Response:
        status_code = 200
        def json(self): return {"result": result}
        def iter_content(self, size): yield payload
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def request(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr(vision.requests, "post", request)
    monkeypatch.setattr(vision.requests, "get", request)
    assert vision.download_image(attachment()) == payload
    assert all(not kwargs["allow_redirects"] for _, kwargs in calls)
    assert calls[-1][1]["stream"]
    for path in ("https://other.example/secret", "../secret", "/file.jpg"):
        result["file_path"] = path
        with pytest.raises(vision.ReceiptError):
            vision.download_image(attachment())
    result["file_path"] = "photos/file_test.jpg"
    payload = b"x" * (vision.MAX_BYTES + 1)
    with pytest.raises(vision.ReceiptError):
        vision.download_image(attachment())


def test_vision_client_is_bounded_json_only_and_does_not_expose_provider_exception(monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "anthropic")
    import anthropic
    captured = {}
    class Block:
        type = "text"
        text = json.dumps({"leitura_completa": True, "objetos": [{"codigo": FIRST}]})
    class Response:
        content = [Block()]
    class Client:
        def __init__(self, **kwargs):
            captured["options"] = kwargs
            self.messages = self
        def create(self, **kwargs):
            captured["request"] = kwargs
            return Response()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setattr(anthropic, "Anthropic", Client)
    assert vision.extract_receipt(image_bytes())[0].codigo == FIRST
    assert captured["options"]["max_retries"] == 0 and captured["options"]["timeout"] == 35
    assert captured["request"]["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"
    assert "tools" not in captured["request"] and "não confiável" in captured["request"]["system"]
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with pytest.raises(vision.ReceiptError, match="ANTHROPIC_API_KEY"):
        vision.extract_receipt(image_bytes())
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-only")
    def broken(**kwargs): raise RuntimeError("Secret provider details")
    monkeypatch.setattr(anthropic, "Anthropic", broken)
    with pytest.raises(vision.ReceiptError) as error:
        vision.extract_receipt(image_bytes())
    assert "Secret" not in str(error.value)


def test_prepare_and_confirm_receipt_once_without_persisting_image(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        msg = photo_message(db, uid)
        result = receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        assert "Conferir comprovante" in result["confirmacao"] and result["confirmacao"].reply_markup
        assert db.query(Rastreamento).count() == 0 and msg.attachment is None
        action = db.query(AssistantAction).one()
        assert "file_id" not in json.dumps(action.payload) and "image-test" not in json.dumps(action.payload)
        assert "destinatario" in action.payload["objetos"][0]
        again = receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        assert "confirmacao" in again and db.query(AssistantAction).count() == 1
        confirmation = incoming(db, uid, "confirmo", channel="telegram")
        response = confirm_action(db, confirmation, identity(db, confirmation), action)
        assert "1 rastreio(s) cadastrado(s)" in response
        shipment = db.query(Rastreamento).one()
        assert shipment.codigo_rastreio == FIRST and shipment.created_by == uid
        assert shipment.status.value == "PENDENTE" and shipment.destino == "Curitiba / PR"
        assert not shipment.pedido_id and not shipment.cliente_id
        confirm_action(db, confirmation, identity(db, confirmation), action)
        assert db.query(Rastreamento).count() == 1


def test_duplicate_legacy_inactive_code_is_not_reactivated_or_overwritten(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        existing = Rastreamento(codigo_rastreio="rr 473124829 br", destinatario="Original", ativo=False)
        db.add(existing)
        db.flush()
        msg = photo_message(db, uid)
        result = receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        assert "já estão no ERP" in result["erro"] and msg.attachment is None
        assert db.query(AssistantAction).count() == 0
        assert existing.destinatario == "Original" and not existing.ativo


def test_duplicate_added_after_preview_is_skipped_without_changing_owner(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        msg = photo_message(db, uid)
        receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        action = db.query(AssistantAction).one()
        db.add(Rastreamento(codigo_rastreio=FIRST, destinatario="Already saved"))
        db.flush()
        assert "0 rastreio(s) cadastrado(s)" in confirm_action(db, msg, identity(db, msg), action)
        assert db.query(Rastreamento).one().destinatario == "Already saved"
        assert action.status == "executed"


def test_photo_requires_direct_intent_and_registration_permission(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        for prompt in ("Olá", "Não cadastre esse comprovante", "Só guarde a imagem"):
            msg = photo_message(db, uid, prompt)
            assert "erro" in receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        msg = photo_message(db, uid)
        identity(db, msg).can_register = False
        assert "erro" in receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        identity(db, msg).can_register = True
        db.get(Usuario, uid).role = UsuarioRole.VENDEDOR
        assert "erro" in receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        assert db.query(AssistantAction).count() == 0


def test_photo_selection_is_scoped_to_author_conversation_channel_and_expiry(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        other = Usuario(nome="Other", email="other-receipt@example.test", senha_hash="test", role=UsuarioRole.GERENTE)
        db.add(other)
        db.flush()
        source = photo_message(db, other.id)
        msg = incoming(db, uid, "Cadastre os rastreios deste comprovante", channel="telegram")
        assert "erro" in receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs(mensagem_id=source.id))
        source.user_id = uid
        source.conversation_id = "-100123:5"
        db.flush()
        assert "erro" in receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs(mensagem_id=source.id))
        source.conversation_id = msg.conversation_id
        source.created_at = utcnow() - timedelta(hours=25)
        db.flush()
        assert "erro" in receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs(mensagem_id=source.id))
        whatsapp = incoming(db, uid, "Cadastre os rastreios deste comprovante")
        assert "erro" in receipts.prepare_receipt(db, whatsapp, identity(db, whatsapp), receipts.ReceiptArgs())


def test_confirm_checks_conversation_identity_and_expiry(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        msg = photo_message(db, uid)
        receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        action = db.query(AssistantAction).one()
        confirmation = incoming(db, uid, "confirmo", channel="telegram")
        confirmation.conversation_id = "-100123:3"
        assert "mesma conversa" in confirm_action(db, confirmation, identity(db, confirmation), action)
        confirmation.conversation_id = msg.conversation_id
        action.created_at = utcnow() - timedelta(hours=25)
        assert "expirada" in confirm_action(db, confirmation, identity(db, confirmation), action)
        assert db.query(Rastreamento).count() == 0


def test_exact_single_order_is_proposed_and_customer_inherited_only_on_confirm(env, extracted, monkeypatch):
    factory, _, uid, _ = env
    with factory() as db:
        customer = Cliente(nome="Maria Teste")
        db.add(customer)
        db.flush()
        order = Pedido(numero_pedido="TEST-1", descricao="Test", valor_total=1, cliente_nome="Maria Teste", cliente_id=customer.id)
        db.add(order)
        db.flush()
        msg = photo_message(db, uid)
        with monkeypatch.context() as preview_patch:
            def no_link_locks(*args, **kwargs):
                raise AssertionError("A preview must not acquire order locks")
            preview_patch.setattr(receipts, "validate_tracking_links", no_link_locks)
            result = receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        assert "Pedido: TEST-1" in result["confirmacao"] and "Confira o vínculo" in result["confirmacao"]
        assert "Cliente vinculado: Maria Teste" in result["confirmacao"]
        assert not order.codigo_rastreio
        action = db.query(AssistantAction).one()
        confirm_action(db, msg, identity(db, msg), action)
        shipment = db.query(Rastreamento).one()
        assert shipment.pedido_id == order.id and shipment.cliente_id == customer.id
        assert order.codigo_rastreio == FIRST
        assert order.status.value == "PENDENTE"  # OCR is not evidence of a transport event.


def test_ambiguous_name_never_selects_first_order(env, extracted):
    factory, _, uid, _ = env
    with factory() as db:
        for n in (1, 2):
            db.add(Pedido(numero_pedido=f"TEST-{n}", descricao="Test", valor_total=1, cliente_nome="Maria Teste"))
        db.flush()
        msg = photo_message(db, uid)
        result = receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        assert "vários pedidos" in result["confirmacao"]
        action = db.query(AssistantAction).one()
        confirm_action(db, msg, identity(db, msg), action)
        assert db.query(Rastreamento).one().pedido_id is None


def test_changed_order_aborts_whole_batch_and_multiple_packages_keep_same_link(env, extracted):
    factory, _, uid, _ = env
    extracted.append(vision.ReceiptObject(codigo=SECOND, destinatario="Maria Teste"))
    with factory() as db:
        order = Pedido(numero_pedido="TEST-1", descricao="Test", valor_total=1, cliente_nome="Maria Teste")
        db.add(order)
        db.flush()
        msg = photo_message(db, uid)
        receipts.prepare_receipt(db, msg, identity(db, msg), receipts.ReceiptArgs())
        action = db.query(AssistantAction).one()
        order.cliente_nome = "Another person"
        assert "mudou" in confirm_action(db, msg, identity(db, msg), action)
        assert db.query(Rastreamento).count() == 0
        order.cliente_nome = "Maria Teste"
        assert "2 rastreio(s)" in confirm_action(db, msg, identity(db, msg), action)
        assert {row.pedido_id for row in db.query(Rastreamento).all()} == {order.id}
        assert order.codigo_rastreio == FIRST


def test_caption_and_followup_use_receipt_flow_without_deepseek(env, extracted, monkeypatch):
    factory, _, uid, _ = env
    def no_llm(*args, **kwargs): raise AssertionError("Receipt dispatch must not depend on text LLM")
    monkeypatch.setattr(agent, "complete", no_llm)
    with factory() as db:
        photo = photo_message(db, uid, "[Imagem recebida: foto para conferência]")
        assert "Foto recebida" in agent.respond(db, photo, identity(db, photo))
        assert db.query(AssistantAction).count() == 0
        photo.status = "done"
        photo.response = "Foto recebida."
        db.flush()
        followup = incoming(db, uid, "Cadastre os rastreios deste comprovante", channel="telegram")
        answer = agent.respond(db, followup, identity(db, followup))
        assert "Conferir comprovante" in answer and answer.reply_markup
        assert db.query(Rastreamento).count() == 0
