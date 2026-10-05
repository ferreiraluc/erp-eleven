"""Optional Paraguay documents keep their text and legacy cpf storage key."""
from copy import deepcopy
from io import BytesIO
import uuid

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from test_address_manager import env, setup
from test_assistant import incoming
from app.models.assistant import AssistantAction, AssistantIdentity
from app.models.printing import PrintJob
from app.schemas.address_book import AddressData
from app.services.assistant_printing import AddressArgs, render_address, print_preview, prepare_print


def pdf_text(content):
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) == 1
    return reader.pages[0].extract_text()


@pytest.mark.parametrize("document", ["80012345-6", "4.567.890", "A-123.456"])
def test_py_document_survives_validation_preview_and_a4_without_cpf_rules(document):
    address = AddressArgs(pais="PY", nome="Cliente sintético", cidade="Asunción", cpf=document)
    assert address.cpf == document and address.endereco == "" and address.remetente is None
    assert AddressData(**{key: value for key, value in address.model_dump().items() if key != "remetente"}).cpf == document
    payload = {"endereco": address.model_dump(), "remetente": None}
    original = deepcopy(payload)
    text = pdf_text(render_address(payload))
    assert "RUC/C.I: " + document in text
    assert "CPF" not in text and "REMETENTE" not in text
    preview = print_preview(AssistantAction(id=uuid.uuid4(), kind="impressao", payload=payload))
    assert "RUC/C.I do destinatário: " + document in preview
    assert "CPF" not in preview
    assert payload == original


def test_py_document_is_optional_and_keeps_the_saved_layout_field_order():
    address = AddressArgs(pais="PY", nome="Nome sintético", cidade="Asunción", cpf="A-123.456")
    payload = {"endereco": address.model_dump(), "remetente": None, "layout": {"fields": ["cpf", "nome", "cidade"]}}
    text = pdf_text(render_address(payload))
    assert text.index("RUC/C.I") < text.index("Nome sintético")
    payload["layout"]["fields"] = ["nome", "cidade"]
    assert "RUC/C.I" not in pdf_text(render_address(payload))
    assert payload["endereco"]["cpf"] == "A-123.456"  # hiding a layout field never deletes data
    payload["layout"]["fields"].append("cpf")
    payload["endereco"]["cpf"] = ""
    assert "RUC/C.I" not in pdf_text(render_address(payload))
    # Old snapshots with no cpf key also remain valid; never recover it from an editor block.
    payload["endereco"].pop("cpf")
    payload["editor"] = {"cpf": "A-123.456"}
    assert "RUC/C.I" not in pdf_text(render_address(payload))


@pytest.mark.parametrize("document", ["A" * 21, "ABC\x01XYZ"])
def test_py_document_still_rejects_oversized_and_control_character_input(document):
    with pytest.raises(ValidationError):
        AddressArgs(pais="PY", cpf=document)


@pytest.mark.parametrize("message", ["Imprima sem RUC", "Imprima sem C.I.", "Imprima sem documento", "Imprima sem CPF"])
def test_explicit_document_omission_reaches_the_preview_without_queuing(env, message):
    factory, _, uid, _ = env
    with factory() as db:
        identity = db.query(AssistantIdentity).filter_by(channel="telegram", user_id=uid).one()
        source = incoming(db, uid, message, channel="telegram")
        result = prepare_print(db, source, identity, AddressArgs(pais="PY", nome="Sintético", cpf="A-123.456"))
        assert "confirmacao" in result
        action = db.query(AssistantAction).filter_by(source_message_id=source.id).one()
        assert action.payload["endereco"]["cpf"] == ""
        assert "A-123.456" not in result["confirmacao"]
        assert db.query(PrintJob).count() == 0


def test_manager_preview_keeps_py_document_without_queuing_a_print(env):
    factory, client, _, device_id = env
    data = {"pais": "PY", "nome": "Destinatário sintético", "cpf": "A-4.567.890", "cidade": "Asunción"}
    saved = client.post("/manager/addresses", json={"label": "Casa sintética", "data": data})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["cpf"] == data["cpf"]
    body = {"request_key": str(uuid.uuid4()), "device_id": device_id, "address_id": saved.json()["id"], "data": data}
    preview = client.post("/manager/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert "RUC/C.I: A-4.567.890" in pdf_text(preview.content)
    with factory() as db:
        assert db.query(PrintJob).count() == 0
    # Saving and previewing are read/write local fixtures; nothing is sent to an agent.
    assert client.get("/manager/addresses").json()["items"][0]["data"]["cpf"] == data["cpf"]
