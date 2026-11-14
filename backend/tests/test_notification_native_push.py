"""Synthetic devices only. Provider HTTP and OAuth are mocked; no real push."""
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
import pytest

from app.models.access import now
from app.models.notification import Notification, NotificationRecipient
from app.models.notification_push import NotificationPushDelivery, NotificationPushSubscription
from app.services import notification_push as push
from app.services import notification_native_push as native
from test_notification_push import db, user_session
from test_access import setup, login

INSTALL = 'a' * 64
BINDING = 'synthetic_binding_012345678901234567890'
PROVIDER = 'synthetic_provider_token_012345678901234567890'


def private_pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_ENABLED', True)
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON', json.dumps({
        'type': 'service_account', 'project_id': 'eleven-fixture',
        'client_email': 'firebase@eleven-fixture.iam.gserviceaccount.com',
        'private_key': private_pem(rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    }))
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_APNS_KEY_ID', 'TESTKEY123')
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_APNS_TEAM_ID', 'TESTTEAM12')
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_APNS_PRIVATE_KEY', private_pem(ec.generate_private_key(ec.SECP256R1())))
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_APNS_TOPIC', 'com.elevenparispy.erp')
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_APNS_SANDBOX', False)
    monkeypatch.setattr(native, '_oauth_cache', None)
    monkeypatch.setattr(native, '_apns_cache', None)
    yield
    native.close_apns_connection()


def subscribe(db, user, session, **extra):
    values = dict(platform='android', registration_token=PROVIDER, installation_secret=INSTALL,
                  device_token=BINDING, device_name='Eleven android')
    values.update(extra)
    return native.subscribe(db, user, session.id, **values)


def queue(db, sub, user):
    notice = Notification(id=uuid.uuid4(), title='Venda U$ 999 concluída', body='Cliente privado',
                          category='sales', severity='success', published_at=now(), version=1)
    db.add(notice); db.flush()
    recipient = NotificationRecipient(id=uuid.uuid4(), notification_id=notice.id, user_id=user.id)
    db.add(recipient); db.flush()
    delivery = NotificationPushDelivery(notification_id=notice.id, recipient_id=recipient.id, subscription_id=sub.id)
    db.add(delivery); db.commit()
    return delivery


def claim(db, **subscription):
    user, session = user_session(db)
    sub = subscribe(db, user, session, **subscription)
    queue(db, sub, user)
    result = push.claim_delivery(db); db.commit()
    return result


def test_disabled_by_default_and_missing_credentials_do_not_expose_configuration(db, monkeypatch):
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_ENABLED', False)
    assert native.config('android') == {'available': False, 'platform': 'android', 'reason': 'not_configured'}
    user, session = user_session(db)
    with pytest.raises(HTTPException) as failure: subscribe(db, user, session)
    assert failure.value.status_code == 503
    assert db.query(NotificationPushSubscription).count() == 0
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_ENABLED', True)
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON', '{bad')
    assert not native.config('android')['available']


def test_native_token_is_encrypted_and_same_installation_rebinds_without_historical_replay(db, configured):
    first, first_session = user_session(db)
    sub = subscribe(db, first, first_session); db.commit()
    assert sub.transport == 'fcm' and PROVIDER not in sub.endpoint
    assert push._decrypt(sub.endpoint) == PROVIDER
    assert sub.installation_hash != INSTALL and sub.device_token_encrypted != BINDING
    old = queue(db, sub, first)
    second, second_session = user_session(db, 'Outra conta')
    with pytest.raises(HTTPException) as failure:
        subscribe(db, second, second_session, installation_secret='b' * 64)
    assert failure.value.status_code == 409
    changed = subscribe(db, second, second_session, device_token='new_binding_0123456789012345678901234')
    db.commit()
    assert changed.id == sub.id and changed.user_id == second.id
    assert db.query(NotificationPushDelivery).count() == 1
    assert push.claim_delivery(db) is None and old.status == 'dead'


def test_rotation_retires_old_token_and_expired_session_is_rejected(db, configured):
    user, session = user_session(db)
    old = subscribe(db, user, session); db.commit()
    new = subscribe(db, user, session, registration_token=PROVIDER + 'new'); db.commit()
    assert old.id != new.id and not old.active and new.active
    session.daily_expires_at = now() - timedelta(seconds=1); db.commit()
    with pytest.raises(HTTPException) as failure: subscribe(db, user, session)
    assert failure.value.status_code == 401


def test_channel_upgrade_preserves_installation_identity_and_already_claimed_work(db, configured, monkeypatch):
    user, session = user_session(db)
    sub = subscribe(db, user, session); db.commit()
    identity = (sub.id, sub.endpoint_hash, sub.installation_hash, sub.device_token_hash)
    queue(db, sub, user)
    previous = push.claim_delivery(db); db.commit()
    upgraded = subscribe(db, user, session, channel_id='eleven-updates-v2'); db.commit()
    assert (upgraded.id, upgraded.endpoint_hash, upgraded.installation_hash, upgraded.device_token_hash) == identity
    assert db.query(NotificationPushSubscription).count() == 1
    assert native._fcm_endpoint(push._decrypt(upgraded.endpoint)) == (PROVIDER, 'eleven-updates-v2')
    assert PROVIDER not in upgraded.endpoint
    with pytest.raises(HTTPException) as failure:
        subscribe(db, user, session, channel_id='eleven-updates-v2', installation_secret='b' * 64)
    assert failure.value.status_code == 409
    queue(db, upgraded, user)
    current = push.claim_delivery(db); db.commit()
    sends = []
    def send(_claim, _data, _ttl, token, channel):
        sends.append((token, channel))
        return 'delivered', None, None
    monkeypatch.setattr(native, '_send_fcm', send)
    assert push.send_claim(previous) == ('delivered', None, None)
    assert push.send_claim(current) == ('delivered', None, None)
    assert sends == [(PROVIDER, 'eleven-updates'), (PROVIDER, 'eleven-updates-v2')]


@pytest.mark.parametrize('endpoint', [
    'broken', 'null', '[]', json.dumps(PROVIDER),
    json.dumps({'version': True, 'token': PROVIDER, 'channel_id': 'eleven-updates-v2'}),
    json.dumps({'version': 2, 'token': PROVIDER, 'channel_id': 'eleven-updates-v2'}),
    json.dumps({'version': 1, 'token': 'short', 'channel_id': 'eleven-updates-v2'}),
    json.dumps({'version': 1, 'token': PROVIDER, 'channel_id': 'unknown-channel'}),
    json.dumps({'version': 1, 'token': PROVIDER, 'channel_id': []}),
    json.dumps({'version': 1, 'token': PROVIDER, 'channel_id': 'eleven-updates-v2', 'url': 'https://invalid.test'}),
    'a' * 5001,
])
def test_malformed_native_endpoint_never_contacts_provider(db, configured, monkeypatch, endpoint):
    result = replace(claim(db), endpoint=push._encrypt(endpoint))
    monkeypatch.setattr(native.requests, 'Session', lambda: pytest.fail('Malformed endpoint cannot contact OAuth or FCM'))
    assert push.send_claim(result) == ('dead', 'native_push_configuration_error', None)


@pytest.mark.parametrize('change', ['revoked', 'expired', 'inactive', 'version'])
def test_native_queue_reuses_session_checks(db, configured, change):
    user, session = user_session(db)
    sub = subscribe(db, user, session); delivery = queue(db, sub, user)
    if change == 'revoked': session.revoked_at = now()
    if change == 'expired': session.daily_expires_at = now() - timedelta(seconds=1)
    if change == 'inactive': user.ativo = False
    if change == 'version': user.auth_version += 1
    db.commit()
    assert push.claim_delivery(db) is None and delivery.status == 'dead'


def test_native_claim_contains_authorized_text_without_routes_or_vapid_key(db, configured):
    result = claim(db)
    data = json.loads(result.payload)
    assert result.transport == 'fcm' and result.private_key == ''
    assert set(data) == {'notification_id', 'device_token', 'expires_at', 'title', 'body', 'sound'}
    assert data['title'] == 'Venda U$ 999 concluída' and data['body'] == 'Cliente privado'
    assert data['sound'] is True and data['expires_at'] == result.expires_at
    assert INSTALL not in result.payload and PROVIDER not in result.payload


def test_native_claim_uses_resolved_presentation_instead_of_raw_template(db, configured, monkeypatch):
    user, session = user_session(db)
    sub = subscribe(db, user, session)
    delivery = queue(db, sub, user)
    notice = db.get(Notification, delivery.notification_id)
    notice.title, notice.body = 'Venda U$ {sale_total} concluída', 'Vendedor: {user_name}'
    monkeypatch.setattr('app.services.notification_context.presented_fields', lambda db, rows: {
        notice.id: {'title': 'Venda U$ 800 concluída', 'body': 'Vendedor: Sol'}})
    result = push.claim_delivery(db)
    data = json.loads(result.payload)
    assert data['title'] == 'Venda U$ 800 concluída' and data['body'] == 'Vendedor: Sol'
    assert '{sale_total}' not in result.payload and '{user_name}' not in result.payload


@pytest.mark.parametrize('change', ['other_recipient', 'removed_recipient', 'reseller_private_notice'])
def test_private_native_text_cannot_be_claimed_outside_current_recipient_scope(db, configured, change):
    user, session = user_session(db)
    sub = subscribe(db, user, session)
    delivery = queue(db, sub, user)
    recipient = db.get(NotificationRecipient, delivery.recipient_id)
    if change == 'other_recipient':
        other, _ = user_session(db, 'Outra conta')
        recipient.user_id = other.id
    elif change == 'removed_recipient':
        recipient.removed_at = now()
    else:
        user.access_profile = 'reseller'
    db.commit()
    assert push.claim_delivery(db) is None and delivery.status == 'dead'


@pytest.mark.parametrize('session_seconds,expected_ttl', [(3600, '300s'), (20, '20s')])
@pytest.mark.parametrize('channel_id', [None, 'eleven-updates', 'eleven-updates-v2'])
def test_fcm_uses_visible_high_priority_alert_with_bounded_ttl(db, configured, monkeypatch, session_seconds, expected_ttl, channel_id):
    result = claim(db, channel_id=channel_id)
    moment = now()
    monkeypatch.setattr(native, 'now', lambda: moment)
    result = replace(result, expires_at=int(moment.timestamp() * 1000) + session_seconds * 1000)
    calls = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            assert self.trust_env is False
            if url == native.OAUTH_URL:
                return SimpleNamespace(status_code=200, json=lambda: {'access_token': 'fixture-access', 'expires_in': 3600})
            return SimpleNamespace(status_code=200, headers={})
    monkeypatch.setattr(native.requests, 'Session', Client)
    assert push.send_claim(result) == ('delivered', None, None)
    assert calls[0][0] == native.OAUTH_URL
    url, request = calls[1]
    assert url == 'https://fcm.googleapis.com/v1/projects/eleven-fixture/messages:send'
    assert request['allow_redirects'] is False
    message = request['json']['message']
    assert message['token'] == PROVIDER and message['android']['ttl'] == expected_ttl
    assert message['android']['priority'] == 'high'
    assert message['android']['notification'] == {
        'channel_id': channel_id or 'eleven-updates', 'tag': str(result.id), 'sound': 'default'}
    assert message['notification'] == {'title': 'Venda U$ 999 concluída', 'body': 'Cliente privado'}
    assert set(message['data']) == {'notification_id', 'device_token', 'expires_at'}
    assert len(json.dumps(request['json']).encode('utf-8')) <= 4096


def test_apns_requires_http2_and_uses_bounded_expiry_and_real_alert(db, configured, monkeypatch):
    user, session = user_session(db)
    sub = subscribe(db, user, session, platform='ios', registration_token='d' * 64)
    queue(db, sub, user)
    result = push.claim_delivery(db); db.commit()
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['http2'] and kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        def close(self): pass
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(status_code=200, headers={})
    monkeypatch.setattr(native.httpx, 'Client', Client)
    assert push.send_claim(result) == ('delivered', None, None)
    url, request = calls[0]
    assert url == 'https://api.push.apple.com/3/device/' + 'd' * 64
    assert request['headers']['apns-topic'] == 'com.elevenparispy.erp'
    assert int(request['headers']['apns-expiration']) <= int(now().timestamp()) + 300
    assert request['json']['aps']['alert'] == {'title': 'Venda U$ 999 concluída', 'body': 'Cliente privado'}
    assert set(request['json']) == {'aps', 'notification_id', 'device_token', 'expires_at'}
    assert len(json.dumps(request['json']).encode('utf-8')) <= 4096


@pytest.mark.parametrize('transport', ['fcm', 'apns'])
def test_legacy_claim_without_text_keeps_generic_alert(db, configured, monkeypatch, transport):
    result = claim(db)
    source = json.loads(result.payload)
    legacy = {key: source[key] for key in ('notification_id', 'device_token', 'expires_at')}
    # Even unexpected keys in an old snapshot must not become provider metadata.
    legacy.update({'action_path': '/private?token=not-a-login-token', 'user_id': 'other',
                   'installation_secret': INSTALL, 'jwt': 'not-a-login-token'})
    result = replace(result, transport=transport, payload=json.dumps(legacy))
    calls = []
    def send(claim, data, ttl, token, *channel):
        calls.append(data)
        assert native._alert_content(data) == {'title': native.GENERIC_TITLE, 'body': native.GENERIC_BODY}
        return 'delivered', None, None
    monkeypatch.setattr(native, '_send_' + transport, send)
    assert push.send_claim(result) == ('delivered', None, None)
    assert set(calls[0]) == {'notification_id', 'device_token', 'expires_at'}


@pytest.mark.parametrize('transport', ['fcm', 'apns'])
@pytest.mark.parametrize('character', ['😀', '衣', '"', '\\', '\x00'])
def test_final_provider_payload_bounds_escaped_text_and_does_not_duplicate_it(db, configured, monkeypatch, transport, character):
    result = replace(claim(db), transport=transport)
    source = json.loads(result.payload)
    source.update({'title': character * 120, 'body': character * 4000, 'action_path': '/inventory?private=1'})
    result = replace(result, payload=json.dumps(source))
    payloads = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def close(self): pass
        def post(self, url, **kwargs):
            payloads.append(kwargs['json'])
            return SimpleNamespace(status_code=200, headers={})
    monkeypatch.setattr(native, '_oauth_access', lambda _: 'fixture-access')
    monkeypatch.setattr(native.requests, 'Session', Client)
    monkeypatch.setattr(native.httpx, 'Client', Client)
    assert push.send_claim(result) == ('delivered', None, None)
    payload = payloads[0]
    assert len(json.dumps(payload).encode('utf-8')) <= 4096
    alert = payload['message']['notification'] if transport == 'fcm' else payload['aps']['alert']
    custom = payload['message']['data'] if transport == 'fcm' else {key: value for key, value in payload.items() if key != 'aps'}
    assert alert['title'] and alert['body']
    assert set(custom) == {'notification_id', 'device_token', 'expires_at'}
    assert '/inventory' not in json.dumps(payload)


@pytest.mark.parametrize('status,gone,expected', [(200,False,'delivered'),(410,True,'gone'),(429,False,'retry'),(503,False,'retry'),(403,False,'dead')])
def test_provider_outcomes_are_bounded(status, gone, expected):
    result = native._outcome(status, {'Retry-After': '2'}, gone=gone)
    assert result[0] == expected
    assert result[2] == (2 if expected == 'retry' else None)


def test_native_expired_or_disabled_claim_never_contacts_provider(db, configured, monkeypatch):
    result = claim(db)
    monkeypatch.setattr(native, '_send_fcm', lambda *args: pytest.fail('Provider must not be called'))
    assert push.send_claim(replace(result, expires_at=0)) == ('dead', 'session_expired', None)
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_ENABLED', False)
    assert push.send_claim(result) == ('dead', 'native_push_not_configured', None)


def test_registration_validates_native_tokens_and_installation(db, configured):
    user, session = user_session(db)
    for values in ({'registration_token': 'https://attacker.test/token'}, {'installation_secret': 'bad'},
                   {'platform': 'ios', 'registration_token': PROVIDER}, {'device_token': 'bad'},
                   {'channel_id': 'unexpected-channel'}, {'channel_id': {}},
                   {'platform': 'ios', 'registration_token': 'd' * 64, 'channel_id': 'eleven-updates-v2'}):
        with pytest.raises(HTTPException) as failure: subscribe(db, user, session, **values)
        assert failure.value.status_code == 422


def test_native_api_authenticates_reseller_binds_own_session_and_logout_revokes(setup, configured):
    from app.api.endpoints import notification_push as api
    from app.database import Base
    from app.models.usuario import Usuario
    from test_notification_push import TABLE_MODELS
    client, factory, ids = setup
    Base.metadata.create_all(factory.kw['bind'], tables=[model.__table__ for model in TABLE_MODELS])
    client.app.include_router(api.router)
    with factory() as db:
        db.get(Usuario, ids['Junior'][0]).access_profile = 'reseller'
        db.commit()
    route = '/api/notifications/push/native/subscribe'
    body = dict(platform='android', registration_token=PROVIDER, installation_secret=INSTALL, device_token=BINDING)
    assert client.post(route, json=body).status_code == 401
    assert client.get('/api/notifications/push/native/config?platform=android').status_code == 401
    headers = login(client, 'Junior')
    assert client.get('/api/notifications/push/native/config?platform=android', headers=headers).json() == {
        'available': True, 'platform': 'android', 'reason': 'ready'}
    assert client.post(route, headers=headers, json={**body, 'user_id': str(ids['Lucas'][0])}).status_code == 422
    assert client.post(route, headers=headers, json={**body, 'channel_id': 'other-channel'}).status_code == 422
    assert client.post(route, headers=headers, json={**body, 'platform': 'ios', 'registration_token': 'd' * 64,
                                                  'channel_id': 'eleven-updates-v2'}).status_code == 422
    body['channel_id'] = 'eleven-updates-v2'
    response = client.post(route, headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['user_id'] == str(ids['Junior'][0])
    assert PROVIDER not in response.text and INSTALL not in response.text
    with factory() as db:
        subscription = db.query(NotificationPushSubscription).one()
        assert native._fcm_endpoint(push._decrypt(subscription.endpoint)) == (PROVIDER, 'eleven-updates-v2')
    stranger = login(client, 'Sol')
    assert client.post('/api/notifications/push/unsubscribe', headers=stranger, json={'device_token': BINDING}).json() == {'disabled': 0}
    with factory() as db:
        queue(db, db.query(NotificationPushSubscription).one(), db.get(Usuario, ids['Junior'][0]))
    assert client.post('/api/auth/logout', headers=headers).status_code == 200
    with factory() as db:
        # Even if the phone disappears before its unsubscribe request, the
        # revoked server session blocks delivery and retires the device binding.
        assert push.claim_delivery(db) is None
        assert not db.query(NotificationPushSubscription).one().active
    assert client.post(route, headers=headers, json=body).status_code == 401


def test_apns_reuses_connection_and_provider_token_until_refresh_or_config_rotation(db, configured, monkeypatch):
    result = claim(db)
    calls, clients = [], []
    class Client:
        closed = False
        def __init__(self, **kwargs): clients.append(self)
        def close(self): self.closed = True
        def post(self, url, **kwargs):
            calls.append(kwargs['headers']['authorization'])
            return SimpleNamespace(status_code=200, headers={})
    monkeypatch.setattr(native.httpx, 'Client', Client)
    for _ in range(2):
        native._send_apns(result, {}, 100, 'd' * 64)
    assert len(clients) == 1 and calls[0] == calls[1]
    native._apns_cache['created_at'] -= 3001
    native._send_apns(result, {}, 100, 'd' * 64)
    assert len(clients) == 1 and native._apns_cache['created_at'] >= int(native.time.time()) - 1
    monkeypatch.setattr(native.settings, 'NATIVE_PUSH_APNS_TOPIC', 'com.elevenparispy.erp.pilot')
    native._send_apns(result, {}, 100, 'd' * 64)
    assert len(clients) == 2 and clients[0].closed


def test_fcm_does_not_send_if_session_expires_during_oauth(db, configured, monkeypatch):
    result = claim(db)
    def oauth(_):
        from datetime import datetime, timezone
        monkeypatch.setattr(native, 'now', lambda: datetime.fromtimestamp(result.expires_at / 1000, timezone.utc))
        return 'fixture-token'
    monkeypatch.setattr(native, '_oauth_access', oauth)
    monkeypatch.setattr(native.requests, 'Session', lambda: pytest.fail('Do not send after session expiry'))
    assert push.send_claim(result) == ('dead', 'session_expired', None)


def test_native_provider_secrets_are_redacted_in_last_line_logger(configured):
    from app.services.safe_logging import redact
    for value in (native.settings.NATIVE_PUSH_APNS_PRIVATE_KEY, native.settings.NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON):
        assert value not in redact('provider failed ' + value)
