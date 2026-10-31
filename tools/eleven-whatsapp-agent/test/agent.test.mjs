import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { Agent } from '../src/agent.mjs';
import { Store } from '../src/store.mjs';
import { ApiError } from '../src/protocol.mjs';
import { EventEmitter } from 'node:events';

const phone = '5511999999999';
function fixture(t, handler = async () => ({})) {
  const directory = mkdtempSync(join(tmpdir(), 'eleven-wa-agent-test-'));
  const store = new Store(directory);
  const calls = [];
  const api = { post: async (path, payload) => { calls.push({ path, payload }); return handler(path, payload); } };
  const agent = new Agent({ store, api, baileys: { initAuthCreds: () => ({}), proto: { Message: { AppStateSyncKeyData: { create: value => value } } } }, logger: {} });
  agent.config = { enabled: true, allowed_senders: [`whatsapp:+${phone}`], allowed_groups: [], allow_private: true };
  agent.configAt = Date.now();
  agent.connected = true;
  let sends = 0;
  agent.socket = { sendMessage: async () => { sends++; return { key: { id: 'wa-sent-1' }, message: { conversation: 'hello' } }; }, end() {} };
  t.after(() => { agent.stop(); store.close(); rmSync(directory, { recursive: true, force: true }); });
  return { store, agent, calls, sends: () => sends };
}
function addDelivery(store, extra = {}) {
  store.completeClaim({ id: 'delivery-1', destination: `${phone}@s.whatsapp.net`, text: 'Resposta do ERP', ...extra }, 'claim-1');
}

function mockSocketFactory(agent) {
  const sockets = [];
  Object.assign(agent.baileys, {
    makeCacheableSignalKeyStore: keys => keys,
    Browsers: { ubuntu: () => ['Ubuntu', 'Eleven', 'test'] },
    DisconnectReason: { loggedOut: 401, connectionReplaced: 440 },
    makeWASocket: options => {
      const socket = { options, ev: new EventEmitter(), end() { this.ended = true; }, user: { id: '5511000000000@s.whatsapp.net' } };
      sockets.push(socket);
      return socket;
    },
  });
  return sockets;
}

test('successful send persists result before ERP ack and does not resend if ack fails', async t => {
  let ackAttempts = 0;
  const f = fixture(t, async path => {
    if (path.endsWith('/start')) return { can_send: true };
    if (path.endsWith('/ack') && ++ackAttempts === 1) throw new Error('network');
    return {};
  });
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 1);
  assert.equal(f.store.pendingOutbound()[0].state, 'accepted');
  await assert.rejects(f.agent.flushOutbox());
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 1);
  assert.equal(f.store.pendingOutbound().length, 0);
});

test('unknown provider result is never automatically retried', async t => {
  const f = fixture(t, async path => path.endsWith('/start') ? { can_send: true } : {});
  let attempts = 0;
  f.agent.socket.sendMessage = async () => { attempts++; throw new Error('timeout after transport write'); };
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.store.pendingOutbound()[0].state, 'uncertain');
  await f.agent.flushOutbox();
  assert.equal(attempts, 1);
  assert.equal(f.calls.find(call => call.path.endsWith('/ack')).payload.status, 'uncertain');
});

test('start response lost or already consumed cannot send', async t => {
  const f = fixture(t, async path => { if (path.endsWith('/start')) throw new Error('timeout'); return {}; });
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 0);
  assert.equal(f.store.pendingOutbound()[0].state, 'uncertain');
});

test('paused or stale configuration and disabled group prevent sends', async t => {
  const f = fixture(t);
  addDelivery(f.store);
  f.agent.configAt = 0;
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 0);
  f.agent.configAt = Date.now();
  f.agent.config.enabled = false;
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 0);
});

test('expired delivery is failed without calling provider/start', async t => {
  const f = fixture(t);
  addDelivery(f.store, { expires_at: new Date(Date.now() - 1000).toISOString() });
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 0);
  assert.equal(f.store.pendingOutbound()[0].state, 'failed');
  assert.equal(f.calls.some(call => call.path.endsWith('/start')), false);
});

test('external document URLs and invalid PDFs cannot reach provider', async t => {
  const f = fixture(t);
  addDelivery(f.store, { document_url: 'http://169.254.169.254/metadata' });
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 0);
  assert.equal(f.store.pendingOutbound()[0].error_code, 'remote_document_rejected');
});

test('incoming rejects revoked sender before downloading queued media', async t => {
  const f = fixture(t);
  f.store.enqueueInbound('in', { payload: { sender_id: 'whatsapp:+5511888888888', conversation_id: `${phone}@s.whatsapp.net` }, media: { mime: 'image/jpeg' }, raw: {} }, Date.now() + 10000);
  await f.agent.flushInbox();
  assert.equal(f.store.pendingInbound().length, 0);
  assert.equal(f.calls.length, 0);
});

test('QR is only sent to authenticated ERP heartbeat and removed when stale', async t => {
  const f = fixture(t, async () => ({ enabled: false }));
  f.agent.qr = 'private pairing secret';
  f.agent.qrAt = Date.now();
  f.agent.state = 'qr';
  await f.agent.heartbeat();
  assert.equal(f.calls[0].payload.qr, 'private pairing secret');
  f.agent.qrAt = Date.now() - 60000;
  await f.agent.heartbeat();
  assert.equal(f.calls[1].payload.qr, null);
});

test('ERP forbidden start is recorded failed, never sent', async t => {
  const f = fixture(t, async path => { if (path.endsWith('/start')) throw new ApiError(403); return {}; });
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 0);
  assert.equal(f.store.pendingOutbound()[0].state, 'failed');
});

test('temporarily paused incoming remains queued locally for retry', async t => {
  const f = fixture(t, async () => ({ status: 'paused' }));
  f.store.enqueueInbound('in', { payload: { sender_id: `whatsapp:+${phone}`, conversation_id: `${phone}@s.whatsapp.net` } }, Date.now() + 10000);
  await f.agent.flushInbox();
  assert.equal(f.store.pendingInbound().length, 1);
  assert.equal(f.agent.nextHeartbeat, 0);
});

test('all outgoing error codes satisfy backend lowercase validation', async t => {
  const f = fixture(t);
  addDelivery(f.store, { expires_at: new Date(Date.now() - 1000).toISOString() });
  await f.agent.flushOutbox();
  await f.agent.flushOutbox();
  const acknowledgement = f.calls.find(call => call.path.endsWith('/ack'));
  assert.match(acknowledgement.payload.error_code, /^[a-z0-9_]{1,80}$/);
});

test('start paused safely keeps claimed while cancelled closes locally', async t => {
  let cancelled = false;
  const f = fixture(t, async path => path.endsWith('/start') ? { can_send: false, status: cancelled ? 'cancelled' : 'claimed', error_code: 'channel_paused' } : {});
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.store.pendingOutbound()[0].state, 'claimed');
  cancelled = true;
  await f.agent.flushOutbox();
  assert.equal(f.store.pendingOutbound().length, 0);
  assert.equal(f.sends(), 0);
  assert.equal(f.calls.some(call => call.path.endsWith('/ack')), false);
});

test('session generation resets auth only; old socket credentials and keys cannot overwrite it', async t => {
  const f = fixture(t, async () => ({ ...f.agent.config, session_generation: 1 }));
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const old = sockets[0];
  old.ev.emit('creds.update', { session: 'old' });
  await old.options.auth.keys.set({ session: { old: 'private' } });
  addDelivery(f.store);
  f.store.enqueueInbound('in', { payload: {} }, Date.now() + 10000);
  await f.agent.heartbeat();
  assert.equal(f.agent.pendingReset, 1);
  assert.equal(f.agent.applySessionReset(), true);
  assert.equal(old.ended, true);
  assert.equal(f.store.get('session-generation'), 1);
  assert.equal(f.store.pendingOutbound().length, 1);
  assert.equal(f.store.pendingInbound().length, 1);
  old.ev.emit('creds.update', { session: 'stale overwrite' });
  await assert.rejects(old.options.auth.keys.set({ session: { bad: 'must not persist' } }), /SUPERSEDED/);
  assert.deepEqual(f.store.get('auth-creds'), {});
  assert.equal(f.store.db.prepare('SELECT COUNT(*) AS n FROM auth_keys').get().n, 0);
  sockets[1].ev.emit('creds.update', { session: 'new' });
  assert.equal(f.store.get('auth-creds').session, 'new');
});

test('asynchronous sender resolution preserves arrival order across inbound batch', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  let resolveFirst;
  socket.signalRepository = { lidMapping: { getPNForLID: () => new Promise(resolve => { resolveFirst = resolve; }) } };
  const first = { key: { id: 'first-preview', remoteJid: '900000000000@lid' }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: 'prepare pedido' } };
  const second = { key: { id: 'second-confirm', remoteJid: `${phone}@s.whatsapp.net` }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: 'confirmo' } };
  socket.ev.emit('messages.upsert', { messages: [first, second], type: 'notify' });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.store.pendingInbound().length, 0);
  resolveFirst(`${phone}@s.whatsapp.net`);
  await f.agent.receiveChain;
  assert.deepEqual(f.store.pendingInbound().map(row => row.payload.payload.message_id), ['first-preview', 'second-confirm']);
  socket.ev.emit('messages.upsert', { messages: [{ ...second, key: { ...second.key, id: 'offline-new' } }, { ...second, key: { ...second.key, id: 'history-old' }, messageTimestamp: Math.floor(Date.now() / 1000) - 90000 }], type: 'append' });
  await f.agent.receiveChain;
  assert.equal(f.store.pendingInbound().length, 3);
  assert.equal(f.store.pendingInbound()[2].payload.payload.message_id, 'offline-new');
  assert.equal(socket.options.shouldSyncHistoryMessage(), false);
});

test('retired start claim closes without invalid ack and allows new never-attempted claim', async t => {
  const f = fixture(t, async path => { if (path.endsWith('/start')) throw new ApiError(409); return {}; });
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.store.pendingOutbound().length, 0);
  assert.equal(f.calls.some(call => call.path.endsWith('/ack')), false);
  f.store.completeClaim({ id: 'delivery-1', destination: `${phone}@s.whatsapp.net`, text: 'same work new claim' }, 'claim-2');
  assert.equal(f.store.pendingOutbound()[0].claim_key, 'claim-2');
  assert.equal(f.sends(), 0);
});

test('provider-attempted uncertain messages cannot be reopened by a new claim', async t => {
  const f = fixture(t);
  addDelivery(f.store);
  f.store.markProviderAttempted('delivery-1');
  f.store.outboundState('delivery-1', 'uncertain', null, 'provider_result_unknown');
  f.store.ackOutbound('delivery-1');
  f.store.completeClaim({ id: 'delivery-1', destination: `${phone}@s.whatsapp.net`, text: 'must not resend' }, 'claim-2');
  assert.equal(f.store.pendingOutbound().length, 0);
  assert.equal(f.store.db.prepare('SELECT claim_key FROM outbox WHERE id=?').get('delivery-1').claim_key, 'claim-1');
});

test('ERP outage journals previously authorized messages without sending until config refresh', async t => {
  const f = fixture(t);
  f.agent.configAt = 0;
  await f.agent.receive({ key: { id: 'outage-message', remoteJid: `${phone}@s.whatsapp.net` }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: 'Consulta' } });
  assert.equal(f.store.pendingInbound().length, 1);
  await f.agent.flushInbox();
  assert.equal(f.calls.length, 0);
  assert.equal(f.store.pendingInbound().length, 1);
});


test('media failures back off one conversation without blocking other senders', async t => {
  const f = fixture(t, async () => ({ status: 'queued' }));
  const other = '5511888888888';
  f.agent.config.allowed_senders.push(`whatsapp:+${other}`);
  let now = Date.now();
  f.agent.now = () => now;
  f.agent.configAt = now;
  let downloads = 0;
  f.agent.baileys.downloadMediaMessage = async () => { downloads++; throw new Error('temporary CDN failure'); };
  const base = { sender_id: `whatsapp:+${phone}`, conversation_id: `${phone}@s.whatsapp.net` };
  f.store.enqueueInbound('media', { payload: base, media: { mime: 'image/jpeg', maximum: 1000 }, raw: { message: { imageMessage: { url: 'https://mmg.whatsapp.net/photo' } } } }, now + 600000);
  f.store.enqueueInbound('confirm', { payload: { ...base, text: 'confirmo' } }, now + 600000);
  f.store.enqueueInbound('other', { payload: { sender_id: `whatsapp:+${other}`, conversation_id: `${other}@s.whatsapp.net` } }, now + 600000);
  await f.agent.flushInbox();
  assert.equal(downloads, 1);
  assert.equal(f.calls.filter(call => call.path === '/incoming').length, 1);
  assert.equal(f.calls[0].payload.sender_id, `whatsapp:+${other}`);
  await f.agent.flushInbox();
  assert.equal(downloads, 1);
  assert.equal(f.store.pendingInbound()[0].attempts, 1);
  now += 10000;
  f.agent.baileys.downloadMediaMessage = async () => { downloads++; const error = new Error('gone'); error.output = { statusCode: 410 }; throw error; };
  await f.agent.flushInbox();
  assert.equal(downloads, 2);
  assert.equal(f.store.pendingInbound().length, 1);
  await f.agent.flushInbox();
  assert.equal(f.calls.at(-1).payload.text, 'confirmo');
  assert.equal(f.store.pendingInbound().length, 0);
});

test('message retry cache failure preserves accepted provider result', async t => {
  const f = fixture(t, async path => path.endsWith('/start') ? { can_send: true } : {});
  f.store.saveMessage = () => { throw new Error('cache unavailable'); };
  addDelivery(f.store);
  await f.agent.flushOutbox();
  assert.equal(f.store.pendingOutbound()[0].state, 'accepted');
  assert.equal(f.store.pendingOutbound()[0].provider_id, 'wa-sent-1');
  await f.agent.flushOutbox();
  assert.equal(f.sends(), 1);
  assert.equal(f.calls.find(call => call.path.endsWith('/ack')).payload.status, 'accepted');
});

test('new group upsert is published immediately without granting ERP access', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  f.agent.nextHeartbeat = Date.now() + 10000;
  sockets[0].ev.emit('groups.upsert', [{ id: '120363123456789@g.us', subject: 'Pedidos e Endereços' }]);
  assert.deepEqual(f.agent.groups, [{ id: '120363123456789@g.us', name: 'Pedidos e Endereços' }]);
  assert.equal(f.agent.nextHeartbeat, 0);
  assert.deepEqual(f.agent.config.allowed_groups, []);
  await f.agent.heartbeat();
  assert.deepEqual(f.calls[0].payload.groups, f.agent.groups);
});

test('provider groups.update inside full discovery does not create a refresh loop', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  let now = Date.now(), queries = 0;
  f.agent.now = () => now;
  const group = { id: '120363123456789@g.us', subject: 'Equipe' };
  socket.groupFetchAllParticipating = async () => {
    queries++;
    socket.ev.emit('groups.update', [group]); // Real Baileys behaviour.
    return { [group.id]: group };
  };
  await f.agent.refreshGroups();
  assert.equal(f.agent.nextGroups, now + 300000);
  await f.agent.refreshGroups();
  assert.equal(queries, 1);
  socket.ev.emit('groups.update', [{ id: group.id, subject: 'Equipe Eleven' }]);
  assert.equal(f.agent.groups[0].name, 'Equipe Eleven');
  now += 300000;
  await f.agent.refreshGroups();
  assert.equal(queries, 2);
});

test('group discovery has one outstanding query and does not block ERP heartbeat or messages', async t => {
  const f = fixture(t, async path => path === '/heartbeat' ? f.agent.config : { status: 'queued' });
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  sockets[0].ev.emit('connection.update', { connection: 'open' });
  let resolveGroups, queries = 0;
  sockets[0].groupFetchAllParticipating = () => { queries++; return new Promise(resolve => { resolveGroups = resolve; }); };
  const discovery = f.agent.refreshGroups();
  await f.agent.refreshGroups();
  await f.agent.heartbeat();
  await f.agent.receive({ key: { id: 'while-discovering', remoteJid: `${phone}@s.whatsapp.net` }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: 'Consulta' } });
  await f.agent.flushInbox();
  assert.equal(queries, 1);
  assert.deepEqual(f.calls.map(call => call.path), ['/heartbeat', '/incoming']);
  resolveGroups({});
  await discovery;
});

test('failed group discovery retains known groups, reports safely and retries after thirty seconds', async t => {
  const f = fixture(t);
  let now = Date.now(), queries = 0;
  f.agent.now = () => now;
  const group = { id: '120363123456789@g.us', name: 'Equipe' };
  f.agent.groups = [group];
  f.agent.socket.groupFetchAllParticipating = async () => { queries++; throw new Error('provider secret and phone must not be reported'); };
  const reports = [];
  f.agent.report = value => reports.push(value);
  await f.agent.refreshGroups();
  assert.deepEqual(f.agent.groups, [group]);
  assert.equal(f.agent.nextGroups, now + 30000);
  assert.deepEqual(reports, ['GROUPS_RETRY']);
  await f.agent.heartbeat();
  assert.equal(f.calls[0].payload.error_code, 'group_sync_retry');
  now += 29999;
  await f.agent.refreshGroups();
  assert.equal(queries, 1);
  now++;
  f.agent.socket.groupFetchAllParticipating = async () => { queries++; return {}; };
  await f.agent.refreshGroups();
  assert.equal(queries, 2);
  assert.equal(f.agent.groupError, null);
  assert.deepEqual(f.agent.groups, []);
});

test('stale group events and delayed queries cannot overwrite a replacement session', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const old = sockets[0];
  old.ev.emit('connection.update', { connection: 'open' });
  let resolveGroups;
  old.groupFetchAllParticipating = () => new Promise(resolve => { resolveGroups = resolve; });
  const discovery = f.agent.refreshGroups();
  f.agent.pendingReset = 1;
  f.agent.applySessionReset();
  f.agent.nextGroups = 123456;
  for (const event of ['groups.upsert', 'groups.update']) old.ev.emit(event, [{ id: '120363123456789@g.us', subject: 'Old session' }]);
  old.ev.emit('group-participants.update', { id: '120363123456789@g.us', participants: [] });
  resolveGroups({ '120363123456789@g.us': { id: '120363123456789@g.us', subject: 'Old session' } });
  await discovery;
  assert.deepEqual(f.agent.groups, []);
  assert.equal(f.agent.nextGroups, 123456);
  assert.equal(f.agent.groupError, null);
  assert.equal(f.agent.groupRefresh, null);
});

test('newly joined and allowed groups remain visible beyond the discovery limit', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  const groups = Array.from({ length: 110 }, (_, index) => ({ id: `${120363123450000 + index}@g.us`, subject: `Group ${index}` }));
  f.agent.config.allowed_groups = [groups[109].id];
  socket.groupFetchAllParticipating = async () => Object.fromEntries(groups.map(group => [group.id, group]));
  await f.agent.refreshGroups();
  assert.equal(f.agent.groups.length, 100);
  assert.ok(f.agent.groups.some(group => group.id === groups[109].id));
  socket.ev.emit('groups.upsert', [{ id: '120363123459999@g.us', subject: 'New group' }]);
  assert.equal(f.agent.groups.length, 100);
  assert.equal(f.agent.groups[0].name, 'New group');
  assert.ok(f.agent.groups.some(group => group.id === groups[109].id));
});

test('group joined during a pending discovery survives its older snapshot', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  let resolveGroups;
  socket.groupFetchAllParticipating = () => new Promise(resolve => { resolveGroups = resolve; });
  const discovery = f.agent.refreshGroups();
  socket.ev.emit('groups.upsert', [{ id: '120363123456789@g.us', subject: 'Just joined' }]);
  resolveGroups({});
  await discovery;
  assert.equal(f.agent.groups[0].name, 'Just joined');
});

test('restart heartbeat preserves ERP group discoveries until a provider snapshot succeeds', async t => {
  const f = fixture(t);
  await f.agent.heartbeat();
  assert.equal('groups' in f.calls[0].payload, false);
  f.agent.socket.groupFetchAllParticipating = async () => { throw new Error('offline'); };
  await f.agent.refreshGroups();
  await f.agent.heartbeat();
  assert.equal('groups' in f.calls[1].payload, false);
  f.agent.nextGroups = 0;
  f.agent.socket.groupFetchAllParticipating = async () => ({});
  await f.agent.refreshGroups();
  await f.agent.heartbeat();
  assert.deepEqual(f.calls[2].payload.groups, []);
});

test('group failure diagnostics contain only a validated HTTP status', async t => {
  const f = fixture(t);
  const reports = [];
  f.agent.report = value => reports.push(value);
  f.agent.socket.groupFetchAllParticipating = async () => {
    const error = new Error('private group name and session payload');
    error.output = { statusCode: 429, payload: { private: true } };
    throw error;
  };
  await f.agent.refreshGroups();
  assert.deepEqual(reports, ['GROUPS_RETRY_429']);
  assert.equal(f.agent.groupError, 'group_sync_retry');
});

test('message metadata recovers an undiscovered group while its command remains unauthorized', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  const id = '120363123456789@g.us';
  let lookups = 0;
  socket.groupMetadata = async target => { lookups++; assert.equal(target, id); return { id, subject: 'Pedidos e Endereços' }; };
  socket.groupFetchAllParticipating = async () => { throw new Error('full discovery unavailable'); };
  await f.agent.refreshGroups();
  socket.ev.emit('messages.upsert', { type: 'notify', messages: [{ key: { id: 'group-query', remoteJid: id, participant: `${phone}@s.whatsapp.net` }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: '/eleven consulte' } }] });
  await new Promise(resolve => setImmediate(resolve));
  await f.agent.receiveChain;
  assert.equal(lookups, 1);
  assert.equal(f.agent.groups[0].name, 'Pedidos e Endereços');
  assert.deepEqual(f.agent.config.allowed_groups, []);
  assert.equal(f.store.pendingInbound().length, 0);
  await f.agent.heartbeat();
  assert.deepEqual(f.calls[0].payload.groups, [{ id, name: 'Pedidos e Endereços' }]);
});

test('metadata discovery rejects stale history and special chats but allows own group observation without commands', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  let lookups = 0;
  socket.groupMetadata = async id => { lookups++; return { id, subject: 'Observed group' }; };
  const raw = { key: { id: 'own-group', fromMe: true, remoteJid: '120363123456789@g.us' }, messageTimestamp: Math.floor(Date.now() / 1000), message: { conversation: '/eleven consulte' } };
  for (const remoteJid of ['status@broadcast', '12@g.us', 'person@newsletter', `${phone}@s.whatsapp.net`]) await f.agent.discoverMessageGroup({ ...raw, key: { ...raw.key, remoteJid } }, socket);
  await f.agent.discoverMessageGroup({ ...raw, messageTimestamp: raw.messageTimestamp - 90000 }, socket);
  await f.agent.discoverMessageGroup({ ...raw, messageTimestamp: raw.messageTimestamp + 1000 }, socket);
  socket.ev.emit('messages.upsert', { type: 'history', messages: [raw] });
  assert.equal(lookups, 0);
  socket.ev.emit('messages.upsert', { type: 'notify', messages: [raw] });
  await new Promise(resolve => setImmediate(resolve));
  await f.agent.receiveChain;
  assert.equal(lookups, 1);
  assert.equal(f.agent.groups[0].name, 'Observed group');
  assert.equal(f.store.pendingInbound().length, 0);
});

test('individual metadata lookups are bounded and retry the same group after thirty seconds', async t => {
  const f = fixture(t);
  let now = Date.now();
  f.agent.now = () => now;
  const pending = [];
  f.agent.socket.groupMetadata = id => new Promise((resolve, reject) => pending.push({ id, resolve, reject }));
  const message = index => ({ key: { remoteJid: `${120363123456700 + index}@g.us` }, messageTimestamp: Math.floor(now / 1000) });
  const first = f.agent.discoverMessageGroup(message(1), f.agent.socket);
  const second = f.agent.discoverMessageGroup(message(2), f.agent.socket);
  await f.agent.discoverMessageGroup(message(1), f.agent.socket);
  await f.agent.discoverMessageGroup(message(3), f.agent.socket);
  assert.equal(pending.length, 2);
  pending[0].reject(new Error('temporary failure'));
  pending[1].resolve({ id: pending[1].id, subject: 'Second group' });
  await Promise.all([first, second]);
  await f.agent.discoverMessageGroup(message(1), f.agent.socket);
  assert.equal(pending.length, 2);
  now += 30000;
  const retry = f.agent.discoverMessageGroup(message(1), f.agent.socket);
  assert.equal(pending.length, 3);
  pending[2].resolve({ id: pending[2].id, subject: 'Recovered group' });
  await retry;
  f.agent.groupLookups = new Map(Array.from({ length: 100 }, (_, index) => [`${120363123450000 + index}@g.us`, { pending: false, nextAt: now + 30000 }]));
  await f.agent.discoverMessageGroup(message(4), f.agent.socket);
  assert.equal(pending.length, 3);
  assert.equal(f.agent.groupLookups.size, 100);
});

test('metadata completion from an old socket cannot publish in the new session', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const old = sockets[0];
  old.ev.emit('connection.update', { connection: 'open' });
  let resolve;
  old.groupMetadata = () => new Promise(done => { resolve = done; });
  const id = '120363123456789@g.us';
  const lookup = f.agent.discoverMessageGroup({ key: { remoteJid: id }, messageTimestamp: Math.floor(Date.now() / 1000) }, old);
  f.agent.pendingReset = 1;
  f.agent.applySessionReset();
  resolve({ id, subject: 'Old account group' });
  await lookup;
  assert.deepEqual(f.agent.groups, []);
  assert.equal(f.agent.groupLookups.size, 0);
});

test('partial unknown group metadata can obtain its name and keeps full metadata cache bounded', async t => {
  const f = fixture(t);
  const sockets = mockSocketFactory(f.agent);
  f.agent.connect();
  const socket = sockets[0];
  socket.ev.emit('connection.update', { connection: 'open' });
  const groups = Array.from({ length: 100 }, (_, index) => ({ id: `${120363123450000 + index}@g.us`, name: `Group ${index}` }));
  f.agent.groups = groups;
  for (const group of groups) f.agent.groupCache.set(group.id, { value: group, expires: Date.now() + 300000 });
  const id = '120363123459999@g.us';
  socket.ev.emit('groups.update', [{ id }]);
  // The bounded display can omit this unknown ID until a current message names it.
  f.agent.groups[99] = { id, name: 'Grupo WhatsApp' };
  socket.groupMetadata = async () => ({ id, subject: 'Pedidos e Endereços' });
  await f.agent.discoverMessageGroup({ key: { remoteJid: id }, messageTimestamp: Math.floor(Date.now() / 1000) }, socket);
  assert.equal(f.agent.groups[0].name, 'Pedidos e Endereços');
  assert.equal(f.agent.groupCache.size, 100);
  assert.ok(f.agent.groupCache.has(id));
  const cached = f.agent.groupCache.get(id);
  cached.expires = Date.now() - 1;
  assert.equal(await socket.options.cachedGroupMetadata(id), undefined);
  assert.equal(f.agent.groupCache.has(id), false);
});
