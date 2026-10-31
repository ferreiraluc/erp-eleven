import { randomBytes } from 'node:crypto';
import { ApiError, GROUP_JID, MAX_MEDIA_BYTES, authorized, boundedMedia, incomingEnvelope, mediaSourceAllowed, phoneFromJid, reconnectDelay, validateMime } from './protocol.mjs';

const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const terminalStates = new Set(['accepted', 'uncertain', 'failed']);

export class Agent {
  constructor({ store, api, baileys, logger, report = () => {}, now = Date.now }) {
    Object.assign(this, { store, api, baileys, logger, report, now });
    this.config = null;
    this.configAt = 0;
    this.state = 'starting';
    this.qr = null;
    this.qrAt = 0;
    this.accountPhone = null;
    this.groups = [];
    this.groupCache = new Map();
    this.socket = null;
    this.connected = false;
    this.stopped = false;
    this.reconnectAttempt = 0;
    this.reconnectTimer = null;
    this.nextHeartbeat = 0;
    this.lastCleanup = 0;
    this.lastGroups = 0;
    this.pendingReset = null;
    this.connectionEpoch = 0;
    this.receiveChain = Promise.resolve();
    this.auth = this.createAuth();
  }

  createAuth() {
    return this.store.authState(this.baileys.initAuthCreds, (kind, value) => kind === 'app-state-sync-key' ? this.baileys.proto.Message.AppStateSyncKeyData.create(value) : value);
  }

  activeConfig() { return this.now() - this.configAt <= 45000 ? this.config : null; }

  async heartbeat() {
    const qr = this.qr && this.now() - this.qrAt < 55000 ? this.qr : null;
    const body = { state: this.state, agent_version: '1.0.0', qr, groups: this.groups };
    if (this.accountPhone) body.account_phone = this.accountPhone;
    const response = await this.api.post('/heartbeat', body);
    this.config = response;
    this.configAt = this.now();
    if (Number.isSafeInteger(response.session_generation) && response.session_generation > (this.store.get('session-generation') ?? 0)) this.pendingReset = response.session_generation;
    this.nextHeartbeat = this.now() + 10000;
  }

  async start() {
    await this.heartbeat(); // Validate ERP credentials before accessing WhatsApp.
    if (!this.applySessionReset()) this.connect();
    while (!this.stopped) {
      try {
        if (this.now() - this.lastCleanup > 60000) { this.store.cleanup(this.now()); this.lastCleanup = this.now(); }
        if (this.now() >= this.nextHeartbeat) await this.heartbeat();
        this.applySessionReset();
        if (this.connected && this.now() - this.lastGroups > 300000) await this.refreshGroups();
        await this.flushInbox();
        await this.flushOutbox();
      } catch (error) {
        // Deliberately omit provider errors, bodies, keys, messages and phone numbers.
        this.report(error instanceof ApiError ? `ERP_HTTP_${error.status}` : 'CYCLE_RETRY');
        if (error instanceof ApiError && [401, 403].includes(error.status)) { this.config = null; this.configAt = 0; }
        await sleep(5000);
      }
      await sleep(1000);
    }
  }

  connect() {
    if (this.stopped) return;
    this.state = 'starting';
    const auth = this.auth;
    const epoch = ++this.connectionEpoch;
    const guardedKeys = {
      get: async (...args) => {
        if (this.auth !== auth || this.connectionEpoch !== epoch || this.stopped) throw new Error('SESSION_SUPERSEDED');
        return auth.state.keys.get(...args);
      },
      set: async data => {
        if (this.auth !== auth || this.connectionEpoch !== epoch || this.stopped) throw new Error('SESSION_SUPERSEDED');
        return auth.state.keys.set(data);
      },
    };
    const socket = this.baileys.makeWASocket({
      logger: this.logger,
      auth: { creds: auth.state.creds, keys: this.baileys.makeCacheableSignalKeyStore(guardedKeys, this.logger) },
      browser: this.baileys.Browsers.ubuntu('Eleven Assistant'),
      markOnlineOnConnect: false,
      syncFullHistory: false,
      shouldSyncHistoryMessage: () => false,
      shouldIgnoreJid: jid => !GROUP_JID.test(jid) && !/^(?:[1-9][0-9]{6,14}(?::\d+)?@s\.whatsapp\.net|\d{1,30}(?::\d+)?@lid)$/.test(jid),
      connectTimeoutMs: 20000,
      defaultQueryTimeoutMs: 30000,
      keepAliveIntervalMs: 30000,
      maxMsgRetryCount: 3,
      getMessage: async key => this.store.message(key.remoteJid, key.id, this.now()),
      cachedGroupMetadata: async jid => {
        const entry = this.groupCache.get(jid);
        return entry && entry.expires > this.now() ? entry.value : undefined;
      },
    });
    this.socket = socket;
    socket.ev.on('creds.update', patch => {
      if (socket !== this.socket || this.stopped || this.auth !== auth) return;
      auth.saveCreds(patch).catch(() => { if (socket === this.socket) this.fatalStore(); });
    });
    socket.ev.on('connection.update', update => this.connectionUpdate(socket, update));
    socket.ev.on('messages.upsert', ({ messages, type }) => {
      // Baileys also uses append for live messages delivered after an offline
      // interval. History syncing is disabled; timestamp/auth/dedupe apply to both.
      if (!['notify', 'append'].includes(type) || socket !== this.socket) return;
      // Preserve delivery order across asynchronous LID lookups and batches.
      for (const message of messages) {
        this.receiveChain = this.receiveChain.then(() => this.receive(message, socket)).catch(() => this.report('INCOMING_REJECTED'));
      }
    });
    socket.ev.on('groups.update', updates => { for (const group of updates) this.groupCache.delete(group.id); this.lastGroups = 0; });
    socket.ev.on('group-participants.update', update => { this.groupCache.delete(update.id); this.lastGroups = 0; });
  }

  applySessionReset() {
    if (!this.pendingReset || this.stopped) return false;
    const generation = this.pendingReset;
    clearTimeout(this.reconnectTimer);
    const previous = this.socket;
    this.socket = null;
    this.auth = null; // Old crypto callbacks cannot write into the replacement session.
    this.connected = false;
    try { previous?.end(undefined); } catch { /* already closed */ }
    this.store.resetAuth(generation);
    this.auth = this.createAuth();
    this.pendingReset = null;
    this.qr = null;
    this.accountPhone = null;
    this.groups = [];
    this.groupCache.clear();
    this.reconnectAttempt = 0;
    this.lastGroups = 0;
    this.nextHeartbeat = 0;
    this.connect();
    return true;
  }

  fatalStore() {
    this.report('AUTH_STORAGE_FAILED');
    this.fatalError = true;
    this.stop(); // Never continue sending with unpersisted Signal keys.
  }

  connectionUpdate(socket, update) {
    if (socket !== this.socket || this.stopped) return;
    if (update.qr) { this.qr = update.qr; this.qrAt = this.now(); this.state = 'qr'; this.nextHeartbeat = 0; }
    if (update.connection === 'open') {
      this.connected = true;
      this.qr = null;
      this.state = 'connected';
      this.accountPhone = phoneFromJid(socket.user?.id);
      this.reconnectAttempt = 0;
      this.nextHeartbeat = 0;
      this.lastGroups = 0;
      this.report('CONNECTED');
    }
    if (update.connection === 'close') {
      this.connected = false;
      this.qr = null;
      this.nextHeartbeat = 0;
      const status = update.lastDisconnect?.error?.output?.statusCode;
      const reason = this.baileys.DisconnectReason;
      if ([reason.loggedOut, reason.connectionReplaced, reason.badSession, reason.multideviceMismatch, reason.forbidden].filter(Number.isFinite).includes(status)) {
        this.state = 'logged_out';
        this.report('PAIRING_REQUIRED');
        return;
      }
      this.state = 'reconnecting';
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(), reconnectDelay(this.reconnectAttempt++));
    }
  }

  async refreshGroups() {
    this.lastGroups = this.now();
    const socket = this.socket;
    try {
      const groups = await socket.groupFetchAllParticipating();
      if (socket !== this.socket || this.stopped) return;
      this.groups = Object.values(groups).filter(group => GROUP_JID.test(group.id)).slice(0, 100).map(group => {
        this.groupCache.set(group.id, { value: group, expires: this.now() + 300000 });
        return { id: group.id, name: String(group.subject || 'Grupo WhatsApp').trim().slice(0, 100) || 'Grupo WhatsApp' };
      });
      this.nextHeartbeat = 0;
    } catch { this.report('GROUPS_RETRY'); }
  }

  async receive(message, sourceSocket = this.socket) {
    if (sourceSocket !== this.socket || this.stopped) return;
    // Keep previously authorized events in the durable journal during an ERP
    // outage. Sending to ERP still requires a fresh heartbeat and revalidation.
    const config = this.config;
    if (!config) return;
    const envelope = await incomingEnvelope(message, config, {
      now: this.now(),
      selfJids: [sourceSocket?.user?.id, sourceSocket?.user?.lid].filter(Boolean),
      resolvePhone: jid => sourceSocket?.signalRepository?.lidMapping?.getPNForLID(jid),
      wasSent: (chat, id) => this.store.wasSent(chat, id),
    });
    if (envelope && !this.stopped && sourceSocket === this.socket) this.store.enqueueInbound(envelope.id, envelope, envelope.expires);
  }

  async flushInbox() {
    const config = this.activeConfig();
    if (!config?.enabled) return;
    for (const entry of this.store.pendingInbound(this.now(), true)) {
      const envelope = entry.payload;
      if (!authorized(envelope.payload, config)) { this.store.finishInbound(entry.id, 'rejected'); continue; }
      if (envelope.media && !envelope.payload.attachment) {
        if (!this.connected) return;
        try {
          if (!mediaSourceAllowed(envelope.raw)) throw new Error('MEDIA_INVALID');
          const stream = await this.baileys.downloadMediaMessage(envelope.raw, 'stream', {
            host: 'mmg.whatsapp.net',
            options: { signal: AbortSignal.timeout(30000), redirect: 'error' },
          }, {
            logger: this.logger,
            reuploadRequest: async message => {
              const updated = await this.socket.updateMediaMessage(message);
              if (!mediaSourceAllowed(updated)) throw new Error('MEDIA_INVALID');
              return updated;
            },
          });
          const bytes = await boundedMedia(stream, envelope.media.maximum);
          if (!validateMime(bytes, envelope.media.mime)) throw new Error('MEDIA_INVALID');
          envelope.payload.attachment = { mime_type: envelope.media.mime, data_base64: bytes.toString('base64') };
          envelope.raw = null;
          this.store.updateInbound(entry.id, envelope);
        } catch (error) {
          const status = error.output?.statusCode ?? error.status ?? error.response?.status;
          if (['MEDIA_TOO_LARGE', 'MEDIA_EMPTY', 'MEDIA_INVALID'].includes(error.message) || [404, 410].includes(status) || entry.attempts >= 4) {
            this.store.finishInbound(entry.id, 'rejected');
            continue;
          }
          this.store.retryInbound(entry.id, entry.attempts + 1, this.now() + Math.min(160000, 10000 * (2 ** entry.attempts)));
          this.report('MEDIA_RETRY');
          continue;
        }
      }
      try {
        const result = await this.api.post('/incoming', envelope.payload);
        if (result.status === 'paused') { this.nextHeartbeat = 0; return; }
        if (['queued', 'duplicate', 'ignored', 'rate_limited'].includes(result.status)) this.store.finishInbound(entry.id, result.status);
        else throw new Error('INCOMING_STATUS_UNKNOWN');
      } catch (error) {
        if (error instanceof ApiError && [400, 403, 404, 410, 413, 422].includes(error.status)) this.store.finishInbound(entry.id, 'rejected');
        else throw error;
      }
    }
  }

  async acknowledge(row) {
    const body = { claim_key: row.claim_key, status: row.state };
    if (row.provider_id) body.provider_id = row.provider_id;
    if (row.error_code) body.error_code = row.error_code.toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 80);
    try { await this.api.post(`/deliveries/${row.id}/ack`, body); }
    catch (error) {
      if (!(error instanceof ApiError && error.status === 409)) throw error;
      this.report('CLAIM_REVIEW_REQUIRED');
      // Token rotation may retire an old claim. Never retry the provider send.
    }
    this.store.ackOutbound(row.id);
  }

  async flushOutbox() {
    // Acknowledgements remain possible while paused; no new send is permitted.
    for (const row of this.store.pendingOutbound()) {
      if (terminalStates.has(row.state)) await this.acknowledge(row);
      else if (row.state === 'claimed' && this.connected && this.activeConfig()?.enabled) await this.sendDelivery(row);
    }
    if (!this.connected || !this.activeConfig()?.enabled || this.store.pendingOutbound().length) return;
    const key = this.store.claimKey();
    const response = await this.api.post('/claim', { claim_key: key });
    this.store.completeClaim(response.delivery ?? null, key, this.now());
  }

  async sendDelivery(row) {
    const config = this.activeConfig();
    const payload = row.payload;
    const destination = payload.destination;
    const allowedDestination = GROUP_JID.test(destination)
      ? config.allowed_groups?.includes(destination)
      : config.allow_private !== false && !!phoneFromJid(destination) && config.allowed_senders?.includes(`whatsapp:${phoneFromJid(destination)}`);
    if (!allowedDestination || row.expires <= this.now()) {
      this.store.outboundState(row.id, 'failed', null, row.expires <= this.now() ? 'EXPIRED' : 'DESTINATION_NOT_ALLOWED');
      return;
    }
    let content;
    try {
      if (payload.document_url && !payload.document_pdf_base64) throw new Error('REMOTE_DOCUMENT_REJECTED');
      if (payload.document_pdf_base64) {
        const bytes = Buffer.from(payload.document_pdf_base64, 'base64');
        if (bytes.length > MAX_MEDIA_BYTES || !validateMime(bytes, 'application/pdf')) throw new Error('DOCUMENT_INVALID');
        content = { document: bytes, mimetype: 'application/pdf', fileName: 'Eleven.pdf', caption: String(payload.text || '').slice(0, 1024) };
      } else {
        const text = String(payload.text || '');
        if (!text || text.length > 16000) throw new Error('MESSAGE_INVALID');
        content = { text, linkPreview: null };
      }
    } catch (error) { this.store.outboundState(row.id, 'failed', null, error.message); return; }
    // Commit intent before asking ERP/start: a crash at either boundary is uncertain.
    this.store.outboundState(row.id, 'sending');
    let started;
    try { started = await this.api.post(`/deliveries/${row.id}/start`, { claim_key: row.claim_key }); }
    catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        this.store.outboundState(row.id, 'superseded', null, 'claim_superseded');
        this.store.ackOutbound(row.id);
        return;
      }
      this.store.outboundState(row.id, error instanceof ApiError && error.status < 500 ? 'failed' : 'uncertain', null, 'START_NOT_CONFIRMED');
      return;
    }
    if (started.can_send !== true) {
      if (['claimed', 'pending'].includes(started.status) && started.error_code === 'channel_paused') {
        this.store.outboundState(row.id, 'claimed');
        this.nextHeartbeat = 0;
      } else if (['cancelled', 'expired', 'failed', 'accepted', 'sent'].includes(started.status)) {
        this.store.outboundState(row.id, 'failed', null, 'closed_by_erp');
        this.store.ackOutbound(row.id);
      } else this.store.outboundState(row.id, 'uncertain', null, 'START_ALREADY_USED');
      return;
    }
    if (!this.connected || !this.activeConfig()?.enabled || row.expires <= this.now()) {
      this.store.outboundState(row.id, 'failed', null, 'NOT_SENT_CONNECTION_CHANGED');
      return;
    }
    try {
      this.store.markProviderAttempted(row.id);
      const sent = await this.socket.sendMessage(destination, content, { messageId: randomBytes(16).toString('hex').toUpperCase() });
      if (!sent?.key?.id) throw new Error('PROVIDER_RESULT_UNKNOWN');
      this.store.outboundState(row.id, 'accepted', sent.key.id);
      // Provider acceptance is durable before this optional retry/reply cache.
      // A cache failure must never erase the provider ID or downgrade success.
      try {
        if (sent.message) this.store.saveMessage(destination, sent.key.id, sent.message, this.now());
        this.store.saveMessage(destination, `sent:${sent.key.id}`, {}, this.now());
      } catch { this.report('MESSAGE_CACHE_FAILED'); }
    } catch { this.store.outboundState(row.id, 'uncertain', null, 'PROVIDER_RESULT_UNKNOWN'); }
  }

  stop() {
    this.stopped = true;
    this.connected = false;
    clearTimeout(this.reconnectTimer);
    try { this.socket?.end(undefined); } catch { /* closing */ }
  }
}
