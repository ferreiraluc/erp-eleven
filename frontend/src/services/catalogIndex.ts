import { reactive } from 'vue'
import api from './api'
import { cachedItem, type CatalogFilters, type CatalogRow } from './catalogSearch'
import { storedToken, tokenIsCurrent } from './sessionStorage'
export const catalogCacheState = reactive({
  supported: typeof Worker !== 'undefined' && typeof indexedDB !== 'undefined',
  loading: false,
  count: 0,
  bytes: 0,
  syncedAt: 0,
  error: false,
})
let worker: Worker | undefined,
  ownerToken = '',
  ownerId = '',
  sequence = 0,
  epoch = 0,
  busyUntil = 0
type IndexPage = { items: CatalogRow[]; next_cursor: string | null }
const hidden = () => document.visibilityState === 'hidden'
let ready: Promise<unknown> | undefined,
  syncController: AbortController | undefined,
  syncing = false
let failures = 0,
  nextAttempt = 0
let syncTimer: ReturnType<typeof setTimeout> | undefined,
  idleTimer: ReturnType<typeof setTimeout> | undefined
const waiting = new Map<
  number,
  {
    resolve: (value: any) => void
    reject: (reason: unknown) => void
    timer: ReturnType<typeof setTimeout>
  }
>()
const current = () => !!ownerToken && storedToken() === ownerToken && tokenIsCurrent(ownerToken)
function rpc(type: string, data: unknown = {}) {
  return new Promise<any>((resolve, reject) => {
    if (!worker) {
      reject(new Error('unavailable'))
      return
    }
    const id = ++sequence,
      timer = setTimeout(() => {
        waiting.delete(id)
        reject(new Error('timeout'))
      }, 15000)
    waiting.set(id, { resolve, reject, timer })
    worker.postMessage({ id, type, data })
  })
}
function stopWorker() {
  worker?.terminate()
  worker = undefined
  ready = undefined
  for (const waiter of waiting.values()) {
    clearTimeout(waiter.timer)
    waiter.reject(new Error('closed'))
  }
  waiting.clear()
}
function releaseWhenIdle() {
  if (idleTimer) clearTimeout(idleTimer)
  idleTimer = setTimeout(
    () => {
      if (!syncing) stopWorker()
    },
    5 * 60 * 1000,
  )
}
function scheduleSync(delay = 5000) {
  if (syncTimer) clearTimeout(syncTimer)
  syncTimer = setTimeout(() => {
    syncTimer = undefined
    void refreshCatalogIndex()
  }, delay)
}
export async function prepareCatalogIndex(userId?: string) {
  const token = storedToken()
  if (!catalogCacheState.supported || !userId || !token || !tokenIsCurrent(token)) return
  if (ownerToken !== token || ownerId !== userId) {
    epoch++
    syncController?.abort()
    stopWorker()
    syncing = false
    failures = 0
    nextAttempt = 0
    ownerToken = token
    ownerId = userId
    Object.assign(catalogCacheState, {
      count: 0,
      bytes: 0,
      syncedAt: 0,
      error: false,
      loading: false,
    })
  }
  if (!worker) {
    try {
      worker = new Worker(new URL('./catalogIndex.worker.ts', import.meta.url), { type: 'module' })
    } catch {
      catalogCacheState.supported = false
      catalogCacheState.error = true
      return
    }
    worker.onmessage = (event) => {
      const waiter = waiting.get(event.data.id)
      if (!waiter) return
      waiting.delete(event.data.id)
      clearTimeout(waiter.timer)
      event.data.error
        ? waiter.reject(new Error(event.data.error))
        : waiter.resolve(event.data.result)
    }
    worker.onerror = () => {
      catalogCacheState.error = true
      stopWorker()
    }
    const mine = epoch
    ready = rpc('init', { scope: userId }).then((meta) => {
      if (mine === epoch && current()) Object.assign(catalogCacheState, meta)
    })
  }
  try {
    await ready
    if (!current()) return
    releaseWhenIdle()
    if (Date.now() - catalogCacheState.syncedAt > 6 * 60 * 60 * 1000 && !syncing && failures < 3)
      scheduleSync(Math.max(5000, nextAttempt - Date.now()))
  } catch {
    catalogCacheState.error = true
    stopWorker()
  }
}
export async function refreshCatalogIndex(manual = false) {
  if (manual) {
    failures = 0
    nextAttempt = 0
  }
  if (syncing || !current() || !worker) return
  const mine = epoch,
    token = ownerToken
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
  if (!navigator.onLine || hidden() || connection?.saveData) return
  if (Date.now() < busyUntil) {
    scheduleSync(busyUntil - Date.now() + 1000)
    return
  }
  syncing = true
  catalogCacheState.loading = true
  catalogCacheState.error = false
  let after: string | null = null
  try {
    await ready
    await rpc('begin', { generation: crypto.randomUUID() })
    do {
      if (!current() || mine !== epoch) throw new Error('session')
      // Searches take priority over the background copy on weak Wi-Fi.
      let page: IndexPage | undefined
      while (!page) {
        while (Date.now() < busyUntil) await new Promise((resolve) => setTimeout(resolve, 250))
        if (!current() || mine !== epoch) throw new Error('session')
        if (!navigator.onLine || hidden()) throw new Error('connection')
        syncController = new AbortController()
        try {
          const response = await api.get<IndexPage>('/api/inventory/search-index', {
            params: { after_id: after || undefined, limit: 500 },
            signal: syncController.signal,
            timeout: 12000,
            headers: { Authorization: `Bearer ${token}` },
          })
          page = response.data
        } catch (error) {
          if (!syncController.signal.aborted) throw error
        }
      }
      if (!current() || mine !== epoch) throw new Error('session')
      await rpc('put', { rows: page.items })
      after = page.next_cursor
      // Yield both network and CPU between bounded pages; never block checkout.
      await new Promise((resolve) => setTimeout(resolve, 150))
    } while (after)
    if (!current() || mine !== epoch) throw new Error('session')
    const meta = await rpc('finish')
    failures = 0
    nextAttempt = 0
    if (current() && mine === epoch) Object.assign(catalogCacheState, meta)
  } catch {
    if (mine === epoch && current()) {
      catalogCacheState.error = true
      failures++
      nextAttempt = Date.now() + 60000 * 2 ** failures
      if (failures < 3) scheduleSync(nextAttempt - Date.now())
    }
  } finally {
    if (mine === epoch) {
      syncing = false
      catalogCacheState.loading = false
      releaseWhenIdle()
    }
  }
}
export async function searchDeviceCatalog(query: string, filters: CatalogFilters = {}) {
  busyUntil = Date.now() + 1500
  syncController?.abort()
  if (!current() || !worker) return []
  const mine = epoch
  try {
    await ready
    releaseWhenIdle()
    const rows: CatalogRow[] = await rpc('search', { query, filters, limit: 50 })
    return mine === epoch && current() ? rows.map(cachedItem) : []
  } catch {
    return []
  }
}
export function clearCatalogIndex() {
  epoch++
  syncController?.abort()
  if (syncTimer) clearTimeout(syncTimer)
  if (idleTimer) clearTimeout(idleTimer)
  syncTimer = idleTimer = undefined
  ownerToken = ownerId = ''
  stopWorker()
  Object.assign(catalogCacheState, {
    count: 0,
    bytes: 0,
    syncedAt: 0,
    error: false,
    loading: false,
  })
  if (typeof indexedDB !== 'undefined') {
    const deletion = indexedDB.deleteDatabase('eleven-catalog-v1')
    deletion.onerror = () => {}
  }
}
