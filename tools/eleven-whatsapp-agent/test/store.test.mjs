import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Store, acquireLock } from '../src/store.mjs';
import { spawn } from 'node:child_process';
import { once } from 'node:events';

function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), 'eleven-wa-store-test-'));
  const store = new Store(directory);
  t.after(() => { try { store.close(); } catch {} rmSync(directory, { recursive: true, force: true }); });
  return { directory, store };
}

test('state and credentials are durable and private; keys support deletion', async t => {
  const { store, directory } = fixture(t);
  const auth = store.authState(() => ({ registered: false }));
  await auth.saveCreds({ registered: true });
  await auth.state.keys.set({ 'lid-mapping': { user: '5511999999999@s.whatsapp.net' } });
  assert.equal(store.authState(() => {}).state.creds.registered, true);
  assert.deepEqual(await auth.state.keys.get('lid-mapping', ['user']), { user: '5511999999999@s.whatsapp.net' });
  await auth.state.keys.set({ 'lid-mapping': { user: null } });
  assert.equal((await auth.state.keys.get('lid-mapping', ['user'])).user, undefined);
  assert.equal(statSync(directory).mode & 0o777, 0o700);
  assert.equal(statSync(store.path).mode & 0o777, 0o600);
});

test('concurrent process lock refuses second holder without deleting state', t => {
  const { directory } = fixture(t);
  const release = acquireLock(directory);
  assert.throws(() => acquireLock(directory), /ALREADY_RUNNING/);
  release();
  acquireLock(directory)();
});

test('a stale PID file does not block replacement containers using the SQLite OS lock', t => {
  const { directory } = fixture(t);
  writeFileSync(join(directory, 'agent.lock'), JSON.stringify({ pid: process.pid, started: 'previous-container-start', token: 'old' }));
  const release = acquireLock(directory);
  assert.throws(() => acquireLock(directory), /ALREADY_RUNNING/);
  release();
});

test('OS ownership lock is released when its process is killed', async t => {
  const { directory } = fixture(t);
  const moduleUrl = new URL('../src/store.mjs', import.meta.url).href;
  const script = `import { acquireLock } from ${JSON.stringify(moduleUrl)}; acquireLock(process.argv[1]); process.stdout.write('ready'); setInterval(() => {}, 1000);`;
  const child = spawn(process.execPath, ['--input-type=module', '-e', script, directory], { stdio: ['ignore', 'pipe', 'pipe'] });
  t.after(() => child.kill('SIGKILL'));
  await once(child.stdout, 'data');
  assert.throws(() => acquireLock(directory), /ALREADY_RUNNING/);
  const exited = once(child, 'exit');
  child.kill('SIGKILL');
  await exited;
  acquireLock(directory)();
});

test('incoming repeated delivery is deduplicated and accepted bytes erased', t => {
  const { store } = fixture(t);
  assert.equal(store.enqueueInbound('id', { secret: 'media' }, Date.now() + 10000), true);
  assert.equal(store.enqueueInbound('id', { secret: 'media' }, Date.now() + 10000), false);
  assert.equal(store.pendingInbound().length, 1);
  store.finishInbound('id');
  assert.equal(store.pendingInbound().length, 0);
  assert.equal(store.db.prepare('SELECT payload FROM inbox WHERE id=?').get('id').payload, '{}');
});

test('restart after send intent makes message uncertain, accepted remains accepted', t => {
  const { store, directory } = fixture(t);
  store.completeClaim({ id: 'one', text: '1' }, 'claim-1');
  store.completeClaim({ id: 'two', text: '2' }, 'claim-2');
  store.outboundState('one', 'sending');
  store.outboundState('two', 'accepted', 'provider-2');
  store.close();
  const reopened = new Store(directory);
  assert.deepEqual(reopened.pendingOutbound().map(row => row.state), ['uncertain', 'accepted']);
  reopened.close();
});

test('claim id is persisted across retries and cleared atomically with claimed response', t => {
  const { store } = fixture(t);
  const key = store.claimKey();
  assert.equal(store.claimKey(), key);
  store.completeClaim({ id: 'outbound-1', destination: 'abc', text: 'hello' }, key);
  assert.equal(store.pendingOutbound()[0].claim_key, key);
  assert.notEqual(store.claimKey(), key);
});

test('expiry removes media content and retains delivery identity until dedupe retention ends', t => {
  const { store } = fixture(t);
  store.enqueueInbound('incoming', { media: 'private bytes' }, 5000);
  assert.deepEqual(store.pendingInbound(6000), []);
  assert.equal(store.db.prepare('SELECT payload FROM inbox').get().payload, '{}');
  store.saveMessage('chat', 'm', { private: true }, 0);
  store.cleanup(86400001);
  assert.equal(store.message('chat', 'm'), undefined);
});

test('cleanup erases expired media even when paused and pendingInbound is never called', t => {
  const { store } = fixture(t);
  store.enqueueInbound('incoming', { media: 'private bytes' }, 5000);
  store.completeClaim({ id: 'outgoing', document_pdf_base64: 'private PDF', expires_at: new Date(5000).toISOString() }, 'claim');
  store.cleanup(6000);
  assert.equal(store.db.prepare('SELECT payload FROM inbox').get().payload, '{}');
  const row = store.db.prepare('SELECT state,payload,error_code FROM outbox').get();
  assert.deepEqual({ ...row }, { state: 'failed', payload: '{}', error_code: 'expired' });
});
