"""Freight recovery uses disposable SQLite and fake provider responses only."""
import copy
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
import requests
from fastapi import HTTPException

from test_assistant import setup, incoming
from test_address_manager import env
from app.models import Usuario
from app.models.usuario import UsuarioRole
from app.models.address_book import FreightOrder, SavedAddress
from app.models.assistant import AssistantDelivery, AssistantIdentity, utcnow
from app.services import freight_recovery as recovery, superfrete as sf
from app.services.superfrete_errors import ProviderError, response_error, valid_document


RATES = [{'id': 1, 'name': 'PAC', 'price': '20.00', 'delivery_time': 5}]
ADDRESS = {'pais': 'BR', 'nome': 'Cliente sintético', 'cpf': '12345678909', 'endereco': 'Rua Exemplo',
           'numero': '10', 'bairro': 'Centro', 'cidade': 'Cidade Exemplo', 'estado': 'SP', 'cep': '01001000'}


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch):
    monkeypatch.setattr(sf.settings, 'SUPERFRETE_TOKEN', 'fixture-token')
    monkeypatch.setattr(sf.settings, 'SUPERFRETE_CONTACT_EMAIL', 'fixture@example.test')
    monkeypatch.setattr(sf.settings, 'SUPERFRETE_SANDBOX', True)
    monkeypatch.setattr(sf.requests, 'request', lambda *a, **k: pytest.fail('Provider request must be mocked'))
    recovery._health.clear()


@pytest.fixture
def queue(env, monkeypatch):
    factory, _, user_id, _ = env
    monkeypatch.setattr(recovery, 'SessionLocal', factory)
    return factory, user_id


def order(factory, user_id, *, state='quoted', kind=None, bot=True, **changes):
    with factory() as db:
        source = incoming(db, user_id, 'Cote esta etiqueta', channel='telegram') if bot else None
        payload = {'from': {'name': 'Remetente sintético', 'city': 'Cidade Exemplo', 'postal_code': '01001000'},
                   'to': {'name': 'Cliente sintético', 'city': 'Cidade Exemplo', 'postal_code': '01001000'},
                   'volumes': {'weight': 1, 'height': 10, 'width': 15, 'length': 20},
                   'options': {'non_commercial': True}, '_quoted_at': utcnow().isoformat()}
        payload.update(changes.pop('payload', {}))
        row = FreightOrder(request_key=source.id if source else uuid.uuid4(), user_id=user_id,
                           environment='sandbox', payload=payload, rates=copy.deepcopy(RATES), state=state,
                           recovery_kind=kind, recovery_check_at=utcnow()-timedelta(seconds=1) if kind else None,
                           **changes)
        db.add(row); db.commit()
        return row.id


def due(factory, key):
    with factory() as db:
        row = db.get(FreightOrder, key)
        if row.recovery_kind:
            row.recovery_check_at = utcnow()-timedelta(seconds=1)
        db.commit()


def quote_input(db, user_id, document='12345678909'):
    saved = SavedAddress(label='Fixture', data=ADDRESS | {'cpf': document}, created_by=user_id)
    db.add(saved); db.flush()
    return sf.QuoteInput(request_key=uuid.uuid4(), address_id=saved.id, remetente=ADDRESS,
                         package={'weight': 1, 'height': 10, 'width': 15, 'length': 20},
                         products=[{'name': 'Camiseta', 'quantity': 1, 'unitary_value': 10}], non_commercial=True)


@pytest.mark.parametrize('document', ['123.456.789-09', '52998224725', '11.222.333/0001-81'])
def test_valid_checksum_accepts_formatted_cpf_and_cnpj(document):
    assert valid_document(document)
    assert sf.party(ADDRESS | {'cpf': document}, recipient=True)['document'].isdigit()


@pytest.mark.parametrize('document', ['12345678900', '52998224724', '11222333000180', '00000000000', '11111111111', '123'])
def test_invalid_document_is_validation_before_any_quote_or_purchase(queue, monkeypatch, document):
    factory, user_id = queue
    calls = []
    monkeypatch.setattr(sf, 'call', lambda *a: calls.append(a) or RATES)
    with factory() as db:
        body = quote_input(db, user_id, document)
        with pytest.raises(HTTPException) as error:
            sf.quote_order(db, body, user_id)
        assert error.value.status_code == 400
        assert db.query(FreightOrder).count() == 0 and calls == []


@pytest.mark.parametrize('status', [400, 422])
def test_provider_invalid_document_is_not_reported_as_outage(queue, monkeypatch, status):
    factory, user_id = queue
    private = 'PRIVATE_DOCUMENT_12345678900'
    monkeypatch.setattr(sf.requests, 'request', lambda *a, **k: SimpleNamespace(
        status_code=status, json=lambda: {'errors': {'to.document': [private]}}))
    key = order(factory, user_id)
    with factory() as db:
        row = sf.calculate(db, db.get(FreightOrder, key))
        assert row.state == 'rejected' and row.error_category == 'validation'
        assert 'CPF/CNPJ' in row.error and private not in row.error
        assert row.recovery_kind is None and row.recovery_check_at is None


@pytest.mark.parametrize(('status', 'category', 'rejected'), [(401, 'configuration', True), (403, 'configuration', True),
    (429, 'unavailable', True), (500, 'unavailable', False), (503, 'unavailable', False), (302, 'unknown', False)])
def test_provider_rejection_is_explicit_and_safe_to_distinguish(status, category, rejected):
    error = response_error(status, {'error': 'RAW_BODY_MUST_NOT_LEAK'})
    assert error.category == category and error.rejected is rejected
    assert 'RAW_BODY' not in error.detail


def test_quote_recovers_once_notifies_original_topic_and_keeps_request_identity(queue, monkeypatch):
    factory, user_id = queue
    calls = []
    responses = iter([ProviderError('unavailable', 'Serviço indisponível'), copy.deepcopy(RATES)])
    def provider(method, path, body=None):
        calls.append((method, path))
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(sf, 'call', provider)
    with factory() as db:
        body = quote_input(db, user_id)
        source = incoming(db, user_id, 'Cote esta etiqueta', channel='telegram')
        source.conversation_id += ':7'
        body.request_key = source.id
        row = sf.quote_order(db, body, user_id)
        key = row.id
        assert row.state == 'retry_waiting' and row.recovery_kind == 'quote'
        db.commit()
        assert sf.quote_order(db, body, user_id).id == key
    due(factory, key)
    assert recovery.process_recovery() is True and recovery.process_recovery() is False
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.state == 'quoted' and row.recovery_kind is None and row.recovery_attempts == 1
        delivery = db.query(AssistantDelivery).one()
        assert delivery.user_id == user_id and delivery.destination == '-100123:7'
        assert delivery.reply_markup['inline_keyboard'][0][0]['callback_data'] == f'q:{key.hex}:1'
        recovery.notify(db, row, 'quoted'); db.commit()
        assert db.query(AssistantDelivery).count() == db.query(FreightOrder).count() == 1
    assert calls == [('POST', 'calculator'), ('POST', 'calculator')]


def test_cart_proven_rejection_retries_once_without_checkout(queue, monkeypatch):
    factory, user_id = queue
    calls = []
    def provider(method, path, body=None):
        calls.append((method, path, copy.deepcopy(body)))
        assert path == 'cart'
        if len(calls) == 1:
            raise response_error(429, {})
        return {'id': 'provider-one', 'price': '21.00'}
    monkeypatch.setattr(sf, 'call', provider)
    key = order(factory, user_id)
    with factory() as db:
        row = sf.cart(db, key, 1)
        assert row.state == 'retry_waiting' and row.recovery_kind == 'cart'
    due(factory, key)
    assert recovery.process_recovery()
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.state == 'pending' and row.price == Decimal('21.00')
        assert row.provider_id == 'provider-one' and row.recovery_kind is None
        assert db.query(AssistantDelivery).one().event_key == f'freight-recovery:{key}:pending'
    assert len(calls) == 2 and calls[0][2]['options']['tags'] == calls[1][2]['options']['tags']


@pytest.mark.parametrize('failure', [requests.ReadTimeout('fixture'), requests.ConnectionError('fixture')])
def test_cart_uncertain_network_outcome_never_reposts_or_matches_by_name(queue, monkeypatch, failure):
    factory, user_id = queue
    calls = []
    def provider(method, url, **kwargs):
        path = url.split('/api/v0/')[1]; calls.append((method, path))
        if path == 'cart':
            raise failure
        if path.startswith('me/orders?'):
            data = {'data': [{'id': 'unrelated', 'to': {'name': 'Cliente sintético'}}], 'meta': {'last_page': 1}}
        else:
            assert path == 'order/info/unrelated'
            data = {'id': 'unrelated', 'price': '20.00', 'status': 'pending', 'tags': [{'tag': 'different-request'}]}
        return SimpleNamespace(status_code=200, json=lambda: data)
    monkeypatch.setattr(sf.requests, 'request', provider)
    key = order(factory, user_id)
    with factory() as db:
        row = sf.cart(db, key, 1)
        assert row.state == 'uncertain' and row.recovery_kind == 'reconcile'
        with pytest.raises(HTTPException):
            sf.cart(db, key, 1)
    for _ in range(2):
        due(factory, key); assert recovery.process_recovery()
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.state == 'uncertain' and row.provider_id is None and row.recovery_kind == 'reconcile'
        assert db.query(AssistantDelivery).count() == 0
    assert calls.count(('POST', 'cart')) == 1 and all(method == 'GET' for method, _ in calls[1:])


def test_connect_timeout_is_the_only_network_failure_safe_to_retry_cart(queue, monkeypatch):
    factory, user_id = queue
    def unreachable(*args, **kwargs):
        raise requests.ConnectTimeout('before connection')
    monkeypatch.setattr(sf.requests, 'request', unreachable)
    key = order(factory, user_id)
    with factory() as db:
        row = sf.cart(db, key, 1)
        assert row.state == 'retry_waiting' and row.recovery_kind == 'cart'


def test_exact_tag_reconciles_uncertain_cart_then_requests_payment_confirmation(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id, state='uncertain', kind='reconcile', service=1)
    with factory() as db:
        row = db.get(FreightOrder, key); row.payload = {**row.payload, '_provider_tag': f'eleven:{key}'}; db.commit()
    calls = []
    def provider(method, path, body=None):
        calls.append((method, path)); assert method == 'GET'
        if path.startswith('me/orders?'):
            return {'data': [{'id': 'correct', 'to': {'name': 'Cliente sintético'}},
                             {'id': 'unrelated', 'to': {'name': 'Cliente sintético'}}], 'meta': {'last_page': 1}}
        identifier = path.rsplit('/', 1)[-1]
        return {'id': identifier, 'price': '23.45', 'status': 'pending',
                'tags': [{'tag': f'eleven:{key}' if identifier == 'correct' else 'different-request'}]}
    monkeypatch.setattr(sf, 'call', provider)
    assert recovery.process_recovery()
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.provider_id == 'correct' and row.state == 'pending' and row.price == Decimal('23.45')
        assert row.recovery_kind is None
        delivery = db.query(AssistantDelivery).one()
        assert delivery.reply_markup['inline_keyboard'][0][0]['callback_data'] == f'q:{key.hex}:1'
    assert not any(path == 'checkout' for _, path in calls)


def test_checkout_timeout_remains_blocked_even_when_provider_reports_pending(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id, state='pending', provider_id='provider-one', price=Decimal('20.00'), service=1)
    calls = []
    def provider(method, path, body=None):
        calls.append((method, path))
        if path == 'checkout':
            raise ProviderError('unavailable', 'Unknown outcome')
        return {'id': 'provider-one', 'status': 'pending'}
    monkeypatch.setattr(sf, 'call', provider)
    with factory() as db:
        assert sf.checkout(db, key, Decimal('20.00')).state == 'uncertain'
        assert sf.refresh(db, key).state == 'uncertain'
        with pytest.raises(HTTPException):
            sf.checkout(db, key, Decimal('20.00'))
        assert db.get(FreightOrder, key).recovery_kind is None
    assert recovery.process_recovery() is False
    assert calls == [('POST', 'checkout'), ('GET', 'order/info/provider-one')]


@pytest.mark.parametrize('change', ['inactive', 'role', 'identity', 'registration', 'reassignment'])
def test_permission_change_stops_recovery_before_any_provider_call(queue, monkeypatch, change):
    factory, user_id = queue
    key = order(factory, user_id, state='retry_waiting', kind='quote')
    with factory() as db:
        user = db.get(Usuario, user_id)
        identity = db.query(AssistantIdentity).filter_by(user_id=user_id, channel='telegram').one()
        if change == 'inactive': user.ativo = False
        elif change == 'role': user.role = UsuarioRole.VENDEDOR
        elif change == 'identity': identity.active = False
        elif change == 'registration': identity.can_register = False
        else:
            other = Usuario(nome='Other', email='other@example.test', senha_hash='unused', role=UsuarioRole.GERENTE)
            db.add(other); db.flush(); identity.user_id = other.id
        db.commit()
    monkeypatch.setattr(sf, 'call', lambda *a, **k: pytest.fail('Unauthorized recovery reached provider'))
    assert recovery.process_recovery()
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.recovery_kind is None and row.recovery_check_at is None
        assert 'sem permissão' in row.error


def test_service_health_is_cached_but_configuration_failure_is_not_outage(monkeypatch):
    calls = []
    monkeypatch.setattr(sf, 'call', lambda *a: calls.append(a) or {'data': []})
    assert recovery.service_status()['availability'] == 'available'
    assert recovery.service_status()['availability'] == 'available' and len(calls) == 1
    monkeypatch.setattr(sf.settings, 'SUPERFRETE_TOKEN', '')
    assert recovery.service_status() == {'configured': False, 'environment': 'sandbox', 'availability': 'configuration'}


def test_stale_reconcile_lease_cannot_reopen_an_uncertain_payment(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id, state='creating', kind='reconcile', service=1)
    with factory() as db:
        row = db.get(FreightOrder, key); row.payload = {**row.payload, '_provider_tag': f'eleven:{key}'}; db.commit()
    real_locked = sf.locked
    advanced = False
    def locked_after_another_operation(db, requested):
        nonlocal advanced
        if not advanced:
            advanced = True
            # Original cart completed, then a confirmed checkout timed out while
            # the recovery worker was between claiming and executing its lease.
            with factory() as other:
                row = other.get(FreightOrder, key)
                row.provider_id = 'provider-one'; row.price = Decimal('20.00'); row.state = 'uncertain'
                row.recovery_kind = None; row.recovery_check_at = None
                row.error = 'Pagamento sem confirmação.'; other.commit()
        return real_locked(db, requested)
    calls = []
    def provider(method, path, body=None):
        calls.append((method, path))
        if path.startswith('me/orders?'):
            return {'data': [{'id': 'provider-one', 'to': {'name': 'Cliente sintético'}}], 'meta': {'last_page': 1}}
        return {'id': 'provider-one', 'price': '20.00', 'status': 'pending', 'tags': [{'tag': f'eleven:{key}'}]}
    monkeypatch.setattr(sf, 'locked', locked_after_another_operation)
    monkeypatch.setattr(sf, 'call', provider)
    assert recovery.process_recovery()
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.state == 'uncertain', 'A stale cart recovery must never authorize checkout again'
        assert row.recovery_kind is None
        assert db.query(AssistantDelivery).count() == 0
    assert calls == []


def test_known_provider_id_recovery_never_reopens_checkout_after_refresh_failure(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id, state='uncertain', kind='reconcile', service=1,
                provider_id='provider-one', price=Decimal('20.00'), error='Pagamento sem confirmação.')
    with factory() as db:
        row = db.get(FreightOrder, key); row.payload = {**row.payload, '_provider_tag': f'eleven:{key}'}; db.commit()
    calls = []
    def provider(method, path, body=None):
        calls.append((method, path)); assert method == 'GET'
        if path.startswith('me/orders?'):
            return {'data': [{'id': 'provider-one', 'to': {'name': 'Cliente sintético'}}], 'meta': {'last_page': 1}}
        return {'id': 'provider-one', 'price': '20.00', 'status': 'pending', 'tags': [{'tag': f'eleven:{key}'}]}
    monkeypatch.setattr(sf, 'call', provider)
    assert recovery.process_recovery()
    with factory() as db:
        assert db.get(FreightOrder, key).state == 'uncertain'
        with pytest.raises(HTTPException):
            sf.checkout(db, key, Decimal('20.00'))
    assert all(path.startswith('order/info/') for _, path in calls)


@pytest.mark.parametrize('rates', [{'unexpected': 'object'}, [{'id': 1, 'price': 'NaN'}], [{'id': 1, 'price': '-1'}],
    [{'id': 1, 'price': 'Infinity'}], [{'id': 1, 'price': '10.001'}], [{'id': 1, 'price': '10000000000'}]])
def test_malformed_rate_never_becomes_a_payable_quote(queue, monkeypatch, rates):
    factory, user_id = queue
    key = order(factory, user_id)
    monkeypatch.setattr(sf, 'call', lambda *a: rates)
    with factory() as db:
        row = sf.calculate(db, db.get(FreightOrder, key))
        assert row.state == 'rejected' and row.error_category == 'unknown'
        assert row.recovery_kind is None


def test_string_service_id_from_provider_can_be_selected(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id)
    def provider(method, path, body=None):
        if path == 'calculator': return [{'id': '1', 'price': '20.00'}]
        assert path == 'cart' and body['service'] == 1
        return {'id': 'provider-one', 'price': '20.00'}
    monkeypatch.setattr(sf, 'call', provider)
    with factory() as db:
        sf.calculate(db, db.get(FreightOrder, key)); db.commit()
        assert sf.cart(db, key, 1).state == 'pending'


@pytest.mark.parametrize('value', [[], {'id': 'provider-one', 'price': 'NaN'}, {'id': 'provider-one', 'price': '-1'}])
def test_invalid_cart_response_remains_uncertain_and_cannot_repost(queue, monkeypatch, value):
    factory, user_id = queue
    key = order(factory, user_id)
    calls = []
    monkeypatch.setattr(sf, 'call', lambda *a: calls.append(a) or value)
    with factory() as db:
        row = sf.cart(db, key, 1)
        assert row.state == 'uncertain' and row.recovery_kind == 'reconcile' and row.provider_id is None
        with pytest.raises(HTTPException): sf.cart(db, key, 1)
    assert len(calls) == 1


@pytest.mark.parametrize('response', [[], {'success': True, 'purchase': []}, {'success': True, 'purchase': {'orders': 'bad'}}])
def test_malformed_checkout_response_is_uncertain_and_never_retried(queue, monkeypatch, response):
    factory, user_id = queue
    key = order(factory, user_id, state='pending', provider_id='provider-one', price=Decimal('20.00'))
    calls = []
    monkeypatch.setattr(sf, 'call', lambda *a: calls.append(a) or response)
    with factory() as db:
        assert sf.checkout(db, key, Decimal('20.00')).state == 'uncertain'
        with pytest.raises(HTTPException): sf.checkout(db, key, Decimal('20.00'))
    assert len(calls) == 1


@pytest.mark.parametrize('late_failure', [False, True])
def test_late_cart_reply_does_not_replace_confirmed_provider_progress(queue, monkeypatch, late_failure):
    factory, user_id = queue
    key = order(factory, user_id)
    def provider(*args):
        with factory() as other:
            row = other.get(FreightOrder, key)
            row.provider_id = 'provider-one'; row.price = Decimal('20.00'); row.state = 'released'
            row.recovery_kind = None; row.recovery_check_at = None; other.commit()
        if late_failure: raise ProviderError('unavailable', 'Late transport failure')
        return {'id': 'provider-one', 'price': '20.00'}
    monkeypatch.setattr(sf, 'call', provider)
    with factory() as db:
        assert sf.cart(db, key, 1).state == 'released'


def test_late_checkout_timeout_does_not_replace_confirmed_payment(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id, state='pending', provider_id='provider-one', price=Decimal('20.00'))
    def provider(*args):
        with factory() as other:
            row = other.get(FreightOrder, key); row.state = 'released'; other.commit()
        raise ProviderError('unavailable', 'Late timeout')
    monkeypatch.setattr(sf, 'call', provider)
    with factory() as db:
        assert sf.checkout(db, key, Decimal('20.00')).state == 'released'


def test_exact_tag_with_confirmed_payment_never_reverts_to_pending(queue, monkeypatch):
    factory, user_id = queue
    key = order(factory, user_id, state='uncertain', kind='reconcile', service=1)
    with factory() as db:
        row = db.get(FreightOrder, key); row.payload = {**row.payload, '_provider_tag': f'eleven:{key}'}; db.commit()
    calls = []
    def provider(method, path, body=None):
        calls.append((method, path)); assert method == 'GET'
        if path.startswith('me/orders?'):
            return {'data': [{'id': 'provider-one', 'to': {'name': 'Cliente sintético'}}], 'meta': {'last_page': 1}}
        return {'id': 'provider-one', 'status': 'generated', 'price': '20.00', 'tags': [{'tag': f'eleven:{key}'}]}
    monkeypatch.setattr(sf, 'call', provider)
    assert recovery.process_recovery()
    with factory() as db:
        row = db.get(FreightOrder, key)
        assert row.state == 'released' and row.label_status == 'waiting' and row.label_check_at is not None
        assert row.notify_channel == 'telegram' and row.notify_destination == '-100123'
        assert db.query(AssistantDelivery).count() == 0
    assert len(calls) == 2


def test_health_bad_query_is_unknown_not_outage(monkeypatch):
    def provider(*args):
        raise response_error(400, {'errors': {'user_agent': ['invalid']}})
    monkeypatch.setattr(sf, 'call', provider)
    assert recovery.service_status()['availability'] == 'unknown'


def test_frontend_quote_recovery_sends_notice_without_unusable_bot_buttons(queue, monkeypatch):
    factory, user_id = queue
    with factory() as db:
        incoming(db, user_id, 'Consulta anterior', channel='telegram'); db.commit()
    key = order(factory, user_id, state='retry_waiting', kind='quote', bot=False)
    monkeypatch.setattr(sf, 'call', lambda *args: copy.deepcopy(RATES))
    assert recovery.process_recovery()
    with factory() as db:
        delivery = db.query(AssistantDelivery).one()
        assert 'gestor de endereços' in delivery.text
        assert delivery.reply_markup is None and delivery.destination == '-100123'
        assert db.get(FreightOrder, key).state == 'quoted'
