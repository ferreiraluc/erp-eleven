import { createHash } from 'node:crypto';

export const MAX_MEDIA_BYTES = 5 * 1024 * 1024;
export const MAX_MESSAGE_AGE_MS = 24 * 60 * 60 * 1000;
export const GROUP_JID = /^[0-9]{5,20}(?:-[0-9]{1,20})?@g\.us$/;

export function phoneFromJid(jid) {
  const match = typeof jid === 'string' && /^([1-9][0-9]{6,14})(?::[0-9]+)?@s\.whatsapp\.net$/.exec(jid);
  return match ? `+${match[1]}` : null;
}

export function normalizeUserJid(jid) {
  return typeof jid === 'string' ? jid.replace(/:\d+@/, '@') : '';
}

export function contentOf(message) {
  if (!message || typeof message !== 'object') return undefined;
  // Do not retain view-once media in the ERP journal.
  if (message.viewOnceMessage || message.viewOnceMessageV2 || message.viewOnceMessageV2Extension) return undefined;
  if (message.ephemeralMessage) return contentOf(message.ephemeralMessage.message);
  if (message.documentWithCaptionMessage) return contentOf(message.documentWithCaptionMessage.message);
  return message;
}

export function mediaSourceAllowed(message) {
  const content = contentOf(message?.message);
  const media = content?.imageMessage ?? content?.documentMessage;
  if (!media) return false;
  if (media.directPath != null && (typeof media.directPath !== 'string' || !media.directPath.startsWith('/') || /[\\\s]/.test(media.directPath))) return false;
  if (media.url != null) {
    try {
      const url = new URL(media.url);
      if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443')) return false;
      if (url.hostname !== 'mmg.whatsapp.net' && !url.hostname.endsWith('.whatsapp.net') && !url.hostname.endsWith('.whatsapp.com')) return false;
    } catch { return false; }
  }
  return !!media.url;
}

export function authorized(payload, config) {
  if (!config?.enabled || !config.allowed_senders?.includes(payload.sender_id)) return false;
  if (GROUP_JID.test(payload.conversation_id)) return config.allowed_groups?.includes(payload.conversation_id) && (config.group_mode === 'all_authorized' || payload.should_reply === true);
  return config.allow_private !== false && /^[1-9][0-9]{6,14}@s\.whatsapp\.net$/.test(payload.conversation_id);
}

export async function incomingEnvelope(message, config, options = {}) {
  const now = options.now ?? Date.now();
  const key = message?.key;
  if (!key?.id || !/^[a-zA-Z0-9_.:-]{1,120}$/.test(key.id) || key.fromMe || !key.remoteJid || !message.message) return null;
  const remoteJid = normalizeUserJid(key.remoteJid);
  const isGroup = GROUP_JID.test(remoteJid);
  if (!isGroup && !/^(?:[1-9][0-9]{6,14}@s\.whatsapp\.net|\d{1,30}@lid)$/.test(remoteJid)) return null;
  if (isGroup && !config.allowed_groups?.includes(remoteJid)) return null;
  if (!isGroup && config.allow_private === false) return null;
  const senderJid = normalizeUserJid(isGroup ? key.participant : key.remoteJid);
  const alternate = isGroup ? key.participantAlt : key.remoteJidAlt;
  let phone = phoneFromJid(senderJid) ?? phoneFromJid(alternate);
  if (!phone && senderJid.endsWith('@lid') && options.resolvePhone) phone = phoneFromJid(await options.resolvePhone(senderJid));
  if (!phone) return null; // Opaque LIDs are never interpreted as telephone numbers.
  const senderId = `whatsapp:${phone}`;
  if (!config.enabled || !config.allowed_senders?.includes(senderId)) return null;
  const seconds = Number(message.messageTimestamp);
  if (!Number.isFinite(seconds)) return null;
  const timestamp = seconds * 1000;
  const maxAge = Math.min(MAX_MESSAGE_AGE_MS, Number(config.limits?.max_message_age_seconds || 86400) * 1000);
  if (timestamp < now - maxAge || timestamp > now + 5 * 60 * 1000) return null;
  const content = contentOf(message.message);
  if (!content) return null;
  const part = content.extendedTextMessage ?? content.imageMessage ?? content.documentMessage;
  const context = part?.contextInfo;
  const text = String(content.conversation ?? part?.text ?? part?.caption ?? '').trim();
  const selfJids = (options.selfJids ?? []).map(normalizeUserJid);
  const mention = context?.mentionedJid?.some(jid => selfJids.includes(normalizeUserJid(jid))) === true;
  const reply = !!context?.stanzaId && options.wasSent?.(remoteJid, context.stanzaId) === true;
  const addressed = !isGroup || mention || reply || /^\/eleven(?:\s|$)/i.test(text) || config.group_mode === 'all_authorized';
  if (!addressed) return null;
  const media = content.imageMessage ?? content.documentMessage;
  const mime = media?.mimetype?.split(';')[0]?.toLowerCase();
  if (media && !['image/jpeg', 'image/png', 'application/pdf'].includes(mime)) return null;
  if (media && !mediaSourceAllowed(message)) return null;
  if (!text && !media) return null;
  const maximum = Math.min(MAX_MEDIA_BYTES, Number(config.limits?.media_bytes || MAX_MEDIA_BYTES));
  if (media?.fileLength && Number(media.fileLength) > maximum) return null;
  const textLimit = Math.min(6000, Number(config.limits?.text_chars || 6000));
  if (text.length > textLimit) return null;
  const conversationId = isGroup ? remoteJid : `${phone.slice(1)}@s.whatsapp.net`;
  const id = createHash('sha256').update(`${conversationId}\0${senderId}\0${key.id}`).digest('hex');
  return {
    id,
    payload: {
      message_id: key.id,
      conversation_id: conversationId,
      sender_id: senderId,
      text: text.replace(/^\/eleven(?:\s+|$)/i, '').trim(),
      should_reply: true,
      timestamp: new Date(timestamp).toISOString(),
    },
    media: media ? { mime, maximum } : null,
    raw: media ? message : null,
    expires: timestamp + maxAge,
  };
}

export async function boundedMedia(stream, maximum = MAX_MEDIA_BYTES) {
  const chunks = [];
  let bytes = 0;
  try {
    for await (const chunk of stream) {
      const buffer = Buffer.from(chunk);
      bytes += buffer.length;
      if (bytes > maximum) throw new Error('MEDIA_TOO_LARGE');
      chunks.push(buffer);
    }
  } finally { stream.destroy?.(); }
  const buffer = Buffer.concat(chunks);
  if (!buffer.length) throw new Error('MEDIA_EMPTY');
  return buffer;
}

export function validateMime(buffer, mime) {
  if (mime === 'application/pdf') return buffer.subarray(0, 5).toString('ascii') === '%PDF-';
  if (mime === 'image/png') return buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  if (mime === 'image/jpeg') return buffer.length > 3 && buffer[0] === 255 && buffer[1] === 216 && buffer[2] === 255;
  return false;
}

export function reconnectDelay(attempt, random = Math.random) {
  return Math.min(60000, 1000 * 2 ** Math.min(attempt, 6)) * (0.8 + random() * 0.4);
}

export class ApiError extends Error {
  constructor(status) { super(`ERP_HTTP_${status}`); this.status = status; }
}

export class ErpClient {
  constructor(baseUrl, token, fetchImpl = fetch) {
    const url = new URL(baseUrl);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw new Error('ERP_HTTPS_REQUIRED');
    if (typeof token !== 'string' || token.length < 32 || /\s/.test(token)) throw new Error('ERP_TOKEN_INVALID');
    this.base = `${url.origin}${url.pathname.replace(/\/$/, '')}/api/assistant/whatsapp-bridge`;
    this.token = token;
    this.fetch = fetchImpl;
  }
  async post(path, body) {
    if (!/^\/[a-z0-9/_-]+$/i.test(path)) throw new Error('API_PATH_INVALID');
    const response = await this.fetch(`${this.base}${path}`, {
      method: 'POST', redirect: 'error', signal: AbortSignal.timeout(25000),
      headers: { 'Authorization': `Bearer ${this.token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new ApiError(response.status);
    const length = Number(response.headers?.get?.('content-length'));
    if (length > 8 * 1024 * 1024) throw new Error('ERP_RESPONSE_TOO_LARGE');
    const bytes = await boundedMedia(response.body, 8 * 1024 * 1024);
    return JSON.parse(bytes.toString('utf8'));
  }
}
