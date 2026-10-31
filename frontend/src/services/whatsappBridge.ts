import api from '@/services/api'

export interface WhatsAppGroup { id: string; name: string }
export interface WhatsAppBridgeConfig {
  name: string
  enabled: boolean
  allow_private: boolean
  notify_tracking: boolean
  group_mode: 'mention' | 'all_authorized'
  allowed_groups: string[]
  discovered_groups: WhatsAppGroup[]
  state: string
  error_code?: string | null
  account_phone: string | null
  last_seen_at: string | null
  credential_configured: boolean
}
export interface WhatsAppBridgePairing { qr_image: string | null; expires_at: string | null }
const base = '/api/assistant/whatsapp-bridge'
export const getWhatsAppBridge = async () => (await api.get<WhatsAppBridgeConfig>(`${base}/config`)).data
export const saveWhatsAppBridge = async (config: Pick<WhatsAppBridgeConfig, 'name' | 'enabled' | 'allow_private' | 'notify_tracking' | 'group_mode' | 'allowed_groups'>) =>
  (await api.put<WhatsAppBridgeConfig>(`${base}/config`, config)).data
export const createWhatsAppBridgeCredential = async () => (await api.post<{ token: string }>(`${base}/credential`)).data
export const getWhatsAppBridgePairing = async () => (await api.get<WhatsAppBridgePairing>(`${base}/pairing`)).data
export const resetWhatsAppBridgeSession = async () => (await api.post(`${base}/session/reset`)).data
