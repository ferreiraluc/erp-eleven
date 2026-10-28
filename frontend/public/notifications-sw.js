/* Push only. This worker never intercepts fetches or caches private ERP data. */
const DATABASE = 'eleven-notification-device'
function bindingStore(action) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(DATABASE, 1)
    open.onupgradeneeded = () => open.result.createObjectStore('binding')
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const db = open.result,
        transaction = db.transaction('binding', action ? 'readwrite' : 'readonly')
      const store = transaction.objectStore('binding'),
        request = store.get('current')
      let value = null
      request.onsuccess = () => {
        value = request.result || null
        // Scoped logout messages may arrive after another login. They may only
        // clear the binding that was captured by the account being closed.
        if (action === true || (action && matches(value, action))) store.delete('current')
      }
      transaction.oncomplete = () => {
        db.close()
        resolve(value)
      }
      transaction.onerror = () => {
        db.close()
        reject(transaction.error)
      }
    }
  })
}
function matches(binding, data) {
  return (
    binding &&
    typeof data?.user_id === 'string' &&
    typeof data?.device_token === 'string' &&
    binding.user_id === data.user_id &&
    binding.device_token === data.device_token
  )
}
function expired(data) {
  return (
    typeof data?.expires_at === 'number' &&
    (!Number.isFinite(data.expires_at) || data.expires_at <= Date.now())
  )
}
function safePath(path) {
  if (
    typeof path !== 'string' ||
    path.length > 500 ||
    !path.startsWith('/') ||
    path.startsWith('//') ||
    /[\\#\s\u0000-\u001f]/.test(path) ||
    path.split('?', 1)[0].includes('%')
  )
    return '/notificacoes'
  const allowed = [
    '/notificacoes',
    '/dashboard',
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
  return allowed.includes(path.split(/[?#]/, 1)[0]) ? path : '/notificacoes'
}
self.addEventListener('install', () => {
  self.skipWaiting()
})
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})
self.addEventListener('message', (event) => {
  if (event.data?.type === 'eleven-notification-clear') {
    const scoped = Object.prototype.hasOwnProperty.call(event.data, 'binding')
    const binding = event.data.binding
    event.waitUntil(
      Promise.all([
        bindingStore(scoped ? binding || false : true),
        self.registration.getNotifications().then((items) =>
          items.forEach((item) => {
            if (!binding || matches(binding, item.data)) item.close()
          }),
        ),
      ]),
    )
  }
})
self.addEventListener('push', (event) => {
  event.waitUntil(
    (async () => {
      let data
      try {
        data = event.data?.json()
      } catch {
        return
      }
      const binding = await bindingStore(false)
      if (!matches(binding, data) || expired(data) || typeof data.notification_id !== 'string')
        return
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      // Logout/account changes can finish while the browser enumerates clients.
      // Recheck immediately before displaying private notification content.
      if (!matches(await bindingStore(false), data) || expired(data)) return
      windows.forEach((client) =>
        client.postMessage({
          type: 'eleven-notification-refresh',
          user_id: data.user_id,
          device_token: data.device_token,
        }),
      )
      // Legacy payloads had no deadline and contained only a generic alert.
      // Show actual content only when the server supplied a live session cap.
      const liveContent = typeof data.expires_at === 'number'
      const title =
        liveContent && typeof data.title === 'string' ? data.title.trim().slice(0, 120) : ''
      const body =
        liveContent && typeof data.body === 'string' ? data.body.trim().slice(0, 1000) : ''
      await self.registration.showNotification(title || 'ELEVEN', {
        body: body || 'Você tem uma nova notificação no sistema.',
        icon: '/icons/eleven-midnight-v3-192.png',
        badge: '/icons/eleven-midnight-v3-48.png',
        tag: `eleven-${data.notification_id}`,
        renotify: false,
        silent:
          data.sound === false || windows.some((client) => client.visibilityState === 'visible'),
        data: {
          user_id: data.user_id,
          device_token: data.device_token,
          notification_id: data.notification_id,
          action_path: safePath(data.action_path),
          expires_at: data.expires_at,
        },
      })
    })().catch(() => undefined),
  )
})
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    (async () => {
      const data = event.notification.data,
        binding = await bindingStore(false)
      if (!matches(binding, data) || expired(data)) return
      const path = safePath(data.action_path),
        windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const client = windows.find((item) => new URL(item.url).origin === self.location.origin)
      if (client) {
        client.postMessage({ type: 'eleven-notification-open', ...data, action_path: path })
        await client.focus()
      } else await self.clients.openWindow(`${self.location.origin}/#${path}`)
    })().catch(() => undefined),
  )
})
