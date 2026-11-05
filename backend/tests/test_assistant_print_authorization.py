"""Operational printing is available to linked staff without granting ERP writes."""
import io
import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from reportlab.pdfgen.canvas import Canvas

from test_address_manager import env
from test_assistant import setup, incoming
from app.api.endpoints import printing
from app.models import Usuario
from app.models.assistant import AssistantAction, AssistantIdentity, AssistantWhatsAppBridge, utcnow
from app.models.address_book import FreightOrder
from app.models.printing import PrintDevice, PrintJob, PrintSender
from app.models.usuario import UsuarioRole
from app.services import assistant_channels as channels, assistant_documents as documents, assistant_freight as freight
from app.services.assistant_print_policy import bot_print_job_authorized, may_print
from app.services.assistant_printing import AddressArgs, prepare_print
from app.services.assistant_schedule import confirm_action
from app.services.assistant_tools import execute_tool
from app.services.assistant_queries import QueryArgs


def staff_message(db, uid, text, channel='telegram', role=UsuarioRole.VENDEDOR):
    db.get(Usuario, uid).role = role
    message = incoming(db, uid, text, channel='telegram' if channel == 'telegram' else 'whatsapp')
    if channel == 'whatsapp_web':
        message.channel = channel
        message.conversation_id = '12000012345@g.us'
        if not db.get(AssistantWhatsAppBridge, 'primary'):
            db.add(AssistantWhatsAppBridge(id='primary', enabled=True, allowed_groups=[message.conversation_id]))
            db.add(AssistantIdentity(channel=channel, external_id=message.sender_id, user_id=uid))
    db.flush()
    identity = channels.authorized_identity(db, channel, message.sender_id)
    identity.can_register = False
    db.flush()
    return message, identity


def prepare_address(db, uid, channel='telegram', role=UsuarioRole.VENDEDOR):
    message, identity = staff_message(db, uid, 'Imprima para Cliente Teste no PY', channel, role)
    result = prepare_print(db, message, identity, AddressArgs(pais='PY', nome='Cliente Teste'))
    assert 'confirmacao' in result
    return message, identity, db.query(AssistantAction).filter_by(source_message_id=message.id).one()


@pytest.mark.parametrize('channel', ['telegram', 'whatsapp_web', 'whatsapp'])
@pytest.mark.parametrize('role', [UsuarioRole.VENDEDOR, UsuarioRole.GERENTE])
def test_staff_prints_without_register_capability_and_keeps_confirmation(env, channel, role):
    factory, _, uid, did = env
    with factory() as db:
        message, identity, action = prepare_address(db, uid, channel, role)
        assert db.query(PrintJob).count() == 0
        confirm, identity = staff_message(db, uid, 'Confirmo', channel, role)
        confirm_action(db, confirm, identity, action)
        job = db.query(PrintJob).one()
        assert action.status == 'executed' and action.result_id == job.id
        assert 'Nenhuma alteração' in confirm_action(db, confirm, identity, action)
        assert db.query(PrintJob).count() == 1
        db.commit()
        device = db.get(PrintDevice, uuid.UUID(did))
        assert bot_print_job_authorized(db, job)
        # HTTP requests start without previously loaded SQLite naive datetimes.
        db.expire_all()
        assert printing.claim(device, db)['id'] == str(job.id)
        assert printing.document(job.id, device, db).body.startswith(b'%PDF')


@pytest.mark.parametrize('kind', ['frete_emitir', 'folga', 'item_cadastrar', 'estoque_entrada', 'apelido'])
def test_print_capability_never_grants_purchase_or_other_writes(env, kind):
    factory, _, uid, _ = env
    with factory() as db:
        message, identity = staff_message(db, uid, 'Confirmo')
        action = AssistantAction(source_message_id=message.id, user_id=uid, kind=kind, payload={})
        db.add(action); db.flush()
        assert 'não tem permissão' in confirm_action(db, message, identity, action)
        assert action.status == 'draft' and db.query(PrintJob).count() == 0
        for operation in ('cotar_superfrete', 'preparar_etiqueta'):
            assert 'erro' in freight.execute(db, message, identity, operation, {})


@pytest.mark.parametrize('change', ['identity', 'user', 'group', 'binding', 'role'])
def test_revocation_blocks_confirmation_and_pending_dispatch(env, change):
    factory, _, uid, did = env
    with factory() as db:
        message, identity, action = prepare_address(db, uid)
        confirm_action(db, message, identity, action)
        job = db.query(PrintJob).one()
        # A second preview must not become executable after revocation either.
        second, _, pending = prepare_address(db, uid)
        if change == 'identity':identity.active = False
        elif change == 'user':db.get(Usuario, uid).ativo = False
        elif change == 'role':db.get(Usuario, uid).role = UsuarioRole.LIMPEZA
        elif change == 'group':
            message.conversation_id = second.conversation_id = '-100999'
        else:
            other = Usuario(nome='Outro', email='other-print@test.invalid', senha_hash='unused')
            db.add(other); db.flush(); identity.user_id = other.id
        db.flush()
        assert not may_print(db, second, identity)
        assert 'não tem permissão' in confirm_action(db, second, identity, pending)
        assert not bot_print_job_authorized(db, job)
        device = db.get(PrintDevice, uuid.UUID(did))
        db.flush(); db.expire_all()
        assert printing.claim(device, db).status_code == 204
        assert job.status == 'failed' and job.diagnostic['code'] == 'bot_authorization_revoked'
        assert job.snapshot and job.finished_at


def test_revocation_after_claim_prevents_pdf_download_without_repeating_job(env):
    factory, _, uid, did = env
    with factory() as db:
        message, identity, action = prepare_address(db, uid)
        confirm_action(db, message, identity, action); db.commit()
        job = db.query(PrintJob).one()
        device = db.get(PrintDevice, uuid.UUID(did))
        db.expire_all()
        assert printing.claim(device, db)['id'] == str(job.id)
        identity.active = False; db.flush()
        with pytest.raises(HTTPException) as denied:
            printing.document(job.id, device, db)
        assert denied.value.status_code == 403 and job.status == 'claimed'


def test_identity_channel_and_private_destination_cannot_be_swapped(env):
    factory, _, uid, _ = env
    with factory() as db:
        message, identity = staff_message(db, uid, 'Imprima')
        other = channels.authorized_identity(db, 'whatsapp', 'whatsapp:+5511888888888')
        assert not may_print(db, message, other)
        message, identity = staff_message(db, uid, 'Imprima', 'whatsapp_web')
        config = db.get(AssistantWhatsAppBridge, 'primary')
        config.allowed_groups = []; db.flush()
        assert not may_print(db, message, identity)
        message.conversation_id = '5511777777777@s.whatsapp.net'
        assert not may_print(db, message, identity)


def test_disabled_original_phone_cannot_be_confirmed_from_another_linked_phone(env):
    factory, _, uid, _ = env
    with factory() as db:
        message, identity, action = prepare_address(db, uid, 'whatsapp_web')
        identity.active = False
        replacement = AssistantIdentity(channel='whatsapp_web', external_id='whatsapp:+5511666666666', user_id=uid)
        db.add(replacement); db.flush()
        confirm = incoming(db, uid, 'Confirmo')
        confirm.channel = 'whatsapp_web'; confirm.sender_id = replacement.external_id
        confirm.conversation_id = message.conversation_id; db.flush()
        assert may_print(db, confirm, replacement)
        assert 'não tem permissão' in confirm_action(db, confirm, replacement, action)
        assert db.query(PrintJob).count() == 0


def test_seller_prints_received_pdf_without_registration_or_purchase(env, monkeypatch):
    factory, _, uid, _ = env
    buffer = io.BytesIO(); canvas = Canvas(buffer); canvas.drawString(20, 700, 'Teste'); canvas.showPage(); canvas.save()
    monkeypatch.setattr(documents, 'download_pdf', lambda *args, **kwargs: buffer.getvalue())
    with factory() as db:
        source, identity = staff_message(db, uid, 'Imprima este PDF')
        source.attachment = {'file_id': 'test-file', 'mime_type': 'application/pdf'}; db.flush()
        assert 'confirmacao' in documents.prepare_file(db, source, identity, documents.FilePrintArgs())
        action = db.query(AssistantAction).one()
        assert 'PDF encaminhado' in confirm_action(db, source, identity, action)
        job = db.query(PrintJob).one()
        assert job.source == 'bot_pdf_ephemeral' and bot_print_job_authorized(db, job)


def test_seller_can_find_operational_addresses_but_only_own_print_queue(env):
    factory, _, uid, did = env
    with factory() as db:
        message, identity, action = prepare_address(db, uid)
        confirm_action(db, message, identity, action)
        db.add(PrintSender(id='mona', name='Mona', lines=['Mona, endereço de teste']))
        other = Usuario(nome='Outro', email='other-history@test.invalid', senha_hash='unused')
        db.add(other); db.flush()
        db.add(PrintJob(device_id=uuid.UUID(did), user_id=other.id, request_key=uuid.uuid4(),
                        source='upload', pdf=b'test', sha256='f'*64, expires_at=utcnow()+timedelta(hours=1)))
        db.flush()
        result = execute_tool(db, message, identity, 'consultar_enderecos', {'termo': 'remetentes'})
        assert result['remetentes'][0]['nome'] == 'Mona'
        result = documents.query_prints(db, message, identity, QueryArgs())
        assert result['total'] == 1


def test_seller_can_print_owned_issued_label_without_buying_another(env, monkeypatch):
    factory, _, uid, _ = env
    monkeypatch.setattr(freight, 'SessionLocal', factory)
    monkeypatch.setattr(freight.sf, 'refresh', lambda db, key: db.get(FreightOrder, key))
    monkeypatch.setattr(freight.sf, 'summary', lambda row: {'state': row.state, 'label_url': row.label_url, 'recipient': 'Cliente'})
    monkeypatch.setattr(freight.sf, 'label_pdf', lambda url: b'%PDF-test')
    with factory() as db:
        message, identity = staff_message(db, uid, 'Imprima a etiqueta já emitida')
        order = FreightOrder(request_key=uuid.uuid4(), user_id=uid, environment=freight.sf.environment(), state='released', rates=[],
                             label_url='https://example.invalid/label.pdf', payload={'to': {'name': 'Cliente'}})
        db.add(order); db.commit()
        result = freight.execute(db, message, identity, 'preparar_impressao_etiqueta', {'freight_id': str(order.id)})
        assert 'confirmacao' in result
        action = db.query(AssistantAction).one()
        assert 'fila' in confirm_action(db, message, identity, action)
        assert bot_print_job_authorized(db, db.query(PrintJob).one())
