"""Opt-in FCM/APNs transport for the existing private notification queue.

Provider tokens and installation secrets are never logged or returned by read
APIs. Native alerts display the authorized inbox title/body; an OS may still
display an already accepted alert after logout. Opening the app rechecks the
current session and loads its inbox through the normal authorization layer.
"""
import atexit
import hashlib
import json
import re
import secrets
import time
from threading import Lock

from fastapi import HTTPException
import httpx
import jwt
import requests
from sqlalchemy import text

from ..config import settings
from ..models.access import AuthSession, now
from ..models.notification_push import NotificationPushSubscription
from ..models.usuario import Usuario
from .user_sessions import effective_session_expiry

FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
OAUTH_URL = 'https://oauth2.googleapis.com/token'
GENERIC_TITLE = 'ELEVEN'
GENERIC_BODY = 'Há uma atualização na sua caixa de notificações.'
FCM_LEGACY_CHANNEL = 'eleven-updates'
FCM_CHANNELS = frozenset((FCM_LEGACY_CHANNEL, 'eleven-updates-v2'))
MAX_PROVIDER_PAYLOAD_BYTES = 4096
_oauth_lock = Lock()
_oauth_cache = None
_apns_lock = Lock()
_apns_cache = None


def close_apns_connection():
    global _apns_cache
    with _apns_lock:
        if _apns_cache:
            _apns_cache['client'].close()
            _apns_cache = None


atexit.register(close_apns_connection)


def _fcm_credentials():
    try:
        value = json.loads(settings.NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON)
        if (value.get('type') != 'service_account'
                or not re.fullmatch(r'[a-z][a-z0-9-]{4,62}', value.get('project_id', ''))
                or not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.gserviceaccount\.com', value.get('client_email', ''))
                or not isinstance(value.get('private_key'), str)
                or not value['private_key'].startswith('-----BEGIN PRIVATE KEY-----')):
            return None
        return value
    except (ValueError, TypeError, AttributeError):
        return None


def transport_available(transport):
    if not settings.NATIVE_PUSH_ENABLED:
        return False
    if transport == 'fcm':
        return _fcm_credentials() is not None
    if transport == 'apns':
        return bool(re.fullmatch(r'[A-Z0-9]{10}', settings.NATIVE_PUSH_APNS_KEY_ID)
                    and re.fullmatch(r'[A-Z0-9]{10}', settings.NATIVE_PUSH_APNS_TEAM_ID)
                    and re.fullmatch(r'[A-Za-z0-9.-]{3,200}', settings.NATIVE_PUSH_APNS_TOPIC)
                    and settings.NATIVE_PUSH_APNS_PRIVATE_KEY.startswith('-----BEGIN PRIVATE KEY-----'))
    return False


def config(platform):
    available = transport_available({'android': 'fcm', 'ios': 'apns'}.get(platform))
    return {'available': available, 'platform': platform, 'reason': 'ready' if available else 'not_configured'}


def subscribe(db, user, session_id, *, platform, registration_token, installation_secret, device_token,
              device_name='Eleven App', channel_id=None):
    from .notification_push import MAX_DEVICE_SUBSCRIPTIONS, _encrypt, endpoint_hash
    transport = {'android': 'fcm', 'ios': 'apns'}.get(platform)
    if not transport_available(transport):
        raise HTTPException(503, 'As notificações deste aplicativo ainda estão em configuração.')
    valid_token = (re.fullmatch(r'(?:[a-fA-F0-9]{2}){16,256}', registration_token) if transport == 'apns'
                   else re.fullmatch(r'[A-Za-z0-9:_-]{32,4096}', registration_token))
    if (not valid_token or not re.fullmatch(r'[a-f0-9]{64}', installation_secret)
            or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', device_token)
            or channel_id is not None and (transport != 'fcm' or not isinstance(channel_id, str) or channel_id not in FCM_CHANNELS)):
        raise HTTPException(422, 'Inscrição do aplicativo inválida. Ative novamente neste aparelho.')
    if transport == 'apns':
        registration_token = registration_token.lower()
    identity = endpoint_hash(f'native:{transport}:{registration_token}')
    installation = endpoint_hash('native-installation:' + installation_secret)
    if db.get_bind().dialect.name == 'postgresql':
        # Stable order serializes token rotation and account switching on a single
        # installation without creating lock-order inversions across two devices.
        for key in sorted({int(identity[:15], 16), int(installation[:15], 16)}):
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': key})
    db.query(Usuario).filter_by(id=user.id).with_for_update().one()
    session = db.get(AuthSession, session_id)
    if not session or session.user_id != user.id or session.revoked_at or effective_session_expiry(session) <= now():
        raise HTTPException(401, 'Sessão expirada. Entre novamente.')
    row = db.query(NotificationPushSubscription).filter_by(endpoint_hash=identity).with_for_update().one_or_none()
    if row and (row.transport != transport or not secrets.compare_digest(row.installation_hash or '', installation)):
        # Knowing a provider token alone never transfers an endpoint to another
        # user. Reinstall/Keychain reset requires explicit operator reconciliation.
        raise HTTPException(409, 'Este aparelho possui outro vínculo de instalação. Contate o administrador.')
    db.query(NotificationPushSubscription).filter(
        NotificationPushSubscription.installation_hash == installation,
        NotificationPushSubscription.transport == transport,
        NotificationPushSubscription.endpoint_hash != identity,
        NotificationPushSubscription.active.is_(True),
    ).update({'active': False, 'updated_at': now()}, synchronize_session='fetch')
    if row is None or not row.active or row.user_id != user.id:
        count = db.query(NotificationPushSubscription).filter_by(user_id=user.id, active=True).count()
        if count >= MAX_DEVICE_SUBSCRIPTIONS:
            raise HTTPException(409, 'Limite de aparelhos atingido. Desative um aparelho antigo.')
    if row is None:
        row = NotificationPushSubscription(endpoint_hash=identity, transport=transport, installation_hash=installation)
        db.add(row)
    row.user_id, row.auth_session_id, row.auth_version = user.id, session_id, user.auth_version
    # Keep endpoint identity/ownership based on the provider token, not the
    # channel. Older clients and already-claimed work retain their legacy token
    # representation; only a client that created v2 opts its own binding into it.
    endpoint = (json.dumps({'version': 1, 'token': registration_token, 'channel_id': channel_id}, separators=(',', ':'))
                if transport == 'fcm' and channel_id is not None else registration_token)
    row.endpoint = _encrypt(endpoint)
    row.p256dh, row.auth = '', ''
    row.device_token_hash, row.device_token_encrypted = endpoint_hash(device_token), _encrypt(device_token)
    row.device_name = re.sub(r'[\x00-\x1f\x7f]', ' ', device_name or 'Eleven App').strip()[:100]
    row.active, row.updated_at = True, now()
    db.flush()
    return row


class ConfigurationError(Exception):
    pass


def _fcm_endpoint(value):
    if not isinstance(value, str) or len(value) > 5000:
        raise ConfigurationError()
    if re.fullmatch(r'[A-Za-z0-9:_-]{32,4096}', value):
        return value, FCM_LEGACY_CHANNEL
    try:
        endpoint = json.loads(value)
    except (ValueError, TypeError):
        raise ConfigurationError() from None
    if (not isinstance(endpoint, dict) or set(endpoint) != {'version', 'token', 'channel_id'}
            or type(endpoint['version']) is not int or endpoint['version'] != 1
            or not isinstance(endpoint['token'], str)
            or not re.fullmatch(r'[A-Za-z0-9:_-]{32,4096}', endpoint['token'])
            or not isinstance(endpoint['channel_id'], str) or endpoint['channel_id'] not in FCM_CHANNELS):
        raise ConfigurationError()
    return endpoint['token'], endpoint['channel_id']


def _oauth_access(credentials):
    global _oauth_cache
    fingerprint = hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).hexdigest()
    with _oauth_lock:
        moment = int(time.time())
        if _oauth_cache and _oauth_cache[0] == fingerprint and _oauth_cache[2] > moment + 60:
            return _oauth_cache[1]
        assertion = jwt.encode({'iss': credentials['client_email'], 'scope': FCM_SCOPE, 'aud': OAUTH_URL,
                                'iat': moment, 'exp': moment + 3600}, credentials['private_key'], algorithm='RS256')
        with requests.Session() as client:
            client.trust_env = False
            response = client.post(OAUTH_URL, data={'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                                   'assertion': assertion}, timeout=(2, 3), allow_redirects=False)
        if response.status_code >= 500 or response.status_code == 429:
            raise requests.RequestException('oauth_unavailable')
        if response.status_code != 200:
            raise ConfigurationError()
        data = response.json()
        access = data.get('access_token')
        if not isinstance(access, str) or not access or len(access) > 10000:
            raise ConfigurationError()
        expires = min(3600, max(60, int(data.get('expires_in', 3600))))
        _oauth_cache = (fingerprint, access, moment + expires)
        return access


def _outcome(status, headers, *, gone=False):
    from .notification_push import _retry_seconds
    if 200 <= status < 300:
        return 'delivered', None, None
    if gone:
        return 'gone', 'subscription_expired', None
    if status == 429 or status >= 500:
        return 'retry', 'provider_rate_limited' if status == 429 else 'provider_unavailable', _retry_seconds(headers.get('Retry-After'), now())
    return 'dead', 'provider_rejected', None


def _alert_content(data):
    def text(key, fallback, characters, byte_limit):
        value = data.get(key)
        if value is None:
            return fallback
        if not isinstance(value, str):
            raise ConfigurationError()
        value = re.sub(r'[\x00-\x1f\x7f]', ' ', value).strip()[:characters]
        return value.encode('utf-8')[:byte_limit].decode('utf-8', errors='ignore') or fallback
    # Older workers/claims did not carry text. Do not fabricate business data.
    return {'title': text('title', GENERIC_TITLE, 120, 300),
            'body': text('body', GENERIC_BODY, 1000, 1600)}


def _provider_data(data):
    # Never duplicate title/body in custom data, or forward arbitrary metadata,
    # routes, JWTs or installation secrets. The random binding is not a login token.
    return {key: data[key] for key in ('notification_id', 'device_token', 'expires_at') if key in data}


def _fit_provider_payload(payload, alert):
    # requests/httpx may escape non-ASCII JSON differently. Counting the larger
    # ASCII-escaped representation bounds both, including wrapping/FCM routing.
    def size():
        return len(json.dumps(payload).encode('utf-8'))
    for field, step in (('body', 128), ('title', 32)):
        while size() > MAX_PROVIDER_PAYLOAD_BYTES and alert[field]:
            alert[field] = alert[field][:-step]
    if size() > MAX_PROVIDER_PAYLOAD_BYTES:
        raise ConfigurationError()
    return payload


def _send_fcm(claim, data, ttl, provider_token, channel_id=FCM_LEGACY_CHANNEL):
    if channel_id not in FCM_CHANNELS:
        raise ConfigurationError()
    credentials = _fcm_credentials()
    if not credentials:
        raise ConfigurationError()
    access = _oauth_access(credentials)
    ttl = min(ttl, (claim.expires_at - int(now().timestamp() * 1000)) // 1000)
    if ttl <= 0:
        return 'dead', 'session_expired', None
    # This transport always emits a visible alert. High priority allows FCM to
    # attempt delivery during Doze; never reuse it for silent background sync.
    alert = _alert_content(data)
    payload = {'message': {'token': provider_token,
        'notification': alert,
        'data': {key: str(value) for key, value in _provider_data(data).items()},
        'android': {'priority': 'high', 'ttl': f'{ttl}s', 'collapse_key': str(claim.id),
                    'notification': {'channel_id': channel_id, 'tag': str(claim.id), 'sound': 'default'}}}}
    _fit_provider_payload(payload, alert)
    with requests.Session() as client:
        client.trust_env = False
        response = client.post(f'https://fcm.googleapis.com/v1/projects/{credentials["project_id"]}/messages:send',
                               json=payload, headers={'Authorization': f'Bearer {access}'}, timeout=(2, 3), allow_redirects=False)
    gone = False
    if response.status_code == 404:
        try:
            details = response.json().get('error', {}).get('details', [])
            gone = any(value.get('errorCode') == 'UNREGISTERED' for value in details if isinstance(value, dict))
        except (ValueError, TypeError, AttributeError):
            pass
    return _outcome(response.status_code, response.headers, gone=gone)


def _send_apns(claim, data, ttl, provider_token):
    global _apns_cache
    host = 'api.sandbox.push.apple.com' if settings.NATIVE_PUSH_APNS_SANDBOX else 'api.push.apple.com'
    alert = _alert_content(data)
    payload = _fit_provider_payload({'aps': {'alert': alert, 'sound': 'default'}, **_provider_data(data)}, alert)
    # APNs requires HTTP/2. Default certificate verification remains enabled and
    # proxies/redirects cannot redirect this credential-bearing request. Reuse
    # both connection and token as required by Apple's provider guidance.
    fingerprint = hashlib.sha256('\n'.join((host, settings.NATIVE_PUSH_APNS_KEY_ID,
        settings.NATIVE_PUSH_APNS_TEAM_ID, settings.NATIVE_PUSH_APNS_TOPIC,
        settings.NATIVE_PUSH_APNS_PRIVATE_KEY)).encode()).hexdigest()
    with _apns_lock:
        moment = int(time.time())
        ttl = min(ttl, (claim.expires_at - int(now().timestamp() * 1000)) // 1000)
        if ttl <= 0:
            return 'dead', 'session_expired', None
        if not _apns_cache or _apns_cache['fingerprint'] != fingerprint:
            if _apns_cache:
                _apns_cache['client'].close()
            _apns_cache = {'fingerprint': fingerprint, 'created_at': 0, 'authorization': '',
                'client': httpx.Client(http2=True, trust_env=False, follow_redirects=False,
                    timeout=httpx.Timeout(5, connect=2), limits=httpx.Limits(max_connections=1, keepalive_expiry=300))}
        if _apns_cache['created_at'] <= moment - 3000:
            _apns_cache['authorization'] = jwt.encode({'iss': settings.NATIVE_PUSH_APNS_TEAM_ID, 'iat': moment},
                settings.NATIVE_PUSH_APNS_PRIVATE_KEY, algorithm='ES256', headers={'kid': settings.NATIVE_PUSH_APNS_KEY_ID})
            _apns_cache['created_at'] = moment
        try:
            response = _apns_cache['client'].post(f'https://{host}/3/device/{provider_token}', json=payload,
                               headers={'authorization': f'bearer {_apns_cache["authorization"]}',
                                        'apns-topic': settings.NATIVE_PUSH_APNS_TOPIC,
                                        'apns-push-type': 'alert', 'apns-priority': '10',
                                        'apns-expiration': str(moment + ttl),
                                        'apns-collapse-id': str(claim.id), 'apns-id': str(claim.id)})
        except httpx.HTTPError:
            _apns_cache['client'].close()
            _apns_cache = None
            raise
    gone = response.status_code == 410
    if response.status_code == 400:
        try:
            gone = response.json().get('reason') in ('BadDeviceToken', 'DeviceTokenNotForTopic')
        except (ValueError, TypeError, AttributeError):
            pass
    return _outcome(response.status_code, response.headers, gone=gone)


def send_claim(claim):
    from .notification_push import _decrypt
    remaining = (claim.expires_at - int(now().timestamp() * 1000)) // 1000
    if remaining <= 0:
        return 'dead', 'session_expired', None
    if not transport_available(claim.transport):
        return 'dead', 'native_push_not_configured', None
    try:
        # Reconstruct an allowlisted payload. Text is the authorized presentation
        # snapshot; click destinations and credentials never reach the provider.
        source = json.loads(claim.payload)
        data = {'notification_id': str(source['notification_id']),
                'device_token': str(source['device_token']), 'expires_at': int(source['expires_at'])}
        data.update({key: source[key] for key in ('title', 'body') if key in source})
        provider_token = _decrypt(claim.endpoint)
        ttl = min(300, remaining)
        if claim.transport == 'fcm':
            provider_token, channel_id = _fcm_endpoint(provider_token)
            return _send_fcm(claim, data, ttl, provider_token, channel_id)
        if claim.transport == 'apns':
            return _send_apns(claim, data, ttl, provider_token)
        return 'dead', 'native_push_not_configured', None
    except (requests.RequestException, httpx.HTTPError):
        return 'retry', 'provider_network_error', None
    except (ConfigurationError, ValueError, TypeError, KeyError, jwt.PyJWTError):
        return 'dead', 'native_push_configuration_error', None
