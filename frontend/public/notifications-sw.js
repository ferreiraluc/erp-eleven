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
        request = action ? store.delete('current') : store.get('current')
      let value = null
      request.onsuccess = () => {
        value = request.result || null
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
function safePath(path) {
  if (
    typeof path !== 'string' ||
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
    event.waitUntil(
      Promise.all([
        bindingStore(true),
        self.registration.getNotifications().then((items) => items.forEach((item) => item.close())),
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
      if (!matches(binding, data) || typeof data.notification_id !== 'string') return
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      windows.forEach((client) =>
        client.postMessage({
          type: 'eleven-notification-refresh',
          user_id: data.user_id,
          device_token: data.device_token,
        }),
      )
      await self.registration.showNotification('ELEVEN', {
        body: 'Você tem uma nova notificação no sistema.',
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
      if (!matches(binding, data)) return
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
