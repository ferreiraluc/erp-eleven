import pino from 'pino';
import { Agent } from './agent.mjs';
import { ErpClient } from './protocol.mjs';
import { Store, acquireLock } from './store.mjs';
import { loadConfig } from './config.mjs';
import { suppressDependencyConsole } from './privacy.mjs';

process.umask(0o077);
let agent;
let store;
let release;
let stopping = false;
const allowedCodes = new Set(['CONNECTED', 'PAIRING_REQUIRED', 'GROUPS_RETRY', 'GROUP_METADATA_RETRY', 'INCOMING_REJECTED', 'CYCLE_RETRY', 'AUTH_STORAGE_FAILED', 'CLAIM_REVIEW_REQUIRED', 'MESSAGE_CACHE_FAILED', 'MEDIA_RETRY']);
function report(code) {
  if (!allowedCodes.has(code) && !/^ERP_HTTP_\d{3}$/.test(code) && !/^(?:GROUPS|GROUP_METADATA)_RETRY_[45]\d{2}$/.test(code)) code = 'AGENT_ERROR';
  process.stdout.write(`${new Date().toISOString()} ${code}\n`);
}
function stop() {
  if (stopping) return;
  stopping = true;
  agent?.stop();
  // Forced termination leaves sending entries uncertain on the next boot.
  setTimeout(() => process.exit(1), 30000).unref();
}
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
process.on('uncaughtException', () => { report('AGENT_ERROR'); stop(); process.exitCode = 1; });
process.on('unhandledRejection', () => { report('AGENT_ERROR'); stop(); process.exitCode = 1; });

try {
  if (Number(process.versions.node.split('.')[0]) < 24) throw new Error('NODE_24_REQUIRED');
  const config = loadConfig();
  const api = new ErpClient(config.url, config.token);
  release = acquireLock(config.directory);
  suppressDependencyConsole();
  const baileys = await import('@whiskeysockets/baileys');
  store = new Store(config.directory, baileys.BufferJSON);
  agent = new Agent({ store, api, baileys: { ...baileys, makeWASocket: baileys.default }, logger: pino({ level: 'silent' }), report });
  await agent.start();
  if (agent.fatalError) process.exitCode = 1;
} catch (error) {
  const safe = new Set(['NODE_24_REQUIRED', 'CONFIG_PERMISSIONS_REQUIRE_0600', 'CONFIG_TOO_LARGE', 'ERP_HTTPS_REQUIRED', 'ERP_TOKEN_INVALID', 'AGENT_ALREADY_RUNNING', 'LOCK_INVALID', 'LOCK_UNAVAILABLE', 'LOCK_IDENTITY_UNAVAILABLE']);
  process.stderr.write(`Eleven WhatsApp: ${safe.has(error.message) ? error.message : 'START_FAILED_CHECK_CONFIGURATION'}\n`);
  process.exitCode = 1;
} finally {
  agent?.stop();
  store?.close();
  release?.();
}
