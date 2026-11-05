"""Tracking negatives must come from a current lookup, not conversational memory."""
import pytest

from test_assistant import setup, incoming
from test_assistant_queries import shipment, tool_call
from app.models.assistant import AssistantIdentity
from app.services import assistant_agent as agent, assistant_channels as channels


@pytest.mark.parametrize("channel", ["telegram", "whatsapp", "whatsapp_web"])
@pytest.mark.parametrize('term,registered', [('Davi Muniz', 'Davi Almeida Muniz'), ('Murilo', 'Murillo Almeida')])
def test_historical_negative_cannot_replace_current_tracking_lookup(setup, monkeypatch, channel, term, registered):
    factory, _, user_id = setup
    replies = iter([
        {"content": "Não encontrei envio em andamento para esse cliente no ERP."},
        tool_call("buscar_rastreios", {"termo": term, "ordem": "priorizar_abertos"}),
    ])
    choices = []

    def complete(messages, **kwargs):
        choices.append(kwargs.get("tool_choice"))
        return next(replies)

    monkeypatch.setattr(agent, "complete", complete)
    with factory() as db:
        if channel == "whatsapp_web":
            db.add(AssistantIdentity(channel=channel, external_id="123", user_id=user_id))
            db.flush()
        previous = incoming(db, user_id, f"Me passa o rastreio do {term}", channel=channel)
        previous.status = "done"
        previous.response = "Não encontrei envio em andamento para esse cliente no ERP."
        shipment(db, "AA123456789BR", name=registered)
        db.flush()
        message = incoming(db, user_id, f"Me passa o rastreio do {term}", channel=channel)
        result = agent.respond(db, message, channels.authorized_identity(db, channel, message.sender_id))

    assert result.parts[0] == "AA123456789BR"
    assert registered in result.parts[1]
    assert "Em trânsito" in result.parts[1]
    assert len(result.parts) == 2
    assert choices == []  # The routine lookup no longer depends on model routing.


def test_empty_current_query_allows_negative_answer(setup, monkeypatch):
    factory, _, user_id = setup
    answer = "Não encontrei rastreios entregues para Davi."
    replies = iter([
        tool_call("buscar_rastreios", {"termo": "Davi", "situacao": "ENTREGUE"}),
        {"content": answer},
    ])
    monkeypatch.setattr(agent, "complete", lambda *args, **kwargs: next(replies))
    with factory() as db:
        message = incoming(db, user_id, "Liste os rastreios entregues de Davi")
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
    assert result.parts == [answer]


@pytest.mark.parametrize("tool", ["buscar_rastreios", "consultar_rastreio_cliente"])
@pytest.mark.parametrize("error", ["Consulta temporariamente indisponível.", "Acesso não permitido para este usuário."])
def test_tracking_tool_error_is_not_reported_as_missing_shipment(setup, monkeypatch, tool, error):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, "complete", lambda *args, **kwargs: tool_call(tool, {"termo": "Davi"}))
    monkeypatch.setattr(agent, "execute_tool", lambda *args, **kwargs: {"erro": error})
    with factory() as db:
        message = incoming(db, user_id, "Consulte o histórico de rastreios do Davi")
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
    assert result.parts == [error]
    assert "Não encontrei" not in result


def test_unqueried_negative_has_bounded_retries_and_reports_unavailable(setup, monkeypatch):
    factory, _, user_id = setup
    calls = []

    def complete(messages, **kwargs):
        calls.append(kwargs.get("tool_choice"))
        return {"content": "Não encontrei rastreio para Davi."}

    monkeypatch.setattr(agent, "complete", complete)
    with factory() as db:
        message = incoming(db, user_id, "Me passa o último rastreio do Davi")
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
    assert len(calls) == 3
    assert "Não consegui verificar" in result
    assert "Não encontrei" not in result


def test_invalid_query_does_not_count_as_current_evidence(setup, monkeypatch):
    factory, _, user_id = setup
    replies = iter([
        tool_call("buscar_rastreios", {"termo": "Davi", "pagina": 0}),
        {"content": "Não encontrei rastreio para Davi."},
        tool_call("buscar_rastreios", {"termo": "Davi"}),
    ])
    choices = []

    def complete(messages, **kwargs):
        choices.append(kwargs.get("tool_choice"))
        return next(replies)

    monkeypatch.setattr(agent, "complete", complete)
    with factory() as db:
        shipment(db, "AA123456789BR", name="Davi Almeida Muniz")
        message = incoming(db, user_id, "Não consultei ainda, me passa o rastreio do Davi")
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
    assert result.parts[0] == "AA123456789BR"
    assert choices[-1] == {"type": "function", "function": {"name": "buscar_rastreios"}}


@pytest.mark.parametrize("content, previous, expected", [
    ("Qual o rastreio do Davi Muniz?", None, True),
    ("E do Davi Muniz?", "Qual o rastreio da Maria?", True),
    ("Tem o código do Davi?", None, True),
    ("AA123456789BR", None, False),  # A bare code is not a tracking intent on its own.
    ("Qual o status do rastreio AA123456789BR?", None, True),
    ("Cadastre os rastreios deste comprovante", None, False),
    ("Imprima o endereço do rastreio do Davi", None, False),
    ("Reimprima o endereço do rastreio do Davi", None, False),
    ("Reimpressão do rastreio AA123456789BR", None, False),
    ("Consulte o PDF da etiqueta do rastreio do Davi", None, False),
    ("Qual o código do produto Camiseta?", None, False),
    ("Qual o código interno desse item?", "Qual o rastreio do Davi?", False),
    ("Me passa o código do item Camiseta", None, False),
    ("Qual o código da venda?", None, False),
    ("Como funciona o rastreamento?", None, False),
    ("Como consultar um rastreio pelo bot?", None, False),
    ("Não preciso consultar rastreio agora", None, False),
    ("Não consultei ainda, me passa o rastreio do Davi", None, True),
])
def test_fresh_tracking_guard_keeps_other_operations_separate(content, previous, expected):
    assert agent._tracking_lookup_required(content, previous) is expected


def test_observation_mode_does_not_force_a_tracking_reply(setup, monkeypatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, "complete", lambda *args, **kwargs: {"content": "Não encontrei rastreio."})
    with factory() as db:
        message = incoming(db, user_id, "Qual o rastreio do Davi?", reply=False)
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
    assert result is None
