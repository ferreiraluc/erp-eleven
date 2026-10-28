import { notificationsAPI } from './notifications'

export type PushSupport = 'ready' | 'denied' | 'unsupported' | 'ios'
export interface PushBinding {
  user_id: string
  device_token: string
}
interface SubscriptionHint {
  user_id: string
  session_key: string
}
const databaseName = 'eleven-notification-device'
let epoch = 0
let work: Promise<unknown> = Promise.resolve()
let audio: AudioContext | null = null
let activeBinding: PushBinding | null = null
let deviceOwner: string | null = null
let deviceSession: Promise<string> | null = null

function serial<T>(action: () => Promise<T>): Promise<T> {
  const next = work.catch(() => undefined).then(action)
  work = next.catch(() => undefined)
  return next
}
export function pushSupport(): PushSupport {
  const ios =
    /iP(ad|hone|od)/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const standalone =
    window.matchMedia?.('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone
  if (ios && !standalone) return 'ios'
  if (
    !window.isSecureContext ||
    !('serviceWorker' in navigator) ||
    !('Notification' in window) ||
    !('PushManager' in window)
  )
    return 'unsupported'
  return Notification.permission === 'denied' ? 'denied' : 'ready'
}
function deviceDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 1)
    request.onupgradeneeded = () => request.result.createObjectStore('binding')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
async function writeDeviceRecord(key: string, value: unknown) {
  const db = await deviceDB()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('binding', 'readwrite')
      const store = transaction.objectStore('binding')
      if (value) store.put(value, key)
      else store.delete(key)
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally {
    db.close()
  }
}
async function readDeviceRecord<T>(key: string): Promise<T | null> {
  const db = await deviceDB()
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction('binding').objectStore('binding').get(key)
      request.onsuccess = () => resolve(request.result || null)
      request.onerror = () => reject(request.error)
    })
  } finally {
    db.close()
  }
}
const writeBinding = (binding: PushBinding | null) => writeDeviceRecord('current', binding)
const readBinding = () => readDeviceRecord<PushBinding>('current')
async function clearBindingFor(
  userId: string | null,
  session: Promise<string> | null,
  known: PushBinding | null,
): Promise<PushBinding | null> {
  const fingerprint = session ? await session.catch(() => null) : null
  const db = await deviceDB()
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction('binding', 'readwrite')
      const store = transaction.objectStore('binding')
      const ownerRequest = store.get('subscription-owner')
      let removed: PushBinding | null = null
      ownerRequest.onsuccess = () => {
        const hint = ownerRequest.result as SubscriptionHint | undefined
        const request = store.get('current')
        request.onsuccess = () => {
          const binding = request.result as PushBinding | undefined
          if (
            binding &&
            (!userId || binding.user_id === userId) &&
            (!known || binding.device_token === known.device_token) &&
            (!fingerprint || !hint?.session_key || hint.session_key === fingerprint)
          ) {
            removed = binding
            store.delete('current')
          }
        }
      }
      transaction.oncomplete = () => resolve(removed)
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally {
    db.close()
  }
}
async function sessionKey(token: string) {
  // An irreversible fingerprint identifies reload versus a new login without
  // persisting the access token in the service worker's database.
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}
async function registration() {
  const registered = await navigator.serviceWorker.register('/notifications-sw.js', {
    scope: '/',
    updateViaCache: 'none',
  })
  if (!registered.active) {
    const worker = registered.installing || registered.waiting
    if (worker)
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => reject(new Error('worker-timeout')), 15000)
        const check = () => {
          if (worker.state === 'activated') {
            clearTimeout(timeout)
            resolve()
          } else if (worker.state === 'redundant') {
            clearTimeout(timeout)
            reject(new Error('worker-unavailable'))
          }
        }
        worker.addEventListener('statechange', check)
        check()
      })
  }
  return registered
}
function keyBytes(value: string): Uint8Array<ArrayBuffer> {
  const base64 = (value + '='.repeat((4 - (value.length % 4)) % 4))
    .replaceAll('-', '+')
    .replaceAll('_', '/')
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
}
function randomToken() {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), (number) =>
    number.toString(16).padStart(2, '0'),
  ).join('')
}
function assertCurrent(current: number) {
  if (current !== epoch) throw new Error('notification-session-changed')
}
async function saveSubscription(
  userId: string,
  token: string,
  registered: ServiceWorkerRegistration,
  subscription: PushSubscription,
  deviceToken: string,
  current: number,
  fingerprint: string,
) {
  assertCurrent(current)
  const payload = subscription.toJSON()
  if (!payload.endpoint || !payload.keys?.p256dh || !payload.keys?.auth)
    throw new Error('invalid-subscription')
  const result = await notificationsAPI.subscribe(
    {
      endpoint: payload.endpoint,
      keys: { p256dh: payload.keys.p256dh, auth: payload.keys.auth },
      device_token: deviceToken,
      device_name: navigator.userAgent.slice(0, 100),
    },
    token,
  )
  assertCurrent(current)
  if (result.user_id !== userId || result.device_token !== deviceToken || !result.active)
    throw new Error('invalid-subscription-owner')
  const binding = { user_id: userId, device_token: deviceToken }
  await writeDeviceRecord('subscription-owner', { user_id: userId, session_key: fingerprint })
  assertCurrent(current)
  await writeBinding(binding)
  assertCurrent(current)
  activeBinding = binding
  registered.active?.postMessage({ type: 'eleven-notification-binding', binding })
}
async function registerGrantedDevice(userId: string, token: string, current: number) {
  assertCurrent(current)
  const binding = await readBinding()
  const hint = await readDeviceRecord<SubscriptionHint>('subscription-owner')
  const fingerprint = await sessionKey(token)
  assertCurrent(current)
  const sameAccount = (hint?.user_id || binding?.user_id) === userId
  const sameSession =
    sameAccount && hint?.session_key === fingerprint && binding?.user_id === userId
  if (binding && binding.user_id !== userId) {
    const removed = await clearBindingFor(
      binding.user_id,
      hint?.session_key ? Promise.resolve(hint.session_key) : null,
      binding,
    )
    if (removed)
      navigator.serviceWorker.controller?.postMessage({
        type: 'eleven-notification-clear',
        binding: removed,
      })
  }
  // A previous account is invalidated before any network wait on a cold start.
  assertCurrent(current)
  const config = await notificationsAPI.pushConfig(token)
  if (!config.available || !config.public_key) throw new Error('unavailable')
  assertCurrent(current)
  if (!sameSession) {
    const removed = binding
      ? await clearBindingFor(
          binding.user_id,
          hint?.session_key ? Promise.resolve(hint.session_key) : null,
          binding,
        )
      : null
    activeBinding = null
    if (removed)
      navigator.serviceWorker.controller?.postMessage({
        type: 'eleven-notification-clear',
        binding: removed,
      })
  }
  const registered = await registration()
  let subscription = await registered.pushManager.getSubscription()
  if (subscription && !sameAccount) {
    await subscription.unsubscribe()
    subscription = null
  }
  assertCurrent(current)
  subscription ||= await registered.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: keyBytes(config.public_key),
  })
  const deviceToken = sameSession ? binding.device_token : randomToken()
  try {
    await saveSubscription(
      userId,
      token,
      registered,
      subscription,
      deviceToken,
      current,
      fingerprint,
    )
  } catch (error) {
    // A provider endpoint owned by another account is never transferred, even
    // after local storage was cleared. Renew it and let the server revalidate.
    if ((error as { response?: { status?: number } }).response?.status !== 409) throw error
    assertCurrent(current)
    await writeBinding(null)
    activeBinding = null
    await subscription.unsubscribe()
    subscription = await registered.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(config.public_key),
    })
    await saveSubscription(
      userId,
      token,
      registered,
      subscription,
      randomToken(),
      current,
      fingerprint,
    )
  }
}
/** Permission is requested synchronously from the user's trusted click, before any network await. */
export function enableNotificationDevice(userId: string, token: string): Promise<void> {
  if (pushSupport() !== 'ready') return Promise.reject(new Error(pushSupport()))
  if (Notification.permission !== 'granted' && navigator.userActivation?.isActive === false)
    return Promise.reject(new Error('gesture-required'))
  const permission =
    Notification.permission === 'granted'
      ? Promise.resolve('granted' as NotificationPermission)
      : Notification.requestPermission()
  deviceOwner = userId
  deviceSession = sessionKey(token)
  const current = epoch
  return serial(async () => {
    if ((await permission) !== 'granted') throw new Error('denied')
    assertCurrent(current)
    await registerGrantedDevice(userId, token, current)
  })
}
export function restoreNotificationDevice(userId: string, token: string): Promise<boolean> {
  deviceOwner = userId
  deviceSession = sessionKey(token)
  const current = epoch
  return serial(async () => {
    if (pushSupport() !== 'ready' || Notification.permission !== 'granted') return false
    // Persisted OS consent is reused. This function never invokes the native
    // permission prompt; browsers that require a tap for renewal can reject it.
    await registerGrantedDevice(userId, token, current)
    return true
  })
}
/** Clear display permission before asynchronous logout/session revocation can finish. */
export function clearNotificationDevice(): void {
  epoch++
  const knownBinding = activeBinding
  const userId = deviceOwner || knownBinding?.user_id || null
  const session = deviceSession
  activeBinding = null
  deviceOwner = null
  deviceSession = null
  // Do not wait for a slow config/subscribe request before revoking display
  // authorization left by a previous page load on this same device.
  const invalidation =
    typeof indexedDB !== 'undefined'
      ? clearBindingFor(userId, session, knownBinding).catch(() => null)
      : Promise.resolve(null)
  try {
    if (knownBinding)
      navigator.serviceWorker?.controller?.postMessage({
        type: 'eleven-notification-clear',
        binding: knownBinding,
      })
  } catch {
    /* unsupported */
  }
  // Once the immediate IDB transaction captures the old nonce, the worker can
  // also close its alerts safely. A delayed message cannot clear a new login.
  void invalidation
    .then((binding) => {
      if (binding)
        navigator.serviceWorker?.controller?.postMessage({
          type: 'eleven-notification-clear',
          binding,
        })
    })
    .catch(() => undefined)
  void serial(async () => {
    const binding = await invalidation
    if (typeof indexedDB !== 'undefined') await clearBindingFor(userId, session, knownBinding)
    if (!('serviceWorker' in navigator)) return
    const registered = await navigator.serviceWorker.getRegistration('/notifications-sw.js')
    if (binding) registered?.active?.postMessage({ type: 'eleven-notification-clear', binding })
    // Keep the native subscription and its ownership hint. The server revokes
    // the session; no payload can be displayed without the cleared binding.
    // Reusing this endpoint on the same account avoids a fresh Safari consent.
  }).catch(() => undefined)
}
export async function disableNotificationDevice(token: string): Promise<void> {
  const binding = typeof indexedDB !== 'undefined' ? await readBinding().catch(() => null) : null
  clearNotificationDevice()
  await notificationsAPI.unsubscribe(binding ? { device_token: binding.device_token } : {}, token)
}
export function allowNotificationSound() {
  const Audio =
    window.AudioContext ||
    (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Audio) return false
  try {
    audio ||= new Audio()
    void audio.resume().catch(() => undefined)
    return true
  } catch {
    return false
  }
}
export function playNotificationSound() {
  if (!audio || audio.state !== 'running' || document.visibilityState !== 'visible') return false
  try {
    const oscillator = audio.createOscillator(),
      gain = audio.createGain(),
      now = audio.currentTime
    oscillator.type = 'sine'
    oscillator.frequency.setValueAtTime(740, now)
    oscillator.frequency.setValueAtTime(988, now + 0.12)
    gain.gain.setValueAtTime(0, now)
    gain.gain.linearRampToValueAtTime(0.08, now + 0.025)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.32)
    oscillator.connect(gain)
    gain.connect(audio.destination)
    oscillator.start(now)
    oscillator.stop(now + 0.35)
    return true
  } catch {
    return false
  }
}
