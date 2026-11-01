"""Operational defaults never learn quantities, identities or payment permissions."""
from copy import deepcopy
from datetime import timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from test_assistant import setup, incoming
from app.database import Base
from app.models.access import AuditEvent
from app.models.assistant import AssistantAction, AssistantKnowledge, utcnow
from app.models.usuario import Usuario, UsuarioRole
from app.services.assistant_channels import authorized_identity
from app.services import assistant_routines as routines


DEFAULTS = {'active': True, 'package': {'weight': 1, 'height': 15, 'width': 15, 'length': 15},
            'product': {'name': 'Camiseta', 'unitary_value': '50.00'}}


@pytest.fixture
def owner(setup):
    factory, _, user_id = setup
    with factory() as db:
        Base.metadata.create_all(db.get_bind(), tables=[AuditEvent.__table__])
        user = db.get(Usuario, user_id)
        user.email, user.role = 'lucas@eleven.com', UsuarioRole.ADMIN
        db.commit()
    return factory, user_id


def prepare(db, user_id, args=None, channel='telegram'):
    message = incoming(db, user_id, 'Guarde este padrão de frete para as próximas etiquetas', channel=channel)
    identity = authorized_identity(db, message.channel, message.sender_id)
    result = routines.prepare_routine(db, message, identity, routines.RoutineArgs.model_validate(args or DEFAULTS))
    action = db.query(AssistantAction).filter_by(source_message_id=message.id).first()
    return message, identity, result, action


def test_routine_only_persists_after_confirmation_and_crosses_conversations(owner):
    factory, user_id = owner
    with factory() as db:
        source, identity, result, action = prepare(db, user_id)
        assert routines.get_routine(db) is None
        assert result['confirmacao'].reply_markup
        assert '1 kg' in result['confirmacao'] and '15 × 15 × 15' in result['confirmacao']
        assert 'R$ 50,00' in result['confirmacao'] and 'quantidade' in result['confirmacao']
        confirm = incoming(db, user_id, 'confirmo', channel='telegram')
        assert 'salvo' in routines.confirm_routine(db, confirm, action)
        assert action.status == 'executed'
        assert 'Nenhuma alteração' in routines.confirm_routine(db, confirm, action)
        db.commit()
    with factory() as db:
        message = incoming(db, user_id, 'Qual o padrão de frete?', channel='whatsapp')
        identity = authorized_identity(db, message.channel, message.sender_id)
        saved = routines.query_routine(db, message, identity)['padrao']
        assert saved['revision'] == 1 and saved['updated_by'] == str(user_id)
        assert saved['package']['weight'] == 1 and saved['product']['unitary_value'] == '50.00'
        assert 'quantity' not in saved['product']
        audit = db.query(AuditEvent).one()
        assert audit.user_id == user_id and audit.entity_id == routines.ROUTINE_KEY
        assert audit.changes['revision'] == {'before': None, 'after': 1}
        assert set(audit.changes) == {'revision', 'active', 'package', 'product'}


def test_only_owner_writes_and_authorized_managers_read(owner):
    factory, user_id = owner
    with factory() as db:
        routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        user = db.get(Usuario, user_id)
        user.role = UsuarioRole.GERENTE
        db.flush()
        message, identity, result, action = prepare(db, user_id)
        assert 'Somente Lucas' in result['erro'] and action is None
        assert routines.query_routine(db, message, identity)['padrao']['revision'] == 1
        with pytest.raises(HTTPException) as denied:
            routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=1)
        assert denied.value.status_code == 403
        identity.can_register = False
        assert 'erro' in routines.query_routine(db, message, identity)
        identity.can_register = True
        identity.active = False
        assert 'erro' in routines.query_routine(db, message, identity)


def test_observation_or_mismatched_identity_cannot_change_defaults(owner):
    factory, user_id = owner
    with factory() as db:
        message = incoming(db, user_id, 'Padrão 1 kg', channel='telegram', reply=False)
        identity = authorized_identity(db, message.channel, message.sender_id)
        assert 'erro' in routines.prepare_routine(db, message, identity, DEFAULTS)
        message.should_reply = True
        identity.channel = 'whatsapp'
        assert 'erro' in routines.prepare_routine(db, message, identity, DEFAULTS)
        assert db.query(AssistantAction).count() == 0


def test_confirmation_requires_same_conversation_unexpired_active_owner(owner):
    factory, user_id = owner
    with factory() as db:
        _, _, _, action = prepare(db, user_id)
        wrong = incoming(db, user_id, 'confirmo', channel='whatsapp')
        assert 'mesma conversa' in routines.confirm_routine(db, wrong, action)
        correct = incoming(db, user_id, 'confirmo', channel='telegram')
        correct.conversation_id = 'other-group'
        assert 'mesma conversa' in routines.confirm_routine(db, correct, action)
        correct.conversation_id = '-100123'
        action.created_at = utcnow() - timedelta(hours=25)
        assert 'expirada' in routines.confirm_routine(db, correct, action)
        action.created_at = utcnow()
        action.status = 'cancelled'
        assert 'Nenhuma alteração' in routines.confirm_routine(db, correct, action)
        action.status = 'draft'
        db.get(Usuario, user_id).ativo = False
        assert 'Somente Lucas' in routines.confirm_routine(db, correct, action)
        assert routines.get_routine(db) is None


def test_stale_preview_cannot_overwrite_a_newer_default(owner):
    factory, user_id = owner
    with factory() as db:
        _, _, _, first = prepare(db, user_id)
        _, _, _, stale = prepare(db, user_id, {**DEFAULTS, 'product': {'name': 'Boné', 'unitary_value': 80}})
        confirm = incoming(db, user_id, 'confirmo', channel='telegram')
        assert 'salvo' in routines.confirm_routine(db, confirm, first)
        assert 'mudou depois da prévia' in routines.confirm_routine(db, confirm, stale)
        assert stale.status == 'draft'
        assert routines.get_routine(db)['product']['name'] == 'Camiseta'
        with pytest.raises(HTTPException) as conflict:
            routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        assert conflict.value.status_code == 409


def test_updates_and_disable_do_not_mutate_prepared_or_merged_values(owner):
    factory, user_id = owner
    with factory() as db:
        routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        merged, metadata = routines.merge_quote_defaults(db, {'quantidade': 3})
        routines.save_routine(db, {'active': False}, user_id=user_id, expected_revision=1)
        assert routines.get_routine(db)['revision'] == 2
        assert routines.get_routine(db)['active'] is False
        assert merged['package']['weight'] == 1 and merged['products'][0]['quantity'] == 3
        assert metadata['revision'] == 1
        assert routines.merge_quote_defaults(db, {'quantidade': 3}) == (
            {}, {'key': None, 'revision': None, 'applied_fields': [], 'missing_fields': ['package', 'products']})


def test_merge_applies_saved_package_and_explicit_quantity_only(owner):
    factory, user_id = owner
    with factory() as db:
        routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        args = {'quantidade': 4, 'address_id': 'specific-address', 'sender_id': 'chosen-sender', 'invoice': '1' * 44}
        original = deepcopy(args)
        merged, metadata = routines.merge_quote_defaults(db, args)
        assert args == original
        assert merged['products'] == [{'name': 'Camiseta', 'unitary_value': '50.00', 'quantity': 4}]
        assert merged['address_id'] == args['address_id'] and merged['sender_id'] == args['sender_id']
        assert merged['invoice'] == args['invoice'] and 'non_commercial' not in merged
        assert metadata['applied_fields'] == ['package', 'product'] and metadata['missing_fields'] == []
        missing, meta = routines.merge_quote_defaults(db, {})
        assert 'products' not in missing and meta['missing_fields'] == ['quantidade']
        assert routines.get_routine(db)['product'] == DEFAULTS['product']


def test_explicit_package_and_products_win_without_saving_them(owner):
    factory, user_id = owner
    with factory() as db:
        routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        args = {'package': {'weight': 2, 'height': 20, 'width': 25, 'length': 30},
                'products': [{'name': 'Sapato', 'unitary_value': '120.00', 'quantity': 2}], 'quantidade': 9}
        merged, metadata = routines.merge_quote_defaults(db, args)
        assert merged['package'] == args['package'] and merged['products'] == args['products']
        assert 'quantidade' not in merged and metadata['applied_fields'] == []
        assert routines.get_routine(db)['package']['weight'] == 1
        explicit_empty, _ = routines.merge_quote_defaults(db, {'package': {}, 'products': []})
        assert explicit_empty == {'package': {}, 'products': []}  # Full quote validation must reject these.


@pytest.mark.parametrize('quantity', [0, -1, 10001, True, 1.5, '2'])
def test_invalid_quantity_is_not_invented_or_coerced(owner, quantity):
    factory, user_id = owner
    with factory() as db:
        routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        with pytest.raises(ValidationError):
            routines.merge_quote_defaults(db, {'quantidade': quantity})


@pytest.mark.parametrize('extra', [
    {'quantidade': 4}, {'sender_id': 'mona'}, {'endereco': {'nome': 'Outro'}},
    {'non_commercial': True}, {'invoice': '1' * 44}, {'service': 1},
    {'product': {'name': 'Camiseta', 'unitary_value': 50, 'quantity': 2}},
    {'product': {'name': '  ', 'unitary_value': 50}},
    {'product': {'name': 'Camiseta', 'unitary_value': 'NaN'}},
    {'package': {'weight': 0, 'height': 15, 'width': 15, 'length': 15}},
])
def test_template_rejects_order_specific_fields_and_invalid_values(extra):
    with pytest.raises(ValidationError):
        routines.RoutineArgs.model_validate({**DEFAULTS, **extra})


def test_no_preset_is_created_by_lookup_and_invalid_storage_never_applies(setup):
    factory, _, _ = setup
    with factory() as db:
        merged, metadata = routines.merge_quote_defaults(db, {'quantidade': 2})
        assert merged == {} and metadata['missing_fields'] == ['package', 'products']
        assert db.query(AssistantKnowledge).count() == 0
        db.add(AssistantKnowledge(key=routines.ROUTINE_KEY, kind=routines.ROUTINE_KIND,
                                 data={**DEFAULTS, 'revision': 1, 'non_commercial': True}))
        db.flush()
        with pytest.raises(HTTPException) as invalid:
            routines.merge_quote_defaults(db, {'quantidade': 2})
        assert invalid.value.status_code == 409


def test_package_only_or_product_only_default_is_supported(owner):
    factory, user_id = owner
    with factory() as db:
        routines.save_routine(db, {'package': DEFAULTS['package']}, user_id=user_id, expected_revision=0)
        merged, metadata = routines.merge_quote_defaults(db, {'quantidade': 2})
        assert merged['package'] == DEFAULTS['package'] and metadata['missing_fields'] == ['products']
        routines.save_routine(db, {'product': DEFAULTS['product']}, user_id=user_id, expected_revision=1)
        merged, metadata = routines.merge_quote_defaults(db, {'quantidade': 2})
        assert merged['products'][0]['quantity'] == 2 and metadata['missing_fields'] == ['package']
