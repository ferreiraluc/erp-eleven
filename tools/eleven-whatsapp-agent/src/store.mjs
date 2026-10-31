import { DatabaseSync } from 'node:sqlite';
import { chmodSync, existsSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';

export function acquireLock(directory) {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  chmodSync(directory, 0o700);
  const path = join(directory, 'owner.sqlite');
  let owner;
  try {
    owner = new DatabaseSync(path);
    chmodSync(path, 0o600);
    owner.exec('PRAGMA busy_timeout=0; PRAGMA journal_mode=DELETE; BEGIN EXCLUSIVE; CREATE TABLE IF NOT EXISTS owner_lock (id INTEGER);');
  } catch (error) {
    try { owner?.close(); } catch { /* partial initialization */ }
    if (/locked|busy/i.test(error.message)) throw new Error('AGENT_ALREADY_RUNNING');
    throw error;
  }
  // SQLite holds an OS lock for this connection. A process crash releases it;
  // there is no PID file to go stale or misidentify a replacement container.
  return () => {
    try { owner.exec('ROLLBACK'); } finally { owner.close(); }
  };
}

export class Store {
  constructor(directory, codec = {}) {
    this.directory = resolve(directory);
    mkdirSync(this.directory, { recursive: true, mode: 0o700 });
    chmodSync(this.directory, 0o700);
    this.path = join(this.directory, 'agent.sqlite');
    this.stringify = value => JSON.stringify(value, codec.replacer);
    this.parse = value => JSON.parse(value, codec.reviver);
    this.db = new DatabaseSync(this.path);
    chmodSync(this.path, 0o600);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA synchronous=FULL;
      PRAGMA secure_delete=ON;
      PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS auth_keys (kind TEXT NOT NULL, id TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(kind,id));
      CREATE TABLE IF NOT EXISTS inbox (id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', expires INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, available_at INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, claim_key TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, provider_id TEXT, error_code TEXT, provider_attempted INTEGER NOT NULL DEFAULT 0, acked INTEGER NOT NULL DEFAULT 0, expires INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS messages (chat TEXT NOT NULL, id TEXT NOT NULL, value TEXT NOT NULL, expires INTEGER NOT NULL, PRIMARY KEY(chat,id));
    `);
    const inboxColumns = this.db.prepare('PRAGMA table_info(inbox)').all();
    for (const column of ['attempts', 'available_at']) {
      if (!inboxColumns.some(item => item.name === column)) this.db.exec(`ALTER TABLE inbox ADD COLUMN ${column} INTEGER NOT NULL DEFAULT 0`);
    }
    if (!this.db.prepare('PRAGMA table_info(outbox)').all().some(column => column.name === 'provider_attempted')) {
      this.db.exec("ALTER TABLE outbox ADD COLUMN provider_attempted INTEGER NOT NULL DEFAULT 0; UPDATE outbox SET provider_attempted=1 WHERE state IN ('sending','accepted','uncertain');");
    }
    for (const suffix of ['-wal', '-shm']) {
      if (existsSync(`${this.path}${suffix}`)) chmodSync(`${this.path}${suffix}`, 0o600);
    }
    // A previous process may have reached WhatsApp before it could record success.
    this.db.prepare("UPDATE outbox SET state='uncertain',error_code='restart_during_send' WHERE state='sending'").run();
  }

  transaction(fn) {
    this.db.exec('BEGIN IMMEDIATE');
    try { const result = fn(); this.db.exec('COMMIT'); return result; }
    catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }

  get(key) { const row = this.db.prepare('SELECT value FROM kv WHERE key=?').get(key); return row ? this.parse(row.value) : undefined; }
  set(key, value) {
    this.db.prepare('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(key, this.stringify(value));
  }
  delete(key) { this.db.prepare('DELETE FROM kv WHERE key=?').run(key); }

  resetAuth(generation) {
    if (!Number.isSafeInteger(generation) || generation < 1) throw new Error('SESSION_GENERATION_INVALID');
    this.transaction(() => {
      this.delete('auth-creds');
      this.db.exec('DELETE FROM auth_keys');
      this.set('session-generation', generation);
    });
  }

  authState(initAuthCreds, hydrate = (_kind, value) => value) {
    const creds = this.get('auth-creds') ?? initAuthCreds();
    this.set('auth-creds', creds);
    return {
      state: {
        creds,
        keys: {
          get: async (kind, ids) => Object.fromEntries(ids.map(id => {
            const row = this.db.prepare('SELECT value FROM auth_keys WHERE kind=? AND id=?').get(kind, id);
            return [id, row ? hydrate(kind, this.parse(row.value)) : undefined];
          })),
          set: async data => this.transaction(() => {
            for (const [kind, values] of Object.entries(data)) {
              for (const [id, value] of Object.entries(values)) {
                if (value == null) this.db.prepare('DELETE FROM auth_keys WHERE kind=? AND id=?').run(kind, id);
                else this.db.prepare('INSERT INTO auth_keys(kind,id,value) VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET value=excluded.value').run(kind, id, this.stringify(value));
              }
            }
          }),
        },
      },
      saveCreds: async patch => { Object.assign(creds, patch); this.set('auth-creds', creds); },
    };
  }

  enqueueInbound(id, payload, expires) {
    return this.db.prepare('INSERT OR IGNORE INTO inbox(id,payload,expires) VALUES(?,?,?)').run(id, this.stringify(payload), expires).changes > 0;
  }
  pendingInbound(now = Date.now(), readyOnly = false) {
    this.db.prepare("UPDATE inbox SET state='expired',payload='{}' WHERE expires<=? AND state='pending'").run(now);
    const ready = readyOnly ? ` AND available_at<=? AND NOT EXISTS (SELECT 1 FROM inbox earlier WHERE earlier.state='pending' AND earlier.expires>? AND earlier.rowid<inbox.rowid AND json_extract(earlier.payload,'$.payload.conversation_id')=json_extract(inbox.payload,'$.payload.conversation_id'))` : '';
    return this.db.prepare(`SELECT id,payload,attempts FROM inbox WHERE state='pending' AND expires>?${ready} ORDER BY rowid LIMIT 10`).all(...(readyOnly ? [now, now, now] : [now])).map(row => ({ id: row.id, payload: this.parse(row.payload), attempts: row.attempts }));
  }
  retryInbound(id, attempts, availableAt) { this.db.prepare('UPDATE inbox SET attempts=?,available_at=? WHERE id=?').run(attempts, availableAt, id); }
  updateInbound(id, payload) { this.db.prepare('UPDATE inbox SET payload=? WHERE id=?').run(this.stringify(payload), id); }
  finishInbound(id, state = 'accepted') { this.db.prepare('UPDATE inbox SET state=?,payload=? WHERE id=?').run(state, '{}', id); }

  claimKey() { const existing = this.get('pending-claim'); if (existing) return existing; const key = randomUUID(); this.set('pending-claim', key); return key; }
  completeClaim(delivery, key, now = Date.now()) {
    this.transaction(() => {
      if (delivery) {
        const expires = delivery.expires_at ? Date.parse(delivery.expires_at) : now + 86400000;
        if (!Number.isFinite(expires)) throw new Error('INVALID_EXPIRY');
        this.db.prepare(`INSERT INTO outbox(id,claim_key,payload,state,expires) VALUES(?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET claim_key=excluded.claim_key,payload=excluded.payload,state='claimed',expires=excluded.expires,error_code=NULL,provider_id=NULL,acked=0
          WHERE outbox.claim_key<>excluded.claim_key AND outbox.provider_attempted=0 AND outbox.state IN ('superseded','claimed','failed','uncertain')`).run(String(delivery.id), key, this.stringify(delivery), 'claimed', expires);
      }
      this.delete('pending-claim');
    });
  }
  pendingOutbound() {
    return this.db.prepare('SELECT * FROM outbox WHERE acked=0 ORDER BY rowid LIMIT 10').all().map(row => ({ ...row, payload: this.parse(row.payload) }));
  }
  outboundState(id, state, providerId = null, errorCode = null) {
    const safeCode = errorCode ? String(errorCode).toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 80) : null;
    this.db.prepare('UPDATE outbox SET state=?,provider_id=?,error_code=? WHERE id=?').run(state, providerId, safeCode, id);
  }
  markProviderAttempted(id) { this.db.prepare('UPDATE outbox SET provider_attempted=1 WHERE id=?').run(id); }
  ackOutbound(id) { this.db.prepare("UPDATE outbox SET acked=1,payload='{}' WHERE id=?").run(id); }
  saveMessage(chat, id, message, now = Date.now()) {
    this.db.prepare('INSERT INTO messages(chat,id,value,expires) VALUES(?,?,?,?) ON CONFLICT(chat,id) DO UPDATE SET value=excluded.value,expires=excluded.expires').run(chat, id, this.stringify(message), now + 86400000);
  }
  message(chat, id, now = Date.now()) {
    const row = this.db.prepare('SELECT value FROM messages WHERE chat=? AND id=? AND expires>?').get(chat, id, now);
    return row ? this.parse(row.value) : undefined;
  }
  wasSent(chat, id) {
    return !!this.db.prepare("SELECT 1 FROM outbox WHERE provider_id=? AND state='accepted' AND json_extract(payload,'$.destination')=?").get(id, chat)
      || !!this.db.prepare('SELECT 1 FROM messages WHERE chat=? AND id=?').get(chat, `sent:${id}`);
  }
  cleanup(now = Date.now()) {
    this.transaction(() => {
      this.db.prepare('DELETE FROM messages WHERE expires<=?').run(now);
      this.db.prepare("UPDATE inbox SET state='expired',payload='{}' WHERE expires<=? AND payload<>'{}'").run(now);
      this.db.prepare('DELETE FROM inbox WHERE expires<?').run(now - 86400000);
      this.db.prepare("UPDATE outbox SET state='failed',error_code='expired',payload='{}' WHERE expires<=? AND state='claimed'").run(now);
      this.db.prepare("UPDATE outbox SET payload='{}' WHERE expires<=? AND state!='claimed'").run(now);
      this.db.prepare('DELETE FROM outbox WHERE expires<? AND acked=1').run(now - 86400000 * 7);
    });
    this.db.exec('PRAGMA wal_checkpoint(TRUNCATE)');
  }
  close() { this.db.close(); }
}
