"""A written preview must correspond to an action the author can confirm."""
import json

import pytest

from test_assistant import setup, incoming
from test_address_manager import env
from app import assistant_worker as worker
from app.models.assistant import AssistantAction, AssistantDelivery, AssistantMessage
from app.models.printing import PrintJob
from app.services import assistant_agent as agent, assistant_channels as channels


PHANTOM = (
    'Imprimir endereço em A4, uma cópia:\nCliente Teste\nPedro Juan Caballero\n'
    'Telefone: 12345\nRUC/C.I: TEST-9\nPaís: Paraguai\n'
    'Diga “confirmo” para enviar à impressora da loja ou “cancela”.\n'
    'Ainda não foi enviado. Prévia válida por 24 horas.'
)
ADDRESS = dict(pais='PY', nome='Cliente Teste', cidade='Pedro Juan Caballero',
               telefone='12345', cpf='TEST-9')


def print_call():
    return {'tool_calls': [{'id': 'print-test', 'type': 'function', 'function': {
        'name': 'preparar_impressao', 'arguments': json.dumps(ADDRESS)}}]}


@pytest.mark.parametrize('prose', [
    PHANTOM,
    '**Imprimir endereço em A4, uma cópia:**\nCliente Teste\nConfirma a impressão?',
    'Endereço pronto. Digite **confirmo** para imprimir ou **cancela**.',
    'Endereço pronto. Confirme para enviar à impressora.',
])
def test_paraguay_followup_has_persisted_preview_buttons_and_text_confirmation(env, monkeypatch, prose):
    factory, _, uid, _ = env
    requests = []

    def complete(messages, **kwargs):
        requests.append(kwargs)
        if len(requests) == 1:
            return {'content': prose}
        if len(requests) == 2:
            return print_call()
        raise AssertionError('A persisted preview must not need another model call')

    monkeypatch.setattr(agent, 'complete', complete)
    with factory() as db:
        previous = incoming(db, uid, 'Imprime envio pro Paraguay', channel='telegram')
        previous.status = 'done'
        previous.response = 'Pode enviar os dados disponíveis do destinatário.'
        message = incoming(db, uid, 'Cliente Teste\nRUC TEST-9\nCel.12345\nPedro Juan Caballero', channel='telegram')
        mid = message.id
        db.commit()
    assert worker.process_inbox()
    with factory() as db:
        assert db.get(AssistantMessage, mid).status == 'done'
        action = db.query(AssistantAction).one()
        key = action.id
        assert action.status == 'draft' and action.payload['endereco']['cpf'] == 'TEST-9'
        assert action.payload['remetente'] is None
        delivery = db.query(AssistantDelivery).filter_by(event_key=f'reply:{mid}').one()
        buttons = delivery.reply_markup['inline_keyboard'][0]
        assert [b['callback_data'] for b in buttons] == ['a:'+key.hex, 'c:'+key.hex]
        assert db.query(PrintJob).count() == 0
        incoming(db, uid, 'Confirmo', channel='telegram')
        db.commit()
    assert worker.process_inbox()
    with factory() as db:
        assert db.query(PrintJob).one().request_key == key
        assert db.get(AssistantAction, key).status == 'executed'
        incoming(db, uid, '/acao a:'+key.hex, channel='telegram')
        db.commit()
    assert worker.process_inbox()
    with factory() as db:
        assert db.query(PrintJob).count() == 1
    assert len(requests) == 2
    if prose == PHANTOM:
        assert requests[1]['tool_choice']['function']['name'] == 'preparar_impressao'


def test_selected_preview_stays_in_history(env, monkeypatch):
    from app.services.assistant_printing import AddressArgs, prepare_print
    factory, _, uid, _ = env
    with factory() as db:
        identity = channels.authorized_identity(db, 'telegram', '123')
        original = incoming(db, uid, 'Imprima Cliente Teste para PY', channel='telegram')
        prepare_print(db, original, identity, AddressArgs(**ADDRESS))
        original.status = 'done'
        action = db.query(AssistantAction).one()
        selected = incoming(db, uid, '/acao v:'+action.id.hex, channel='telegram')
        sid = selected.id
        db.commit()
    assert worker.process_inbox()

    def complete(messages, **kwargs):
        assert any(m['role'] == 'assistant' and 'RUC/C.I do destinatário: TEST-9' in (m['content'] or '') for m in messages)
        return {'content': 'Os dados da prévia incluem RUC/C.I: TEST-9.'}

    monkeypatch.setattr(agent, 'complete', complete)
    with factory() as db:
        assert db.get(AssistantMessage, sid).status == 'done'
        message = incoming(db, uid, 'Qual documento aparece nessa prévia?', channel='telegram')
        agent.respond(db, message, channels.authorized_identity(db, 'telegram', '123'))
        assert db.query(PrintJob).count() == 0


def test_repeated_prose_without_tool_is_never_offered_for_confirmation(env, monkeypatch):
    factory, _, uid, _ = env
    monkeypatch.setattr(agent, 'complete', lambda *a, **kw: {'content': PHANTOM})
    with factory() as db:
        message = incoming(db, uid, 'Imprime Cliente Teste para PY', channel='telegram')
        answer = agent.respond(db, message, channels.authorized_identity(db, 'telegram', '123'))
        assert 'Não consegui preparar' in answer
        assert 'Diga “confirmo”' not in answer
        assert db.query(AssistantAction).count() == db.query(PrintJob).count() == 0


def test_old_unpersisted_preview_is_not_used_as_assistant_example(env, monkeypatch):
    factory, _, uid, _ = env

    def complete(messages, **kwargs):
        assert not any(m['role'] == 'assistant' and m['content'] == PHANTOM for m in messages)
        assert any('RUC TEST-9' in (m.get('content') or '') for m in messages if m['role'] == 'user')
        return print_call()

    monkeypatch.setattr(agent, 'complete', complete)
    with factory() as db:
        old = incoming(db, uid, 'Cliente Teste\nRUC TEST-9', channel='telegram')
        old.status, old.response = 'done', PHANTOM
        db.add(AssistantDelivery(event_key=f'reply:{old.id}', channel='telegram',
            destination=old.conversation_id, user_id=uid, text=PHANTOM,
            status='accepted', reply_markup=None))
        db.flush()
        message = incoming(db, uid, 'Imprima esses dados para PY', channel='telegram')
        answer = agent.respond(db, message, channels.authorized_identity(db, 'telegram', '123'))
        assert answer.reply_markup['inline_keyboard'][0][0]['text'] == 'Imprimir'
        assert db.query(PrintJob).count() == 0
