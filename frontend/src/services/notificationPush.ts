import { notificationsAPI } from './notifications'

export type PushSupport = 'ready' | 'denied' | 'unsupported' | 'ios'
export interface PushBinding {
  user_id: string
  device_token: string
}
const databaseName = 'eleven-notification-device'
let epoch = 0
let work: Promise<unknown> = Promise.resolve()
let audio: AudioContext | null = null

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
async function writeBinding(binding: PushBinding | null) {
  const db = await deviceDB()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('binding', 'readwrite')
      const store = transaction.objectStore('binding')
      if (binding) store.put(binding, 'current')
      else store.delete('current')
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally {
    db.close()
  }
}
async function readBinding(): Promise<PushBinding | null> {
  const db = await deviceDB()
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction('binding').objectStore('binding').get('current')
      request.onsuccess = () => resolve(request.result || null)
      request.onerror = () => reject(request.error)
    })
  } finally {
    db.close()
  }
}
async function registration() {
  const registered = await navigator.serviceWorker.register('/notifications-sw.js', { scope: '/', updateViaCache:'none' })
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
  await writeBinding(binding)
  assertCurrent(current)
  registered.active?.postMessage({ type: 'eleven-notification-binding', binding })
}
/** Permission is requested synchronously from the user's trusted click, before any network await. */
export function enableNotificationDevice(userId: string, token: string): Promise<void> {
  if (pushSupport() !== 'ready') return Promise.reject(new Error(pushSupport()))
  const permission =
    Notification.permission === 'granted'
      ? Promise.resolve('granted' as NotificationPermission)
      : Notification.requestPermission()
  const current = epoch
  return serial(async () => {
    if ((await permission) !== 'granted') throw new Error('denied')
    assertCurrent(current)
    const config = await notificationsAPI.pushConfig(token)
    if (!config.available || !config.public_key) throw new Error('unavailable')
    assertCurrent(current)
    const registered = await registration()
    const oldBinding = await readBinding()
    let subscription = await registered.pushManager.getSubscription()
    if (subscription && oldBinding?.user_id !== userId) {
      await subscription.unsubscribe()
      subscription = null
    }
    assertCurrent(current)
    subscription ||= await registered.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(config.public_key),
    })
    const deviceToken = oldBinding?.user_id === userId ? oldBinding.device_token : randomToken()
    try {
      await saveSubscription(userId, token, registered, subscription, deviceToken, current)
    } catch (error) {
      // An endpoint from a different account is never reassigned. A new native
      // subscription is only requested within this explicit activation flow.
      if ((error as { response?: { status?: number } }).response?.status !== 409) throw error
      assertCurrent(current)
      await subscription.unsubscribe()
      subscription = await registered.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(config.public_key),
      })
      await saveSubscription(userId, token, registered, subscription, randomToken(), current)
    }
  })
}
export function restoreNotificationDevice(userId: string, token: string): Promise<boolean> {
  const current = epoch
  return serial(async () => {
    if (pushSupport() !== 'ready' || Notification.permission !== 'granted') return false
    const binding = await readBinding()
    assertCurrent(current)
    if (binding?.user_id !== userId) return false
    const registered = await registration()
    const subscription = await registered.pushManager.getSubscription()
    if (!subscription) {
      await writeBinding(null)
      return false
    }
    await saveSubscription(userId, token, registered, subscription, binding.device_token, current)
    return true
  })
}
/** Clear display permission before asynchronous logout/session revocation can finish. */
export function clearNotificationDevice(): void {
  epoch++
  try {
    navigator.serviceWorker?.controller?.postMessage({ type: 'eleven-notification-clear' })
  } catch {
    /* unsupported */
  }
  void serial(async () => {
    if (typeof indexedDB !== 'undefined') await writeBinding(null)
    if (!('serviceWorker' in navigator)) return
    const registered = await navigator.serviceWorker.getRegistration('/notifications-sw.js')
    registered?.active?.postMessage({ type: 'eleven-notification-clear' })
    const subscription = await registered?.pushManager.getSubscription()
    if (subscription) await subscription.unsubscribe()
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
