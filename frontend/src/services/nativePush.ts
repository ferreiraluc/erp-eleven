import { Capacitor, registerPlugin, type PluginListenerHandle } from '@capacitor/core'
import { PushNotifications } from '@capacitor/push-notifications'
import { notificationsAPI } from './notifications'
import { sessionExpiry, storedToken, tokenIsCurrent } from './sessionStorage'

type NativePlatform = 'android' | 'ios'
type NativeSupport = 'ready' | 'denied' | 'native_pending'
interface Binding { user_id: string; session_key: string; device_token: string; expires_at: number }
interface Installation { secret: string; binding?: Binding }
interface SecureStorage {
  get(options: { key: 'notification-installation' }): Promise<{ value: string | null }>
  set(options: { key: 'notification-installation'; value: string }): Promise<void>
}
const vault = registerPlugin<SecureStorage>('ElevenSecureStorage')
let status: NativeSupport = 'native_pending'
let epoch = 0
let work: Promise<unknown> = Promise.resolve()
let listeners: Promise<void> | undefined
let binding: Binding | null = null
let ownerToken: string | null = null
let ownerUser: string | null = null
let installation: Installation | null = null

export function isNativePushPlatform() {
  return Capacitor.isNativePlatform() && ['ios', 'android'].includes(Capacitor.getPlatform())
}
export function nativePushSupport(): NativeSupport { return status }
function platform(): NativePlatform { return Capacitor.getPlatform() as NativePlatform }
function serial<T>(action: () => Promise<T>): Promise<T> {
  const next = work.catch(() => undefined).then(action)
  work = next.catch(() => undefined)
  return next
}
function assertCurrent(current: number, token: string) {
  if (current !== epoch || ownerToken !== token || storedToken() !== token || !tokenIsCurrent(token))
    throw new Error('notification-session-changed')
}
function randomSecret() {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), value => value.toString(16).padStart(2, '0')).join('')
}
async function fingerprint(token: string) {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token))
  return Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('')
}
async function readInstallation(): Promise<Installation> {
  if (installation) return installation
  const { value } = await vault.get({ key: 'notification-installation' })
  let parsed: Installation | null = null
  try { parsed = value ? JSON.parse(value) : null } catch { /* fail closed below */ }
  if (value && (!parsed || !/^[a-f0-9]{64}$/.test(parsed.secret))) throw new Error('native-push-storage')
  if (parsed) { installation = parsed; return parsed }
  const created = { secret: randomSecret() }
  // Never publish an installation identity that exists only in JS memory: a
  // failed Keychain/Keystore write must not orphan a provider token on the server.
  await writeInstallation(created)
  return created
}
async function writeInstallation(value: Installation) {
  await vault.set({ key: 'notification-installation', value: JSON.stringify(value) })
  installation = value
}
async function configured(token: string, current: number) {
  if (import.meta.env.VITE_NATIVE_PUSH_ENABLED !== 'true') { status = 'native_pending'; return false }
  const result = await notificationsAPI.nativePushConfig(platform(), token)
  assertCurrent(current, token)
  if (!result.available || result.platform !== platform()) { status = 'native_pending'; return false }
  status = 'ready'
  return true
}
function validTap(data: Record<string, unknown> | undefined) {
  if (!data || !binding || !ownerToken || storedToken() !== ownerToken || !tokenIsCurrent(ownerToken)) return false
  const expiry = Number(data.expires_at)
  return typeof data.notification_id === 'string' && /^[a-f0-9-]{36}$/i.test(data.notification_id)
    && data.device_token === binding.device_token && Number.isFinite(expiry)
    && expiry <= binding.expires_at && expiry > Date.now() && binding.expires_at > Date.now()
}
async function ensureListeners() {
  if (!listeners) listeners = (async () => {
    const handles: PluginListenerHandle[] = []
    try {
      handles.push(await PushNotifications.addListener('pushNotificationActionPerformed', action => {
        if (!validTap(action.notification.data)) return
        // The provider never chooses a URL. The normal router and backend protect
        // this inbox; opening a system alert does not mark it read automatically.
        window.dispatchEvent(new CustomEvent('erp:native-notification-open', { detail: { path: '/notificacoes' } }))
      }))
      handles.push(await PushNotifications.addListener('pushNotificationReceived', notice => {
        if (validTap(notice.data)) window.dispatchEvent(new Event('erp:native-notification-received'))
      }))
    } catch (error) {
      await Promise.all(handles.map(handle => handle.remove().catch(() => undefined)))
      throw error
    }
  })().catch(error => { listeners = undefined; throw error })
  await listeners
}
async function registrationToken(): Promise<string> {
  const handles: PluginListenerHandle[] = []
  let timer: ReturnType<typeof setTimeout> | undefined
  let finished = false
  async function track(handle: PluginListenerHandle) {
    if (finished) await handle.remove().catch(() => undefined)
    else handles.push(handle)
  }
  try {
    return await new Promise<string>((resolve, reject) => {
      timer = setTimeout(() => reject(new Error('native-push-timeout')), 15000)
      void (async () => {
        await track(await PushNotifications.addListener('registration', result => resolve(result.value)))
        if (finished) return
        await track(await PushNotifications.addListener('registrationError', () => reject(new Error('native-push-registration'))))
        if (finished) return
        await PushNotifications.register()
      })().catch(() => reject(new Error('native-push-registration')))
    })
  } finally {
    finished = true
    if (timer) clearTimeout(timer)
    await Promise.all(handles.map(handle => handle.remove().catch(() => undefined)))
  }
}
async function activate(userId: string, token: string, current: number, askPermission: boolean) {
  assertCurrent(current, token)
  if (!await configured(token, current)) return false
  let permission = await PushNotifications.checkPermissions()
  assertCurrent(current, token)
  if (permission.receive === 'denied') { status = 'denied'; return false }
  if (permission.receive !== 'granted') {
    if (!askPermission) return false
    permission = await PushNotifications.requestPermissions()
    assertCurrent(current, token)
    if (permission.receive !== 'granted') { status = 'denied'; return false }
  }
  status = 'ready'
  const record = await readInstallation()
  const sessionKey = await fingerprint(token)
  assertCurrent(current, token)
  const expiry = sessionExpiry(token)
  if (!expiry || expiry <= Date.now()) throw new Error('notification-session-changed')
  // Restore only this session's local nonce before listening for pending tap
  // events. A payload from an old login or account cannot open another inbox.
  binding = record.binding?.user_id === userId && record.binding.session_key === sessionKey
    && record.binding.expires_at > Date.now() ? { ...record.binding, expires_at: expiry } : null
  await ensureListeners()
  if (platform() === 'android') await PushNotifications.createChannel({
    id: 'eleven-updates', name: 'Avisos da Eleven', description: 'Vendas, rastreios e recados da equipe',
    importance: 3, visibility: 0, sound: 'default',
  })
  const registration = await registrationToken()
  assertCurrent(current, token)
  const candidate: Binding = binding || { user_id: userId, session_key: sessionKey, device_token: randomSecret(), expires_at: expiry }
  // Capture the candidate before the network call so logout can unregister a
  // just-created binding even when the request resolves after logout.
  binding = candidate
  const response = await notificationsAPI.subscribeNative({ platform: platform(), registration_token: registration,
    installation_secret: record.secret, device_token: candidate.device_token, device_name: `Eleven ${platform()}` }, token)
  assertCurrent(current, token)
  if (response.user_id !== userId || response.device_token !== candidate.device_token || !response.active)
    throw new Error('invalid-subscription-owner')
  await writeInstallation({ secret: record.secret, binding: candidate })
  assertCurrent(current, token)
  return true
}
export function restoreNativeNotificationDevice(userId: string, token: string) {
  ownerUser = userId; ownerToken = token
  const current = epoch
  return serial(() => activate(userId, token, current, false))
}
export function enableNativeNotificationDevice(userId: string, token: string): Promise<void> {
  ownerUser = userId; ownerToken = token
  const current = epoch
  return serial(async () => {
    if (!await activate(userId, token, current, true)) throw new Error(status === 'native_pending' ? 'unavailable' : 'denied')
  })
}
export function clearNativeNotificationDevice(): void {
  epoch++
  const previous = binding, token = ownerToken, user = ownerUser
  binding = null; ownerToken = null; ownerUser = null; status = 'native_pending'
  // Remove generic alerts already visible on this phone; the OS may still
  // deliver an accepted packet later, which is why it contains no private text.
  if (isNativePushPlatform() && import.meta.env.VITE_NATIVE_PUSH_ENABLED === 'true')
    void PushNotifications.removeAllDeliveredNotifications().catch(() => undefined)
  void serial(async () => {
    if (token && previous) await notificationsAPI.unsubscribe({ device_token: previous.device_token }, token).catch(() => undefined)
    const record = await readInstallation()
    if (record.binding && (!user || record.binding.user_id === user)
      && (!previous || record.binding.device_token === previous.device_token))
      await writeInstallation({ secret: record.secret })
  }).catch(() => undefined)
}
