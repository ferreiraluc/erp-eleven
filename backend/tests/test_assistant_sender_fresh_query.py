"""Sender refusals need current registry evidence, independently of recipient matches."""
import json

import pytest

from test_assistant import setup, incoming
from test_address_manager import env
from test_assistant_queries import tool_call
from app.models.assistant import AssistantAction, AssistantIdentity, AssistantKnowledge
from app.models.printing import PrintJob, PrintSender
from app.models.usuario import Usuario, UsuarioRole
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services.assistant_routines import ROUTINE_KEY, save_routine
from app.services.assistant_tools import execute_tool


@pytest.fixture
def sender_owner(env):
    factory, _, user_id, _ = env
    with factory() as db:
        user = db.get(Usuario, user_id)
        user.email, user.role = 'lucas@eleven.com', UsuarioRole.ADMIN
        db.add_all([
            PrintSender(id='mona', name='Mona Silva', lines=['Rua de teste, 10']),
            PrintSender(id='debora', name='Débora Almeida', lines=['Rua de teste, 20']),
            PrintSender(id='old', name='Mona anterior', lines=[], active=False),
            AssistantIdentity(channel='whatsapp_web', external_id='123', user_id=user_id, can_register=True),
        ])
        db.flush()
        save_routine(db, {
            'package': {'weight': 1, 'height': 15, 'width': 15, 'length': 15},
            'product': {'name': 'Camiseta', 'unitary_value': '50.00'},
        }, user_id=user_id, expected_revision=0)
        db.commit()
    return factory, user_id


@pytest.mark.parametrize('channel', ['telegram', 'whatsapp', 'whatsapp_web'])
@pytest.mark.parametrize(('term', 'sender_id'), [('Mona', 'mona'), ('Debora', 'debora')])
def test_query_separates_live_sender_matches_from_empty_recipients_and_exposes_saved_routine(sender_owner, channel, term, sender_id):
    factory, user_id = sender_owner
    with factory() as db:
        message = incoming(db, user_id, f'Consulte o remetente {term}', channel=channel)
        identity = channels.authorized_identity(db, channel, message.sender_id)
        output = execute_tool(db, message, identity, 'consultar_enderecos', {'termo': term})
        assert output['enderecos'] == [] and output['enderecos_impressos'] == []
        assert {row['id'] for row in output['remetentes']} == {'mona', 'debora'}
        assert output['remetentes_correspondentes'] == [{'id': sender_id, 'nome': 'Mona Silva' if sender_id == 'mona' else 'Débora Almeida'}]
        assert 'Endereços vazios não significam remetente ausente' in output['orientacao_remetentes']
        saved = output['padrao_frete']['padrao']
        assert saved['package'] == {'weight': 1, 'height': 15, 'width': 15, 'length': 15}
        assert saved['product'] == {'name': 'Camiseta', 'unitary_value': '50.00'}
        assert saved['revision'] == 1
        assert db.get(AssistantKnowledge, ROUTINE_KEY).data['revision'] == 1
        assert db.query(AssistantAction).count() == db.query(PrintJob).count() == 0


@pytest.mark.parametrize('channel', ['telegram', 'whatsapp', 'whatsapp_web'])
@pytest.mark.parametrize('old_refusal', ['Não encontrei o remetente Mona no gestor.', 'Não achei a Mona.'])
def test_historical_sender_negative_is_discarded_and_model_must_consult_again(sender_owner, monkeypatch, channel, old_refusal):
    factory, user_id = sender_owner
    calls = []

    def complete(messages, **kwargs):
        calls.append(kwargs.get('tool_choice'))
        assert not any(row.get('role') == 'assistant' and row.get('content') == old_refusal for row in messages)
        assert any('Mona usa Rua de teste, 10' in (row.get('content') or '') for row in messages)
        if len(calls) == 1:
            return {'content': 'Não encontrei o remetente Mona.'}
        if len(calls) == 2:
            return tool_call('consultar_enderecos', {'termo': 'Mona'})
        output = json.loads(messages[-1]['content'])
        assert output['enderecos'] == []
        assert output['remetentes_correspondentes'][0]['id'] == 'mona'
        assert output['padrao_frete']['padrao']['package']['weight'] == 1
        return {'content': 'Mona Silva está cadastrada. O padrão confirmado é 1 kg e 15 × 15 × 15 cm.'}

    monkeypatch.setattr(agent, 'complete', complete)
    with factory() as db:
        previous = incoming(db, user_id, 'A remetente Mona usa Rua de teste, 10', channel=channel)
        previous.status, previous.response = 'done', old_refusal
        db.flush()
        message = incoming(db, user_id, 'O remetente Mona está cadastrado?', channel=channel)
        identity = channels.authorized_identity(db, channel, message.sender_id)
        answer = agent.respond(db, message, identity)
    assert 'Mona Silva está cadastrada' in answer
    required = {'type': 'function', 'function': {'name': 'consultar_enderecos'}}
    assert calls == [required, required, None]


@pytest.mark.parametrize('prompt', [
    'O remetente Mona está cadastrado?',
    'Quais remetentes temos cadastrados?',
    'Quais são os padrões de frete?',
])
def test_repeated_unqueried_negative_has_bounded_retry_and_reports_unavailable(sender_owner, monkeypatch, prompt):
    factory, user_id = sender_owner
    calls = []

    def complete(messages, **kwargs):
        calls.append(kwargs.get('tool_choice'))
        return {'content': 'Não encontrei nenhum remetente.'}

    monkeypatch.setattr(agent, 'complete', complete)
    with factory() as db:
        message = incoming(db, user_id, prompt, channel='whatsapp_web')
        identity = channels.authorized_identity(db, message.channel, message.sender_id)
        answer = agent.respond(db, message, identity)
    assert len(calls) == 2
    assert 'Não consegui consultar' in answer
    assert 'não significa que o cadastro não existe' in answer
    assert 'Não encontrei' not in answer


@pytest.mark.parametrize('error', [
    'Consulta temporariamente indisponível.',
    'Acesso a endereços exige gestor habilitado.',
])
def test_query_error_is_returned_without_turning_into_missing_sender(sender_owner, monkeypatch, error):
    factory, user_id = sender_owner
    calls = []

    def complete(*args, **kwargs):
        calls.append(True)
        return tool_call('consultar_enderecos', {'termo': 'Debora'})

    monkeypatch.setattr(agent, 'complete', complete)
    monkeypatch.setattr(agent, 'execute_tool', lambda *args, **kwargs: {'erro': error})
    with factory() as db:
        message = incoming(db, user_id, 'Encontre o remetente Débora', channel='whatsapp_web')
        identity = channels.authorized_identity(db, message.channel, message.sender_id)
        answer = agent.respond(db, message, identity)
    assert answer.parts == [error]
    assert len(calls) == 1


def test_invalid_query_is_not_current_evidence_and_can_be_corrected(sender_owner, monkeypatch):
    factory, user_id = sender_owner
    responses = iter([
        tool_call('consultar_enderecos', {'termo': ''}),
        {'content': 'Não encontrei o remetente Débora.'},
        tool_call('consultar_enderecos', {'termo': 'Debora'}),
        {'content': 'Débora Almeida está cadastrada.'},
    ])
    choices = []

    def complete(messages, **kwargs):
        choices.append(kwargs.get('tool_choice'))
        return next(responses)

    monkeypatch.setattr(agent, 'complete', complete)
    with factory() as db:
        message = incoming(db, user_id, 'Encontre o remetente Débora')
        identity = channels.authorized_identity(db, message.channel, message.sender_id)
        answer = agent.respond(db, message, identity)
    assert 'Débora Almeida está cadastrada' in answer
    assert choices[2] == {'type': 'function', 'function': {'name': 'consultar_enderecos'}}


def test_observation_does_not_send_a_sender_reply(sender_owner, monkeypatch):
    factory, user_id = sender_owner
    monkeypatch.setattr(agent, 'complete', lambda *args, **kwargs: {'content': 'Não encontrei o remetente Mona.'})
    with factory() as db:
        message = incoming(db, user_id, 'Encontre o remetente Mona', reply=False)
        identity = channels.authorized_identity(db, message.channel, message.sender_id)
        assert agent.respond(db, message, identity) is None


@pytest.mark.parametrize(('content', 'previous', 'expected'), [
    ('Quais remetentes temos cadastrados?', None, True),
    ('Consulte o remetente Mona', None, True),
    ('Qual o padrão de frete?', None, True),
    ('Emita uma etiqueta para Maria', None, True),
    ('Cote uma etiqueta com PDF', None, True),
    ('E a Débora?', 'Consulte o remetente Mona', True),
    ('Use a mesma', 'Consulte o remetente Mona', True),
    ('E a Débora?', 'Quem vendeu ontem?', False),
    ('Consulte o PDF da etiqueta para imprimir', None, False),
    ('Qual o status da etiqueta?', None, False),
    ('Qual o rastreio da etiqueta?', None, False),
    ('Reimprima a etiqueta existente', None, False),
    ('Imprima novamente a etiqueta', None, False),
    ('Envie a segunda via da etiqueta', None, False),
    ('E o PDF?', 'Consulte o remetente Mona', False),
    ('E o estoque de camisetas?', 'Consulte o remetente Mona', False),
    ('Como funciona o cadastro de remetentes?', None, False),
    ('Não preciso consultar remetentes agora', None, False),
])
def test_sender_guard_does_not_intercept_other_operations(content, previous, expected):
    assert agent._sender_lookup_required(content, previous) is expected


def test_short_sender_continuation_also_requires_a_current_lookup(sender_owner, monkeypatch):
    factory, user_id = sender_owner
    replies = iter([
        {'content': 'Não encontrei a Débora.'},
        tool_call('consultar_enderecos', {'termo': 'Debora'}),
        {'content': 'Débora Almeida está cadastrada.'},
    ])
    monkeypatch.setattr(agent, 'complete', lambda *args, **kwargs: next(replies))
    with factory() as db:
        previous = incoming(db, user_id, 'Consulte o remetente Mona')
        previous.status = 'done'; db.flush()
        message = incoming(db, user_id, 'E a Débora?')
        identity = channels.authorized_identity(db, message.channel, message.sender_id)
        assert 'Débora Almeida está cadastrada' in agent.respond(db, message, identity)
