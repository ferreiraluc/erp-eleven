import api from './api'
import { storedToken } from './sessionStorage'

export type NotificationCategory = 'manual' | 'sales' | 'tracking' | 'reminder' | 'greeting'
export type NotificationSeverity = 'info' | 'success' | 'warning' | 'urgent'
export interface NotificationItem {
  id: string
  title: string
  body: string
  category: NotificationCategory
  severity: NotificationSeverity
  action_path: string | null
  requires_ack: boolean
  requires_response: boolean
  created_at: string
  published_at: string | null
  scheduled_at: string | null
  read_at: string | null
  acknowledged_at: string | null
  version: number
  cancelled_at: string | null
  acknowledgement_note?: string | null
  read_version?: number
  acknowledged_version?: number
}
export interface NotificationPreferences {
  push_enabled: boolean
  sound_enabled: boolean
  categories: NotificationCategory[]
}
export interface NotificationReceipt {
  user_id: string
  user_name: string
  read_at: string | null
  acknowledged_at: string | null
  acknowledgement_note?: string | null
  push_status: string
  removed_at?: string | null
  read_version?: number
  acknowledged_version?: number
}
export interface AdminNotification extends NotificationItem {
  user_ids: string[]
  receipts: NotificationReceipt[]
}
export interface NotificationTemplate {
  id: string
  name: string
  title: string
  body: string
  category: NotificationCategory
  severity: NotificationSeverity
  requires_ack: boolean
  requires_response: boolean
  action_path: string | null
  version: number
}
export interface NotificationRule {
  event_key: string
  enabled: boolean
  template_id: string | null
  user_ids: string[]
  local_time: string
  weekdays: number[]
  version: number
}
export interface NotificationContent {
  title: string
  body: string
  category: NotificationCategory
  severity: NotificationSeverity
  requires_ack: boolean
  requires_response: boolean
  action_path: string | null
}
export interface NotificationAdminResult {
  items: AdminNotification[]
  total: number
  users: { id: string; nome: string }[]
  templates: NotificationTemplate[]
  rules: NotificationRule[]
}
export const notificationCategories: NotificationCategory[] = [
  'manual',
  'sales',
  'tracking',
  'reminder',
  'greeting',
]
export const notificationSeverities: NotificationSeverity[] = [
  'info',
  'success',
  'warning',
  'urgent',
]
const root = '/api/notifications'
function headers(token: string | null) {
  return { Authorization: token ? `Bearer ${token}` : null }
}
export function safeNotificationPath(path: string | null | undefined): string | null {
  if (
    !path ||
    !path.startsWith('/') ||
    path.startsWith('//') ||
    /[\\#\s\u0000-\u001f]/.test(path) ||
    path.split('?', 1)[0].includes('%')
  )
    return null
  const route = path.split(/[?#]/, 1)[0]
  const allowed = [
    '/dashboard',
    '/notificacoes',
    '/vendas-pdv',
    '/rastreamento',
    '/inventory',
    '/inventory/labels',
    '/clientes',
    '/pedidos',
    '/pdv',
    '/conta',
    '/auditoria',
    '/fiado',
    '/vendors',
    '/bi-vendas',
    '/vendas',
    '/enderecos',
    '/configuracoes',
    '/assistente',
    '/usuarios',
  ]
  return allowed.includes(route) ? path : null
}
export const notificationsAPI = {
  inbox: (
    params: { offset?: number; limit?: number; unread_only?: boolean } = {},
    token = storedToken(),
  ) =>
    api
      .get<{
        items: NotificationItem[]
        total: number
        unread_count: number
      }>(`${root}/inbox`, { params, headers: headers(token) })
      .then((r) => r.data),
  read: (id: string, token = storedToken()) =>
    api.post(`${root}/${encodeURIComponent(id)}/read`, {}, { headers: headers(token) }),
  acknowledge: (id: string, note?: string, expected_version?: number, token = storedToken()) =>
    api.post(
      `${root}/${encodeURIComponent(id)}/acknowledge`,
      { note, expected_version },
      { headers: headers(token) },
    ),
  readAll: (token = storedToken()) => api.post(`${root}/read-all`, {}, { headers: headers(token) }),
  preferences: (token = storedToken()) =>
    api
      .get<NotificationPreferences>(`${root}/preferences`, { headers: headers(token) })
      .then((r) => r.data),
  savePreferences: (value: NotificationPreferences, token = storedToken()) =>
    api
      .put<NotificationPreferences>(`${root}/preferences`, value, { headers: headers(token) })
      .then((r) => r.data),
  admin: (offset = 0, token = storedToken()) =>
    api
      .get<NotificationAdminResult>(`${root}/admin`, {
        params: { offset, limit: 20 },
        headers: headers(token),
      })
      .then((r) => r.data),
  create: (
    value: NotificationContent & {
      request_id: string
      user_ids: string[]
      scheduled_at: string | null
    },
    token = storedToken(),
  ) =>
    api
      .post<AdminNotification>(`${root}/admin`, value, { headers: headers(token) })
      .then((r) => r.data),
  update: (
    id: string,
    value: NotificationContent & {
      expected_version: number
      user_ids: string[]
      scheduled_at: string | null
    },
    token = storedToken(),
  ) =>
    api
      .patch<AdminNotification>(`${root}/admin/${encodeURIComponent(id)}`, value, {
        headers: headers(token),
      })
      .then((r) => r.data),
  cancel: (id: string, expected_version: number, token = storedToken()) =>
    api.post(
      `${root}/admin/${encodeURIComponent(id)}/cancel`,
      { expected_version },
      { headers: headers(token) },
    ),
  template: (
    value: NotificationContent & { name: string },
    id?: string,
    expected_version?: number,
    token = storedToken(),
  ) =>
    (id
      ? api.patch<NotificationTemplate>(
          `${root}/templates/${encodeURIComponent(id)}`,
          { ...value, expected_version },
          { headers: headers(token) },
        )
      : api.post<NotificationTemplate>(`${root}/templates`, value, { headers: headers(token) })
    ).then((r) => r.data),
  rule: (
    key: string,
    value: Omit<NotificationRule, 'event_key' | 'version'> & { expected_version: number },
    token = storedToken(),
  ) =>
    api
      .put<NotificationRule>(`${root}/rules/${encodeURIComponent(key)}`, value, {
        headers: headers(token),
      })
      .then((r) => r.data),
  pushConfig: (token = storedToken()) =>
    api
      .get<{
        available: boolean
        public_key: string
      }>(`${root}/push/config`, { headers: headers(token) })
      .then((r) => r.data),
  subscribe: (
    value: {
      endpoint: string
      keys: { p256dh: string; auth: string }
      device_token: string
      device_name: string
    },
    token = storedToken(),
  ) =>
    api
      .post<{
        id: string
        device_token: string
        user_id: string
        active: boolean
      }>(`${root}/push/subscribe`, value, { headers: headers(token) })
      .then((r) => r.data),
  unsubscribe: (value: { endpoint?: string; device_token?: string } = {}, token = storedToken()) =>
    api.post(`${root}/push/unsubscribe`, value, { headers: headers(token) }),
}
