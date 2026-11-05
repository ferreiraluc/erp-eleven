"""Regressions from print-history follow-ups, without any physical dispatch."""
import json
import uuid

import pytest

from test_address_manager import env
from test_assistant import setup, incoming
from app.models import Usuario
from app.models.assistant import AssistantAction
from app.models.printing import PrintJob
from app.models.usuario import UsuarioRole
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services.assistant_documents import query_prints
from app.services.assistant_printing import AddressArgs, prepare_print, prepare_address_reprint, ReprintAddressArgs
from app.services.assistant_queries import QueryArgs
from app.services.assistant_schedule import confirm_action
from app.services.assistant_tools import execute_tool


def original_print(db, uid):
    identity = channels.authorized_identity(db, 'telegram', '123')
    message = incoming(db, uid, 'Imprime endereço de Cliente Teste', channel='telegram')
    prepare_print(db, message, identity, AddressArgs(pais='PY', nome='Cliente Teste', cidade='Asunción'))
    action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
    confirm_action(db, message, identity, action)
    job = db.query(PrintJob).one()
    job.status, job.pdf = 'uncertain', b''  # The normal ACK clears the temporary PDF.
    job.diagnostic = {'code': 'renderer_exit_error', 'exit_code': 1, 'agent_version': '2026.10.15.1'}
    db.flush()
    return job, identity


@pytest.mark.parametrize('status', ['uncertain', 'submitted', 'failed'])
def test_reprint_reuses_saved_address_requires_confirmation_and_is_idempotent(env, status):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        original.status = status
        message = incoming(db, uid, 'Pode reimprimir Cliente Teste', channel='telegram')
        args = ReprintAddressArgs(trabalho_id=original.id)
        response = prepare_address_reprint(db, message, identity, args)
        assert 'Nova cópia do endereço já salvo' in response['confirmacao']
        assert 'Confira o papel' in response['confirmacao']
        assert 'Asunción' in response['confirmacao']
        assert db.query(PrintJob).count() == 1
        action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
        assert action.payload['reprint_of'] == str(original.id)
        prepare_address_reprint(db, message, identity, args)
        assert db.query(AssistantAction).count() == 2
        confirm = incoming(db, uid, 'Confirmo', channel='telegram')
        confirm_action(db, confirm, identity, action)
        assert db.query(PrintJob).count() == 2
        copied = db.query(PrintJob).filter_by(request_key=action.id).one()
        assert copied.parent_id == original.id and copied.pdf.startswith(b'%PDF-')
        assert copied.status == 'pending' and original.status == status and original.pdf == b''
        confirm_action(db, confirm, identity, action)
        assert db.query(PrintJob).count() == 2


@pytest.mark.parametrize('status', ['pending', 'claimed'])
def test_reprint_does_not_duplicate_work_in_progress(env, status):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        original.status = status
        message = incoming(db, uid, 'Reimprimir Cliente Teste', channel='telegram')
        result = prepare_address_reprint(db, message, identity, ReprintAddressArgs(trabalho_id=original.id))
        assert 'erro' in result and db.query(PrintJob).count() == db.query(AssistantAction).count() == 1


def test_reprint_rechecks_pending_state_at_confirmation(env):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        message = incoming(db, uid, 'Reimprimir Cliente Teste', channel='telegram')
        prepare_address_reprint(db, message, identity, ReprintAddressArgs(trabalho_id=original.id))
        action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
        original.status = 'claimed'
        assert 'Nenhuma segunda cópia' in confirm_action(db, message, identity, action)
        assert db.query(PrintJob).count() == 1 and action.status == 'draft'


def test_two_previews_cannot_enqueue_concurrent_copies_of_same_original(env):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        messages = [incoming(db, uid, 'Reimprimir Cliente Teste', channel='telegram') for _ in range(2)]
        for message in messages:
            prepare_address_reprint(db, message, identity, ReprintAddressArgs(trabalho_id=original.id))
        actions = [db.query(AssistantAction).filter_by(source_message_id=message.id).one() for message in messages]
        confirm_action(db, messages[0], identity, actions[0])
        assert 'Nenhuma segunda cópia' in confirm_action(db, messages[1], identity, actions[1])
        assert db.query(PrintJob).count() == 2
        third = incoming(db, uid, 'Reimprimir Cliente Teste', channel='telegram')
        assert 'erro' in prepare_address_reprint(db, third, identity, ReprintAddressArgs(trabalho_id=original.id))


def test_staff_cannot_reprint_another_authors_job_or_repurpose_external_file(env):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        db.get(Usuario, uid).role = UsuarioRole.VENDEDOR
        other = Usuario(id=uuid.uuid4(), nome='Outro', email='other-reprint@example.test', senha_hash='test')
        db.add(other); db.flush()
        original.user_id = other.id
        message = incoming(db, uid, 'Reimprimir Cliente Teste', channel='telegram')
        assert 'erro' in prepare_address_reprint(db, message, identity, ReprintAddressArgs(trabalho_id=original.id))
        original.user_id, original.source = uid, 'bot_pdf_ephemeral'
        db.flush()
        assert 'erro' in prepare_address_reprint(db, message, identity, ReprintAddressArgs(trabalho_id=original.id))
        assert db.query(AssistantAction).count() == 1


def test_print_lookup_distinguishes_cleared_pdf_from_generation_failure(env):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        message = incoming(db, uid, 'Já imprimiu Cliente Teste?', channel='telegram')
        result = query_prints(db, message, identity, QueryArgs(termo='Cliente Teste'))
        row = result['resultados'][0]
        assert row['status'] == 'uncertain' and not row['pdf_armazenado_agora']
        assert row['endereco_salvo_para_nova_previa']
        assert 'preparar_reimpressao_endereco' in row['proxima_acao']
        assert 'não significa falha na geração' in result['aviso']
        assert db.query(PrintJob).count() == 1


def test_bot_recovers_from_false_tool_unavailable_refusal(env, monkeypatch):
    factory, _, uid, _ = env
    with factory() as db:
        original, identity = original_print(db, uid)
        calls = []
        def complete(messages, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {'content': 'A ferramenta de impressão não está disponível. Envie todos os dados novamente.'}
            name, args = ('consultar_impressoes', {'termo': 'Cliente Teste'}) if len(calls) == 2 else (
                'preparar_reimpressao_endereco', {'trabalho_id': str(original.id)})
            assert len(calls) <= 3
            return {'tool_calls': [{'id': f'tool-{len(calls)}', 'type': 'function', 'function': {
                'name': name, 'arguments': json.dumps(args)}}]}
        monkeypatch.setattr(agent, 'complete', complete)
        message = incoming(db, uid, 'Imprime de novo Cliente Teste, essa não saiu', channel='telegram')
        result = agent.respond(db, message, identity)
        assert 'Nova cópia do endereço já salvo' in result
        assert result.reply_markup and db.query(PrintJob).count() == 1
        assert calls[1]['tool_choice']['function']['name'] == 'consultar_impressoes'


@pytest.mark.parametrize('text,expected', [
    ('Pode reeimprimir', True), ('Imprime esse de novo', True), ('A fila está limpa', True),
    ('Não quero reimprimir', False), ('Como funciona a reimpressão?', False),
    ('Já imprimiu o endereço?', True), ('Imprime de novo, não saiu', True),
])
def test_print_lookup_intent(text, expected):
    assert agent._print_lookup_required(text) is expected
