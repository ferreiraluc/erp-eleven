"""Print-specific text cannot authorize another kind of pending action."""
import pytest

from test_assistant import incoming, setup
from test_address_manager import env
from app.models.assistant import AssistantAction
from app.models.printing import PrintJob
from app.services import assistant_agent as agent, assistant_channels as channels
from app.services import assistant_schedule as schedule
from app.services.assistant_printing import AddressArgs, prepare_print


def payment_draft(db, uid, recipient='Cliente Teste'):
    message = incoming(db, uid, 'Preparar etiqueta', channel='telegram')
    action = AssistantAction(source_message_id=message.id, user_id=uid,
                             kind='frete_emitir', payload={'recipient': recipient, 'price': '20.00'})
    db.add(action)
    db.flush()
    return action


@pytest.mark.parametrize('content', ['pode imprimir', 'Imprimir.', 'pode imprimir Cliente Teste'])
def test_print_confirmation_never_selects_a_pending_payment(env, monkeypatch, content):
    factory, _, uid, _ = env
    selected = []
    monkeypatch.setattr(schedule, 'confirm_action', lambda db, message, identity, action, **kw: (selected.append(action.id), 'Confirmado pelo executor espião')[1])
    with factory() as db:
        payment = payment_draft(db, uid)
        identity = channels.authorized_identity(db, 'telegram', '123')
        response = agent.respond(db, incoming(db, uid, content, channel='telegram'), identity)
        assert selected == []
        assert 'prévia' in response
        assert payment.status == 'draft'
        assert db.query(PrintJob).count() == 0


def test_print_confirmation_selects_only_print_and_repeated_text_does_not_pay(env):
    factory, _, uid, _ = env
    with factory() as db:
        identity = channels.authorized_identity(db, 'telegram', '123')
        payment = payment_draft(db, uid)
        source = incoming(db, uid, 'Imprima Cliente Teste', channel='telegram')
        prepare_print(db, source, identity, AddressArgs(pais='PY', nome='Cliente Teste', cidade='Asunción'))
        printing = db.query(AssistantAction).filter_by(source_message_id=source.id).one()
        db.expire_all()
        response = agent.respond(db, incoming(db, uid, 'pode imprimir', channel='telegram'), identity)
        assert 'fila de impressão' in response
        assert db.query(PrintJob).one().request_key == printing.id
        assert payment.status == 'draft'
        repeated = agent.respond(db, incoming(db, uid, 'pode imprimir', channel='telegram'), identity)
        assert 'prévia' in repeated
        assert db.query(PrintJob).count() == 1
        assert payment.status == 'draft'


def test_print_confirmation_cannot_use_a_payment_uuid(env, monkeypatch):
    factory, _, uid, _ = env
    selected = []
    monkeypatch.setattr(schedule, 'confirm_action', lambda db, message, identity, action, **kw: (selected.append(action.id), 'Confirmado pelo executor espião')[1])
    with factory() as db:
        payment = payment_draft(db, uid)
        identity = channels.authorized_identity(db, 'telegram', '123')
        agent.respond(db, incoming(db, uid, f'pode imprimir {payment.id}', channel='telegram'), identity)
        assert selected == []
        assert payment.status == 'draft'


def test_named_print_selection_and_exact_callback_keep_other_drafts_pending(env):
    factory, _, uid, _ = env
    with factory() as db:
        identity = channels.authorized_identity(db, 'telegram', '123')
        payment = payment_draft(db, uid, 'Maria')
        prints = {}
        for name in ('Maria', 'João'):
            source = incoming(db, uid, f'Imprima {name}', channel='telegram')
            prepare_print(db, source, identity, AddressArgs(pais='PY', nome=name, cidade='Asunción'))
            prints[name] = db.query(AssistantAction).filter_by(source_message_id=source.id).one().id
        db.expire_all()
        response = agent.respond(db, incoming(db, uid, 'pode imprimir Maria', channel='telegram'), identity)
        assert 'fila de impressão' in response
        assert db.query(PrintJob).one().request_key == prints['Maria']
        assert payment.status == 'draft'

        choices = agent.respond(db, incoming(db, uid, 'confirmo', channel='telegram'), identity)
        assert {row[0]['callback_data'] for row in choices.reply_markup['inline_keyboard']} == {
            'v:' + prints['João'].hex, 'v:' + payment.id.hex,
        }
        assert db.query(PrintJob).count() == 1
        response = agent.respond(db, incoming(db, uid, '/acao a:' + prints['João'].hex, channel='telegram'), identity)
        assert 'fila de impressão' in response
        assert {job.request_key for job in db.query(PrintJob).all()} == set(prints.values())
        assert payment.status == 'draft'

        # Repeating the exact confirmation never retries an uncertain print job.
        job = db.query(PrintJob).filter_by(request_key=prints['João']).one()
        job.status = 'uncertain'
        db.flush()
        response = agent.respond(db, incoming(db, uid, '/acao a:' + prints['João'].hex, channel='telegram'), identity)
        assert 'Nenhuma alteração foi repetida' in response
        assert db.query(PrintJob).count() == 2
        assert job.status == 'uncertain' and payment.status == 'draft'


@pytest.mark.parametrize('content', ['confirmo', '/acao a:{id}'])
def test_generic_confirmation_and_exact_payment_callback_keep_existing_selection(env, monkeypatch, content):
    factory, _, uid, _ = env
    selected = []
    monkeypatch.setattr(schedule, 'confirm_action', lambda db, message, identity, action, **kw: (selected.append(action.id), 'Executor espião')[1])
    with factory() as db:
        payment = payment_draft(db, uid)
        identity = channels.authorized_identity(db, 'telegram', '123')
        response = agent.respond(db, incoming(db, uid, content.format(id=payment.id.hex), channel='telegram'), identity)
        assert response == 'Executor espião'
        assert selected == [payment.id]
        assert payment.status == 'draft'


@pytest.mark.parametrize('kind', ['impressao', 'frete_imprimir', 'arquivo_imprimir'])
def test_print_instruction_accepts_each_existing_print_kind(env, monkeypatch, kind):
    factory, _, uid, _ = env
    selected = []
    monkeypatch.setattr(schedule, 'confirm_action', lambda db, message, identity, action, **kw: (selected.append(action.id), 'Executor espião')[1])
    with factory() as db:
        action = payment_draft(db, uid)
        action.kind = kind
        db.flush()
        identity = channels.authorized_identity(db, 'telegram', '123')
        agent.respond(db, incoming(db, uid, 'pode imprimir', channel='telegram'), identity)
        assert selected == [action.id]
