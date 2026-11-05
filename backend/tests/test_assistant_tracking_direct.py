"""Real operational wordings resolve with current data even when AI is unavailable."""
from datetime import date, timedelta

import pytest

from test_assistant import setup, incoming
from test_assistant_queries import shipment
from app.models.assistant import AssistantIdentity, utcnow
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services.assistant_tracking import customer_tracking_term, tracking_choice_request


def no_model(*args, **kwargs):
    raise AssertionError('Routine tracking must not require a model call')


@pytest.mark.parametrize('channel', ['telegram', 'whatsapp', 'whatsapp_web'])
@pytest.mark.parametrize('text,registered', [
    ('Me passe o rastreio do Murilo', 'Murillo Nicolau Marcelino da Silva'),
    ('Me passa o rastreio do Davi Muniz', 'Davi Almeida Muniz'),
    ('Manda os rastreios do davi', 'Davi Almeida Muniz'),
    ('Rastreio Davi Muniz', 'Davi Almeida Muniz'),
    ('/eleven rastreio Davi Muniz', 'Davi Almeida Muniz'),
    ('Tem o código do Davi Muniz?', 'Davi Almeida Muniz'),
])
def test_routine_tracking_returns_current_codes_without_ai(setup, monkeypatch, channel, text, registered):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    with factory() as db:
        if channel == 'whatsapp_web':
            db.add(AssistantIdentity(channel=channel, external_id='123', user_id=user_id))
            db.flush()
        shipment(db, 'AA123456789BR', name=registered)
        shipment(db, 'BB123456789BR', name=registered)
        shipment(db, 'CC123456789BR', name=registered, status='ENTREGUE')
        message = incoming(db, user_id, text, channel=channel)
        result = agent.respond(db, message, channels.authorized_identity(db, channel, message.sender_id))
        assert set(result.parts[::2]) == {'AA123456789BR', 'BB123456789BR'}
        assert all(registered in part and 'Em trânsito' in part for part in result.parts[1::2])
        if 'Murilo' in text:
            assert all('Nome próximo à busca' in part for part in result.parts[1::2])
        assert 'CC123456789BR' not in result


@pytest.mark.parametrize('text,previous,term', [
    ('Rastreio Davi Muniz', None, 'davi muniz'),
    ('Me passa o rastreio do Davi Muniz, por favor', None, 'davi muniz'),
    ('E do Murilo?', 'Qual o rastreio do Davi?', 'murilo'),
    ('E do Murilo?', 'Qual o código do produto?', None),
    ('Me passa todos os rastreios então', None, None),
    ('Rastreio do Davi de ontem', None, None),
    ('Qual o último rastreio do Davi?', None, None),
    ('Qual o rastreio do Davi em 02/11?', None, None),
    ('Rastreio Davi deu erro', None, None),
    ('Não encontrei o rastreio do Davi', None, None),
    ('Como consultar o rastreio do Davi?', None, None),
    ('Imprima o endereço do rastreio do Davi', None, None),
    ('Reimprima o endereço do rastreio do Davi', None, None),
    ('PDF do rastreio Davi', None, None),
    ('Me passa o código do item Camiseta', None, None),
    ('Rastreio do Davi e da Maria', None, None),
    ('Rastreio do cliente', None, None),
    ('Rastreio X', None, None),
    ('AA123456789BR', None, None),
    ('2', 'Qual o rastreio do Davi?', None),
])
def test_only_simple_current_name_requests_use_direct_route(text, previous, term):
    assert customer_tracking_term(text, previous) == term


def test_name_followup_queries_current_customer_without_ai(setup, monkeypatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    with factory() as db:
        previous = incoming(db, user_id, 'Qual o rastreio do Davi?')
        previous.status = 'done'
        previous.response = 'Não encontrei envio em andamento para esse cliente no ERP.'
        shipment(db, 'AA123456789BR', name='Murillo Nicolau Marcelino da Silva')
        message = incoming(db, user_id, 'E do Murilo?')
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
        assert result.parts[0] == 'AA123456789BR'
        assert 'Murillo Nicolau' in result.parts[1]


def ambiguity(db, user_id):
    shipment(db, 'AA123456789BR', name='Davi Almeida Muniz', day=date(2026, 11, 1))
    second = shipment(db, 'BB123456789BR', name='Davi Rocha Muniz', day=date(2026, 10, 30))
    previous = incoming(db, user_id, 'Me passa o rastreio do Davi Muniz')
    identity = channels.authorized_identity(db, previous.channel, previous.sender_id)
    previous.response = str(agent.respond(db, previous, identity))
    previous.status = 'done'
    db.flush()
    assert '1. Davi Almeida Muniz' in previous.response and '2. Davi Rocha Muniz' in previous.response
    return previous, second, identity


def test_numbered_choice_uses_live_result_bound_to_previous_ambiguity(setup, monkeypatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    with factory() as db:
        previous, _, identity = ambiguity(db, user_id)
        message = incoming(db, user_id, '2')
        result = agent.respond(db, message, identity)
        assert result.parts[0] == 'BB123456789BR'
        assert 'Davi Rocha Muniz' in result.parts[1]
        assert 'Davi Almeida Muniz' not in result


def test_changed_choices_do_not_select_a_different_recipient(setup, monkeypatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    with factory() as db:
        _, second, identity = ambiguity(db, user_id)
        second.status = 'ENTREGUE'
        db.flush()
        result = agent.respond(db, incoming(db, user_id, '2'), identity)
        assert 'lista de envios mudou' in result
        assert 'AA123456789BR' not in result and 'BB123456789BR' not in result


def test_out_of_range_choice_does_not_guess_a_recipient(setup, monkeypatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    with factory() as db:
        _, _, identity = ambiguity(db, user_id)
        result = agent.respond(db, incoming(db, user_id, '3'), identity)
        assert 'não corresponde à lista' in result
        assert 'AA123456789BR' not in result and 'BB123456789BR' not in result


@pytest.mark.parametrize('mismatch', ['user_id', 'sender_id', 'channel', 'conversation_id', 'status', 'expired', 'response'])
def test_numbered_choice_cannot_borrow_foreign_expired_or_other_messages(setup, monkeypatch, mismatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    with factory() as db:
        previous, _, _ = ambiguity(db, user_id)
        message = incoming(db, user_id, '2')
        if mismatch == 'expired':
            previous.created_at = utcnow() - timedelta(minutes=31)
        elif mismatch == 'status':
            previous.status = 'failed'
        elif mismatch == 'response':
            previous.response = 'Escolha o serviço: 1. PAC\n2. SEDEX'
        else:
            setattr(message, mismatch, 'different')
        assert tracking_choice_request('2', message, previous, utcnow()) is None


def test_direct_lookup_error_is_not_a_missing_shipment(setup, monkeypatch):
    factory, _, user_id = setup
    monkeypatch.setattr(agent, 'complete', no_model)
    monkeypatch.setattr(agent, 'execute_tool', lambda *args, **kwargs: {'erro': 'Consulta temporariamente indisponível.'})
    with factory() as db:
        message = incoming(db, user_id, 'Rastreio Davi Muniz')
        result = agent.respond(db, message, channels.authorized_identity(db, message.channel, message.sender_id))
        assert result.parts == ['Consulta temporariamente indisponível.']
        assert 'Não encontrei' not in result
