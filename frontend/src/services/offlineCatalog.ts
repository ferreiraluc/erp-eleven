import { reactive } from 'vue'
import { Capacitor } from '@capacitor/core'
import axios from 'axios'
import api from './api'
import { storedToken, tokenIsCurrent } from './sessionStorage'
import type { CatalogFilters } from './catalogSearch'
import type { OfflineCatalogFacets, OfflineCatalogItem, OfflineCatalogSearchResult } from './offlineCatalogSearch'
export type { OfflineCatalogFacets, OfflineCatalogItem, OfflineCatalogSearchResult } from './offlineCatalogSearch'

export const offlineCatalogState = reactive({ supported: typeof Worker !== 'undefined' && typeof indexedDB !== 'undefined', loading: false,
  count: 0, bytes: 0, syncedAt: 0, startedAt: 0, error: false, thumbnailCount: 0, thumbnailBytes: 0 })
const FULL_INTERVAL = 15 * 60 * 1000
type Context = { userId: string; token: string; isCurrent?: () => boolean }
type Page = { schema: number; owner_id: string; observed_at: string; items: OfflineCatalogItem[]; next_cursor: string | null }
let context: Context | undefined, worker: Worker | undefined, epoch = 0, sequence = 0, ready: Promise<void> | undefined
let syncing = false, fetchingThumbnails = false, failures = 0, retryAt = 0, busyUntil = 0
let thumbnailFailures = 0
let syncController: AbortController | undefined, thumbnailController: AbortController | undefined
let timer: ReturnType<typeof setTimeout> | undefined, thumbnailTimer: ReturnType<typeof setTimeout> | undefined
let deletion: Promise<void> = Promise.resolve()
const waiting = new Map<number, { resolve: (value: any) => void; reject: (reason: unknown) => void; timer: ReturnType<typeof setTimeout> }>()
const current = () => !!context && storedToken() === context.token && tokenIsCurrent(context.token) && (!context.isCurrent || context.isCurrent())
const online = () => navigator.onLine && document.visibilityState !== 'hidden' && !(navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
function invalidateDenied(error: unknown, mine: number) {
  if (mine === epoch && current() && axios.isAxiosError(error) && [401, 403].includes(error.response?.status || 0)) {
    window.dispatchEvent(new Event('erp:session-expired'))
    // Stop even in a caller without the root auth listener (isolated tests).
    if (mine === epoch) stopOfflineCatalog()
  }
}
function rpc<T = any>(type: string, data: unknown = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    if (!worker) { reject(new Error('unavailable')); return }
    const id = ++sequence, timeout = setTimeout(() => { waiting.delete(id); reject(new Error('timeout')) }, 30000)
    waiting.set(id, { resolve, reject, timer: timeout }); worker.postMessage({ id, type, data })
  })
}
function resetState() { Object.assign(offlineCatalogState, { loading: false, count: 0, bytes: 0, syncedAt: 0, startedAt: 0, error: false, thumbnailCount: 0, thumbnailBytes: 0 }) }
export function stopOfflineCatalog() {
  epoch++; context = undefined; ready = undefined
  clearTimeout(timer); clearTimeout(thumbnailTimer); timer = thumbnailTimer = undefined
  syncController?.abort(); thumbnailController?.abort(); worker?.terminate(); worker = undefined
  for (const waiter of waiting.values()) { clearTimeout(waiter.timer); waiter.reject(new Error('closed')) }
  waiting.clear(); syncing = fetchingThumbnails = false; failures = thumbnailFailures = retryAt = busyUntil = 0
  resetState()
}
/** Memory access stops synchronously. A subsequent login waits for deletion,
 * preventing a delayed logout cleanup from erasing the new account's cache. */
export function clearOfflineCatalog(): Promise<void> {
  stopOfflineCatalog()
  deletion = deletion.catch(() => undefined).then(() => new Promise<void>((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { resolve(); return }
    const request = indexedDB.deleteDatabase('eleven-offline-catalog-v1')
    request.onsuccess = () => resolve(); request.onerror = () => reject(request.error || new Error('storage'))
    // All our workers are closed above; another same-origin tab closes its DB
    // through onversionchange. Do not open a new user while deletion is blocked.
  }))
  void deletion.catch(() => undefined)
  return deletion
}
function schedule(delay = 60000) {
  clearTimeout(timer)
  timer = setTimeout(() => {
    timer = undefined
    if (!current()) return
    if (online() && Date.now() >= retryAt && (!offlineCatalogState.syncedAt || Date.now() - offlineCatalogState.syncedAt >= FULL_INTERVAL)) void refreshOfflineCatalog()
    else schedule()
  }, delay)
}
export async function prepareOfflineCatalog(next: Context): Promise<void> {
  if (!Capacitor.isNativePlatform() || !offlineCatalogState.supported || !next.userId || !next.token) return
  if (context?.userId === next.userId && context.token === next.token && worker) {
    context = { ...next, isCurrent: next.isCurrent || context.isCurrent }
    try { await ready } catch { offlineCatalogState.error = true }
    return
  }
  stopOfflineCatalog(); context = next
  const mine = epoch
  try {
    await deletion
    if (mine !== epoch || !current()) return
    worker = new Worker(new URL('./offlineCatalog.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = event => {
      const waiter = waiting.get(event.data.id)
      if (!waiter) return
      waiting.delete(event.data.id); clearTimeout(waiter.timer)
      event.data.error ? waiter.reject(new Error(event.data.error)) : waiter.resolve(event.data.result)
    }
    worker.onerror = () => { if (mine === epoch) { stopOfflineCatalog(); offlineCatalogState.error = true } }
    // No credential is sent to the worker or persisted in IndexedDB.
    ready = rpc('init', { scope: next.userId }).then(meta => { if (mine === epoch && current()) Object.assign(offlineCatalogState, meta) })
    await ready
    if (mine !== epoch || !current()) return
    schedule(5000); scheduleThumbnails()
  } catch { if (mine === epoch) { stopOfflineCatalog(); offlineCatalogState.error = true } }
}
export async function refreshOfflineCatalog(): Promise<void> {
  if (syncing || !worker || !current() || !online()) return
  if (Date.now() < busyUntil) { schedule(busyUntil - Date.now() + 1000); return }
  const mine = epoch, owner = context!, cursors = new Set<string>()
  syncing = true; offlineCatalogState.loading = true; offlineCatalogState.error = false
  let after: string | null = null, startedAt = 0, observedAt = 0
  try {
    await ready; await rpc('begin', { generation: crypto.randomUUID() })
    do {
      let page: Page | undefined
      while (!page) {
        while (Date.now() < busyUntil && current() && mine === epoch) await sleep(250)
        if (mine !== epoch || !current() || !online()) throw new Error('interrupted')
        syncController = new AbortController()
        try {
          page = (await api.get<Page>('/api/inventory/offline-catalog', { params: { after_id: after || undefined, limit: 500 },
            headers: { Authorization: `Bearer ${owner.token}` }, signal: syncController.signal, timeout: 12000 })).data
        } catch (error) { if (!syncController.signal.aborted) throw error }
      }
      if (mine !== epoch || !current()) throw new Error('session')
      observedAt = Date.parse(page.observed_at)
      if (page.schema !== 1 || page.owner_id !== owner.userId || !Array.isArray(page.items) || page.items.length > 500 || !Number.isFinite(observedAt)) throw new Error('invalid')
      startedAt ||= observedAt
      await rpc('put', { rows: page.items })
      after = page.next_cursor
      if (after && cursors.has(after)) throw new Error('cursor')
      if (after) cursors.add(after)
      if (after) await sleep(200)
    } while (after)
    if (mine !== epoch || !current()) throw new Error('session')
    const meta = await rpc('finish', { startedAt, syncedAt: observedAt })
    if (mine === epoch && current()) { Object.assign(offlineCatalogState, meta); failures = thumbnailFailures = retryAt = 0 }
  } catch (error) {
    invalidateDenied(error, mine)
    if (mine === epoch && current()) { offlineCatalogState.error = true; failures++; retryAt = Date.now() + Math.min(15 * 60000, 30000 * 2 ** failures) }
  } finally {
    if (mine === epoch) { syncing = false; offlineCatalogState.loading = false; schedule(); scheduleThumbnails() }
  }
}
const empty = (): OfflineCatalogSearchResult => ({ items: [], total: 0, syncedAt: 0, startedAt: 0 })
function foregroundSearch() { busyUntil = Date.now() + 1500; syncController?.abort(); thumbnailController?.abort() }
export async function searchOfflineCatalog(query: string, filters: CatalogFilters = {}, options: { limit?: number; offset?: number } = {}): Promise<OfflineCatalogSearchResult> {
  foregroundSearch()
  if (!current() || !worker) return empty()
  const mine = epoch
  try { await ready; const result = await rpc<OfflineCatalogSearchResult>('search', { query: query.slice(0, 256), filters, ...options }); return mine === epoch && current() ? result : empty() }
  catch (error) { if (mine === epoch && current()) throw error; return empty() }
}
export async function readOfflineCatalogItem(id: string): Promise<OfflineCatalogItem | null> {
  foregroundSearch(); if (!current() || !worker) return null
  const mine = epoch
  try { await ready; const result = await rpc<OfflineCatalogItem | null>('item', { id }); return mine === epoch && current() ? result : null }
  catch (error) { if (mine === epoch && current()) throw error; return null }
}
export async function getOfflineCatalogFacets(): Promise<OfflineCatalogFacets> {
  const none = { brands: [], categories: [], colors: [], sizes: [] }
  if (!current() || !worker) return none
  const mine = epoch
  try { await ready; const result = await rpc<OfflineCatalogFacets>('facets'); return mine === epoch && current() ? result : none }
  catch (error) { if (mine === epoch && current()) throw error; return none }
}
export async function loadOfflineThumbnail(id: string, version: string): Promise<string | null> {
  if (!current() || !worker) return null
  const mine = epoch
  try { await ready; const result = await rpc<string | null>('thumbnail', { id, version }); return mine === epoch && current() ? result : null }
  catch { return null }
}
function scheduleThumbnails(delay = 3000) {
  clearTimeout(thumbnailTimer)
  if (!current() || !online() || thumbnailFailures >= 3) return
  thumbnailTimer = setTimeout(() => { thumbnailTimer = undefined; void prefetchThumbnails() }, delay)
}
async function prefetchThumbnails() {
  if (!current() || !worker || !online() || !offlineCatalogState.count || thumbnailFailures >= 3) return
  if (fetchingThumbnails || syncing || Date.now() < busyUntil) { scheduleThumbnails(); return }
  const mine = epoch, owner = context!
  fetchingThumbnails = true
  let again = false, delay = 3000
  try {
    const candidates: { id: string; version: string }[] = await rpc('thumbnail-candidates')
    if (!candidates.length || mine !== epoch || !current()) return
    thumbnailController = new AbortController()
    const params = new URLSearchParams(); candidates.forEach(row => params.append('ids', row.id))
    const { data } = await api.get<{ thumbnails: Record<string, { image_data: string | null }>; retry_ids: string[] }>('/api/inventory/items/thumbnails', {
      params, headers: { Authorization: `Bearer ${owner.token}` }, signal: thumbnailController.signal, timeout: 15000,
    })
    for (const row of candidates) {
      if (mine !== epoch || !current()) return
      if (data.retry_ids?.includes(row.id)) continue
      const meta = await rpc('thumbnail-put', { ...row, image: data.thumbnails[row.id]?.image_data || null })
      if (mine === epoch && current()) Object.assign(offlineCatalogState, meta)
    }
    again = true
    if (data.retry_ids?.length) { thumbnailFailures++; delay = 30000 * 2 ** thumbnailFailures }
    else thumbnailFailures = 0
  } catch (error) {
    invalidateDenied(error, mine)
    // A transport/storage failure must not turn a weak connection into a 3s
    // request loop. Three attempts, then foreground/reconnect/new snapshot rearm.
    if (mine === epoch) { thumbnailFailures++; again = true; delay = 30000 * 2 ** thumbnailFailures }
  } finally {
    if (mine === epoch) { fetchingThumbnails = false; if (again) scheduleThumbnails(delay) }
  }
}
function resumed() { if (current() && online()) { thumbnailFailures = 0; schedule(1000); scheduleThumbnails() } }
window.addEventListener('online', resumed)
window.addEventListener('erp:native-app-active', resumed)
document.addEventListener('visibilitychange', resumed)
// Yield background bandwidth to ordinary stock/PDV interactions too, not only
// to the offline browser's own searches. These listeners never change the UI.
window.addEventListener('pointerdown', foregroundSearch, { passive: true })
window.addEventListener('keydown', foregroundSearch, { passive: true })
