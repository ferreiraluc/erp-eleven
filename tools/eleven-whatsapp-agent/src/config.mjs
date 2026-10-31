import { readFileSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { resolve } from 'node:path';

export function loadConfig(env = process.env) {
  let file = {};
  if (env.ELEVEN_WHATSAPP_CONFIG) {
    const path = resolve(env.ELEVEN_WHATSAPP_CONFIG);
    const stat = statSync(path);
    if (!stat.isFile() || (stat.mode & 0o077)) throw new Error('CONFIG_PERMISSIONS_REQUIRE_0600');
    if (stat.size > 16384) throw new Error('CONFIG_TOO_LARGE');
    file = JSON.parse(readFileSync(path, 'utf8'));
  }
  return {
    url: env.ELEVEN_ERP_URL ?? file.erp_url,
    token: env.ELEVEN_WHATSAPP_TOKEN ?? file.token,
    directory: resolve(env.ELEVEN_WHATSAPP_STATE_DIR ?? file.state_dir ?? `${homedir()}/.eleven-whatsapp`),
  };
}
