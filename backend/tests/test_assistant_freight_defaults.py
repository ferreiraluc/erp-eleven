"""Bot shipping defaults integrated with validated quotes and immutable payment previews."""
from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from test_address_manager import env
from test_assistant import setup, incoming
from test_assistant_routines import DEFAULTS
from app.models.address_book import FreightOrder, SavedAddress
from app.models.assistant import AssistantAction
from app.models.printing import PrintJob, PrintSender
from app.models.usuario import Usuario
from app.services import assistant_freight as freight, assistant_routines as routines, superfrete as sf
from app.services.assistant_channels import authorized_identity
from app.services.assistant_tools import execute_tool


@pytest.fixture
def freight_defaults(env, monkeypatch):
    factory, _, user_id, _ = env
    captures = []
    carts = []
    with factory() as db:
        db.get(Usuario, user_id).email = 'lucas@eleven.com'
        db.add(PrintSender(id='debora', name='Débora Almeida Santos', lines=['Remetente de teste'],
                           data={'pais': 'BR', 'nome': 'Débora Almeida Santos'}))
        address = SavedAddress(label='Cliente de teste', data={'pais': 'BR', 'nome': 'Cliente de teste'},
                               created_by=user_id)
        db.add(address)
        db.flush()
        routines.save_routine(db, DEFAULTS, user_id=user_id, expected_revision=0)
        address_id = address.id
        db.commit()

    def forbidden(*args, **kwargs):
        raise AssertionError('No real provider, purchase or printing is allowed in defaults tests')

    def quote_order(db, body, actor_id):
        captures.append(body.model_dump(mode='json'))
        sender = db.get(PrintSender, body.sender_id)
        row = FreightOrder(request_key=body.request_key, user_id=actor_id, address_id=body.address_id,
                           environment='sandbox', state='quoted',
                           rates=[{'id': 1, 'name': 'PAC', 'price': 20, 'delivery_time': 5}],
                           payload={'from': {'name': sender.name},
                                    'to': {'name': db.get(SavedAddress, body.address_id).data['nome']},
                                    'volumes': body.package.model_dump(mode='json'),
                                    'products': [item.model_dump(mode='json') for item in body.products],
                                    'options': {'non_commercial': body.non_commercial},
                                    '_request': body.model_dump(mode='json', exclude={'request_key'})})
        db.add(row)
        db.flush()
        return row

    def cart(db, key, service):
        carts.append((str(key), service))
        row = db.get(FreightOrder, key)
        row.service, row.state, row.price = service, 'pending', Decimal('20.00')
        row.provider_id = 'fake-provider-cart'
        db.commit()
        return row

    monkeypatch.setattr(sf, 'call', forbidden)
    monkeypatch.setattr(sf, 'checkout', forbidden)
    monkeypatch.setattr(sf, 'print_label', forbidden)
    monkeypatch.setattr(sf, 'quote_order', quote_order)
    monkeypatch.setattr(sf, 'cart', cart)
    monkeypatch.setattr(freight, 'SessionLocal', factory)
    return factory, user_id, address_id, captures, carts


def quote_args(address_id, **changes):
    return {'address_id': str(address_id), 'sender_id': 'DÉBORA SANTOS', 'quantidade': 3,
            'invoice': '1' * 44, **changes}


def quote(db, user_id, arguments):
    message = incoming(db, user_id, 'Cote 3 camisetas com remetente Débora Santos', channel='telegram')
    identity = authorized_identity(db, message.channel, message.sender_id)
    result = execute_tool(db, message, identity, 'cotar_superfrete', arguments)
    return message, identity, result


def test_quote_uses_saved_package_template_and_current_sender(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    with factory() as db:
        message, _, result = quote(db, user_id, quote_args(address_id))
        assert result['state'] == 'quoted' and len(captures) == 1
        request = captures[0]
        assert request['package'] == DEFAULTS['package']
        assert request['products'] == [{'name': 'Camiseta', 'unitary_value': '50.00', 'quantity': 3}]
        assert request['sender_id'] == 'debora'
        assert request['invoice'] == '1' * 44 and request['non_commercial'] is False
        row = db.query(FreightOrder).filter_by(request_key=message.id).one()
        assert row.payload['_assistant_defaults'] == {
            'key': 'shipping:defaults', 'revision': 1,
            'applied_fields': ['package', 'product'], 'missing_fields': []}
        assert db.query(AssistantAction).count() == 0 and db.query(PrintJob).count() == 0


def test_explicit_package_and_products_win_over_defaults(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    package = {'weight': 2, 'height': 20, 'width': 25, 'length': 30}
    products = [{'name': 'Boné', 'quantity': 2, 'unitary_value': '89.00'}]
    with factory() as db:
        message, _, result = quote(db, user_id, quote_args(address_id, package=package, products=products,
                                                         quantidade=None))
        assert result['state'] == 'quoted'
        assert captures[0]['package'] == package and captures[0]['products'] == products
        row = db.query(FreightOrder).filter_by(request_key=message.id).one()
        assert '_assistant_defaults' not in row.payload
        text = freight.quote_preview(row)
        assert '2 kg' in text and '2 × Boné' in text and 'R$ 89,00' in text
        assert 'Padrão da equipe aplicado' not in text
        assert routines.get_routine(db)['package']['weight'] == 1


def test_current_products_can_use_only_saved_package(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    products = [{'name': 'Calça', 'quantity': 4, 'unitary_value': '150.00'}]
    with factory() as db:
        message, _, result = quote(db, user_id, quote_args(address_id, products=products, quantidade=None))
        assert result['state'] == 'quoted' and captures[0]['products'] == products
        row = db.query(FreightOrder).filter_by(request_key=message.id).one()
        assert row.payload['_assistant_defaults']['applied_fields'] == ['package']
        assert 'Padrão da equipe aplicado: pacote (revisão 1)' in freight.quote_preview(row)


def test_missing_quantity_never_reuses_another_order_or_calls_provider(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    with factory() as db:
        quote(db, user_id, quote_args(address_id, quantidade=8))
        _, _, missing = quote(db, user_id, quote_args(address_id, quantidade=None))
        assert missing['campos'] == ['quantidade'] and 'erro' in missing
        assert len(captures) == 1 and db.query(FreightOrder).count() == 1


@pytest.mark.parametrize('changes', [
    {'invoice': ''}, {'invoice': '123'}, {'quantidade': 0}, {'quantidade': True},
    {'products': []}, {'package': {'weight': 0, 'height': 15, 'width': 15, 'length': 15}},
])
def test_missing_fiscal_data_or_invalid_explicit_fields_cannot_call_provider(freight_defaults, changes):
    factory, user_id, address_id, captures, carts = freight_defaults
    with factory() as db:
        with pytest.raises(ValidationError):
            quote(db, user_id, quote_args(address_id, **changes))
        assert captures == [] and carts == []
        assert db.query(FreightOrder).count() == 0 and db.query(AssistantAction).count() == 0


def test_disabled_default_requires_current_package_and_products(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    with factory() as db:
        routines.save_routine(db, {'active': False}, user_id=user_id, expected_revision=1)
        _, _, missing = quote(db, user_id, quote_args(address_id))
        assert missing['campos'] == ['package', 'products'] and captures == []


def test_reexecution_returns_existing_snapshot_even_after_default_changes(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    with factory() as db:
        message, identity, result = quote(db, user_id, quote_args(address_id))
        row = db.query(FreightOrder).filter_by(request_key=message.id).one()
        before = deepcopy(row.payload)
        routines.save_routine(db, {'active': True, 'package': {'weight': 2, 'height': 20, 'width': 20, 'length': 20},
                                  'product': {'name': 'Outra peça', 'unitary_value': '99.00'}},
                              user_id=user_id, expected_revision=1)
        repeated = execute_tool(db, message, identity, 'cotar_superfrete', quote_args(address_id, quantidade=9))
        assert repeated['id'] == result['id'] and len(captures) == 1
        assert row.payload == before and row.payload['_assistant_defaults']['revision'] == 1
        assert row.payload['products'][0]['quantity'] == 3


def test_quote_and_payment_previews_preserve_original_default_snapshot(freight_defaults):
    factory, user_id, address_id, _, carts = freight_defaults
    with factory() as db:
        message, _, result = quote(db, user_id, quote_args(address_id))
        row = db.query(FreightOrder).filter_by(request_key=message.id).one()
        quote_preview = freight.quote_preview(row)
        assert '1 kg' in quote_preview and '15 × 15 × 15' in quote_preview
        assert '3 × Camiseta' in quote_preview and 'R$ 50,00 por unidade' in quote_preview
        assert 'revisão 1' in quote_preview and quote_preview.reply_markup
        routines.save_routine(db, {'active': False}, user_id=user_id, expected_revision=1)
        selection = incoming(db, user_id, 'PAC', channel='telegram')
        selection_id = selection.id
        db.commit()
    with factory() as db:
        from app.models.assistant import AssistantMessage
        selection = db.get(AssistantMessage, selection_id)
        identity = authorized_identity(db, selection.channel, selection.sender_id)
        response = execute_tool(db, selection, identity, 'preparar_etiqueta',
                                {'freight_id': result['id'], 'service': 1})
        preview = response['confirmacao']
        assert '1 kg' in preview and '15 × 15 × 15' in preview
        assert '3 × Camiseta' in preview and 'R$ 50,00 por unidade' in preview
        assert 'revisão 1' in preview and 'Nenhuma compra realizada' in preview
        assert preview.reply_markup and len(carts) == 1
        action = db.query(AssistantAction).filter_by(source_message_id=selection.id).one()
        assert action.kind == 'frete_emitir' and action.status == 'draft'
        assert 'revisão 1' in action.payload['shipment_details']
        assert db.query(PrintJob).count() == 0


def test_unknown_or_inactive_sender_stops_before_quote(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    with factory() as db:
        _, _, unknown = quote(db, user_id, quote_args(address_id, sender_id='Pessoa inexistente'))
        assert unknown['codigo'] == 'remetente_nao_encontrado'
        db.get(PrintSender, 'debora').active = False
        db.flush()
        _, _, inactive = quote(db, user_id, quote_args(address_id, sender_id='DÉBORA'))
        assert inactive['codigo'] == 'remetente_inativo'
        assert captures == []


def test_disabled_assistant_permission_cannot_use_shipping_defaults(freight_defaults):
    factory, user_id, address_id, captures, _ = freight_defaults
    with factory() as db:
        message = incoming(db, user_id, 'Cote o frete', channel='telegram')
        identity = authorized_identity(db, message.channel, message.sender_id)
        identity.can_register = False
        result = execute_tool(db, message, identity, 'cotar_superfrete', quote_args(address_id))
        assert 'erro' in result and captures == []


def test_routine_tool_and_action_dispatchers_keep_confirmation_required(freight_defaults):
    from app.services.assistant_schedule import action_preview, confirm_action
    factory, user_id, _, captures, carts = freight_defaults
    with factory() as db:
        message = incoming(db, user_id, 'Lembre o padrão de 2 kg para as próximas etiquetas', channel='telegram')
        identity = authorized_identity(db, message.channel, message.sender_id)
        current = execute_tool(db, message, identity, 'consultar_padrao_frete', {})
        assert current['padrao']['revision'] == 1
        updated = {**DEFAULTS, 'package': {**DEFAULTS['package'], 'weight': 2}}
        prepared = execute_tool(db, message, identity, 'preparar_padrao_frete', updated)
        action = db.query(AssistantAction).filter_by(source_message_id=message.id).one()
        assert prepared['confirmacao'] == action_preview(action)
        assert '2 kg' in prepared['confirmacao'] and prepared['confirmacao'].reply_markup
        assert routines.get_routine(db)['package']['weight'] == 1
        confirmation = incoming(db, user_id, 'confirmo', channel='telegram')
        assert 'salvo' in confirm_action(db, confirmation, identity, action)
        saved = execute_tool(db, confirmation, identity, 'consultar_padrao_frete', {})['padrao']
        assert saved['revision'] == 2 and saved['package']['weight'] == 2
        assert captures == carts == [] and db.query(PrintJob).count() == 0
