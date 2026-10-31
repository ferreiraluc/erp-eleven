import test from 'node:test';
import assert from 'node:assert/strict';
import { Readable } from 'node:stream';
import { ErpClient, ApiError, MAX_MEDIA_BYTES, boundedMedia, incomingEnvelope, mediaSourceAllowed, phoneFromJid, reconnectDelay, validateMime } from '../src/protocol.mjs';

const now = Date.UTC(2026, 9, 30, 12);
const phone = '5511999999999';
const group = '120363123456789@g.us';
const config = { enabled: true, allowed_senders: [`whatsapp:+${phone}`], allowed_groups: [group], group_mode: 'mention', allow_private: true };
function message(overrides = {}) { return { key: { id: 'incoming-1', remoteJid: `${phone}@s.whatsapp.net`, ...overrides.key }, messageTimestamp: now / 1000, message: { conversation: 'Consulte o estoque' }, ...Object.fromEntries(Object.entries(overrides).filter(([key]) => key !== 'key')) }; }

test('phone identity never comes from opaque LID digits', () => {
  assert.equal(phoneFromJid(`${phone}@lid`), null);
  assert.equal(phoneFromJid(`${phone}:9@s.whatsapp.net`), `+${phone}`);
  assert.equal(phoneFromJid(`123@g.us`), null);
});

test('private messages normalize actual phone and keep stable deduplication key', async () => {
  const first = await incomingEnvelope(message(), config, { now });
  const second = await incomingEnvelope(message(), config, { now });
  assert.equal(first.id, second.id);
  assert.equal(first.payload.sender_id, `whatsapp:+${phone}`);
  assert.equal(first.payload.conversation_id, `${phone}@s.whatsapp.net`);
});

test('unknown senders, old history, fromMe, future and special JIDs are ignored', async () => {
  for (const raw of [
    message({ key: { remoteJid: '5511888888888@s.whatsapp.net' } }),
    message({ key: { fromMe: true } }),
    message({ messageTimestamp: now / 1000 - 86401 }),
    message({ messageTimestamp: now / 1000 + 301 }),
    message({ key: { remoteJid: 'status@broadcast' } }),
    message({ key: { remoteJid: '123456789@newsletter' } }),
  ]) assert.equal(await incomingEnvelope(raw, config, { now }), null);
});

test('LID mapping requires verified alternate or previously learned PN', async () => {
  const raw = message({ key: { remoteJid: '900123456789@lid' } });
  assert.equal(await incomingEnvelope(raw, config, { now }), null);
  assert.equal((await incomingEnvelope(raw, config, { now, resolvePhone: async () => `${phone}@s.whatsapp.net` })).payload.sender_id, `whatsapp:+${phone}`);
  raw.key.remoteJidAlt = `${phone}@s.whatsapp.net`;
  assert.equal((await incomingEnvelope(raw, config, { now })).payload.sender_id, `whatsapp:+${phone}`);
});

test('groups require both allowlist and authorized author; conversation is never identity', async () => {
  const raw = message({ key: { remoteJid: group, participant: `${phone}@s.whatsapp.net` }, message: { conversation: '/eleven consulte o estoque' } });
  assert.equal((await incomingEnvelope(raw, config, { now })).payload.conversation_id, group);
  assert.equal(await incomingEnvelope(raw, { ...config, allowed_groups: [] }, { now }), null);
  raw.key.participant = '5511888888888@s.whatsapp.net';
  assert.equal(await incomingEnvelope(raw, config, { now }), null);
});

test('groups respond only to prefix, own mention, own known reply or explicit all-authorized mode', async () => {
  const raw = message({ key: { remoteJid: group, participant: `${phone}@s.whatsapp.net` } });
  assert.equal(await incomingEnvelope(raw, config, { now }), null);
  assert.ok(await incomingEnvelope(raw, { ...config, group_mode: 'all_authorized' }, { now }));
  raw.message = { extendedTextMessage: { text: 'Consulte', contextInfo: { mentionedJid: ['5599000000000@s.whatsapp.net'] } } };
  assert.ok(await incomingEnvelope(raw, config, { now, selfJids: ['5599000000000:2@s.whatsapp.net'] }));
  raw.message.extendedTextMessage.contextInfo = { stanzaId: 'sent-1' };
  assert.equal(await incomingEnvelope(raw, config, { now, wasSent: () => false }), null);
  assert.ok(await incomingEnvelope(raw, config, { now, wasSent: () => true }));
});

test('media rejects view once, unsupported format and declared oversized content before downloading', async () => {
  for (const body of [
    { viewOnceMessage: { message: { imageMessage: { mimetype: 'image/jpeg' } } } },
    { documentMessage: { mimetype: 'application/zip' } },
    { imageMessage: { mimetype: 'image/jpeg', fileLength: MAX_MEDIA_BYTES + 1 } },
  ]) assert.equal(await incomingEnvelope(message({ message: body }), config, { now }), null);
});

test('stream enforces size even if metadata was missing or false', async () => {
  const stream = Readable.from([Buffer.alloc(4), Buffer.alloc(4)]);
  await assert.rejects(boundedMedia(stream, 5), /MEDIA_TOO_LARGE/);
  assert.equal(stream.destroyed, true);
  assert.equal((await boundedMedia(Readable.from([Buffer.from('%PDF-1.7')]))).length, 8);
  assert.equal(validateMime(Buffer.from('%PDF-1.7'), 'application/pdf'), true);
  assert.equal(validateMime(Buffer.from('not a PDF'), 'application/pdf'), false);
});

test('media cannot request internal, arbitrary or credential-bearing URLs', () => {
  for (const url of ['http://169.254.169.254/metadata', 'https://evil.example/file', 'https://mmg.whatsapp.net.evil.example/file', 'https://user:pass@mmg.whatsapp.net/file', 'https://mmg.whatsapp.net:9443/file']) {
    assert.equal(mediaSourceAllowed({ message: { imageMessage: { url, directPath: '/v/t/file' } } }), false);
  }
  assert.equal(mediaSourceAllowed({ message: { imageMessage: { url: 'https://mmg.whatsapp.net/v/t/file', directPath: '/v/t/file' } } }), true);
});

test('ERP bridge enforces HTTPS, does not follow redirects and redacts response errors', async () => {
  assert.throws(() => new ErpClient('http://localhost', 'a'.repeat(32)), /HTTPS/);
  assert.throws(() => new ErpClient('https://user:pass@erp.example', 'a'.repeat(32)), /HTTPS/);
  let captured;
  const api = new ErpClient('https://erp.example', 'a'.repeat(32), async (url, options) => { captured = { url, options }; return new Response('{"enabled":true}', { status: 200 }); });
  assert.deepEqual(await api.post('/heartbeat', {}), { enabled: true });
  assert.equal(captured.options.redirect, 'error');
  assert.equal(captured.url, 'https://erp.example/api/assistant/whatsapp-bridge/heartbeat');
  const errorApi = new ErpClient('https://erp.example', 'a'.repeat(32), async () => new Response('secret provider text', { status: 403 }));
  await assert.rejects(errorApi.post('/heartbeat', {}), error => error instanceof ApiError && error.message === 'ERP_HTTP_403');
});

test('reconnect grows gradually and remains bounded', () => {
  assert.equal(reconnectDelay(0, () => 0.5), 1000);
  assert.equal(reconnectDelay(5, () => 0.5), 32000);
  assert.equal(reconnectDelay(50, () => 0.5), 60000);
});

test('group action instructions keep the server command after the eleven prefix', async () => {
  const command = '/acao a:12345678-1234-1234-1234-123456789abc';
  const raw = message({ key: { remoteJid: group, participant: `${phone}@s.whatsapp.net` }, message: { conversation: `/eleven ${command}` } });
  const incoming = await incomingEnvelope(raw, config, { now });
  assert.equal(incoming.payload.text, command);
  assert.equal(incoming.payload.should_reply, true);
  assert.equal(incoming.payload.conversation_id, group);
});
