import { offlineIndex, offlineSearch, offlineFacets, normalizeOfflineItem, validOfflineThumbnail, MAX_OFFLINE_ROWS, MAX_OFFLINE_BYTES, MAX_THUMBNAIL_BYTES, type OfflineCatalogItem } from './offlineCatalogSearch'

const DB = 'eleven-offline-catalog-v1'
type Meta = { generation: string; count: number; bytes: number; syncedAt: number; startedAt: number }
type ThumbnailInfo = { key: string; scope: string; id: string; version: string; bytes: number; checkedAt: number }
let db: IDBDatabase, scope = '', stage = '', stageCount = 0, stageBytes = 0
let meta: Meta = { generation: '', count: 0, bytes: 0, syncedAt: 0, startedAt: 0 }
let rows: OfflineCatalogItem[] = [], previewRows: OfflineCatalogItem[] = [], byId = new Map<string, OfflineCatalogItem>(), index = offlineIndex([])
let previews = new Map<string, ThumbnailInfo>(), thumbnailBytes = 0
const priority = new Set<string>()
const request = <T>(r: IDBRequest<T>) => new Promise<T>((resolve, reject) => { r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error) })
const committed = (tx: IDBTransaction) => new Promise<void>((resolve, reject) => { tx.oncomplete = () => resolve(); tx.onabort = tx.onerror = () => reject(tx.error || new Error('storage')) })
const state = () => ({ ...meta, thumbnailCount: [...previews.values()].filter(p => p.bytes > 0).length, thumbnailBytes })

async function open() {
  const r = indexedDB.open(DB, 1)
  r.onupgradeneeded = () => {
    r.result.createObjectStore('entries', { keyPath: 'key' }).createIndex('batch', 'batch')
    r.result.createObjectStore('meta')
    r.result.createObjectStore('thumbnailInfo', { keyPath: 'key' }).createIndex('scope', 'scope')
    r.result.createObjectStore('thumbnails')
  }
  db = await request(r)
  db.onversionchange = () => db.close()
}
async function eraseBatch(batch: string) {
  if (!batch) return
  const tx = db.transaction('entries', 'readwrite'), cursor = tx.objectStore('entries').index('batch').openCursor(IDBKeyRange.only(batch))
  cursor.onsuccess = () => { if (cursor.result) { cursor.result.delete(); cursor.result.continue() } }
  await committed(tx)
}
function prepareRows(values: unknown[]) {
  const rows = values.map(normalizeOfflineItem)
  return { rows, byId: new Map(rows.map(row => [row.id, row])), index: offlineIndex(rows),
    previewRows: rows.filter(row => row.has_image).sort((a, b) => b.created_at.localeCompare(a.created_at)) }
}
function useRows(next: ReturnType<typeof prepareRows>) {
  rows = next.rows; byId = next.byId; index = next.index; previewRows = next.previewRows
}
async function run(type: string, data: any) {
  if (type === 'init') {
    if (!db) await open()
    scope = data.scope
    meta = await request(db.transaction('meta').objectStore('meta').get(scope)) || { generation: '', count: 0, bytes: 0, syncedAt: 0, startedAt: 0 }
    const saved = meta.generation ? await request(db.transaction('entries').objectStore('entries').index('batch').getAll(meta.generation)) : []
    useRows(prepareRows(saved.map(entry => entry.row)))
    const info: ThumbnailInfo[] = await request(db.transaction('thumbnailInfo').objectStore('thumbnailInfo').index('scope').getAll(scope))
    previews = new Map(info.map(p => [p.id, p])); thumbnailBytes = info.reduce((sum, p) => sum + p.bytes, 0)
    return state()
  }
  if (type === 'begin') {
    const previous = await request(db.transaction('meta').objectStore('meta').get(scope + ':stage'))
    if (previous && previous !== meta.generation) await eraseBatch(previous)
    stage = `${scope}:${data.generation}`; stageCount = stageBytes = 0
    const tx = db.transaction('meta', 'readwrite'); tx.objectStore('meta').put(stage, scope + ':stage'); await committed(tx)
    return true
  }
  if (type === 'put') {
    if (!stage || !Array.isArray(data.rows) || data.rows.length > 500) throw new Error('invalid')
    const added = data.rows.map(normalizeOfflineItem)
    stageCount += added.length; stageBytes += new TextEncoder().encode(JSON.stringify(added)).byteLength
    if (stageCount > MAX_OFFLINE_ROWS || stageBytes > MAX_OFFLINE_BYTES) throw new Error('limit')
    const tx = db.transaction('entries', 'readwrite'), store = tx.objectStore('entries')
    for (const row of added) {
      if (typeof row.id !== 'string' || !row.id || typeof row.name !== 'string') { tx.abort(); throw new Error('invalid') }
      store.put({ key: `${stage}:${row.id}`, batch: stage, row })
    }
    await committed(tx)
    return true
  }
  if (type === 'finish') {
    if (!stage || !Number.isFinite(data.startedAt) || !Number.isFinite(data.syncedAt)) throw new Error('invalid')
    const saved = await request(db.transaction('entries').objectStore('entries').index('batch').getAll(stage))
    // Duplicate IDs / repeated server cursor must never publish a partial copy.
    if (saved.length !== stageCount) throw new Error('invalid')
    // Build/validate the index BEFORE switching the durable active generation.
    const prepared = prepareRows(saved.map(entry => entry.row))
    const next: Meta = { generation: stage, count: stageCount, bytes: stageBytes, startedAt: data.startedAt, syncedAt: data.syncedAt }
    const tx = db.transaction('meta', 'readwrite'); tx.objectStore('meta').put(next, scope); tx.objectStore('meta').delete(scope + ':stage'); await committed(tx)
    const old = meta.generation; meta = next; stage = ''; useRows(prepared)
    // Cleanup cannot turn a successfully committed generation into a reported
    // failure. Stale previews are never served when their revision differs.
    try { await eraseBatch(old) } catch { /* Disposable old generation. */ }
    try {
      const obsolete = [...previews].filter(([id, info]) => { const row = byId.get(id); return !row?.has_image || row.updated_at !== info.version })
      const cleanup = db.transaction(['thumbnailInfo', 'thumbnails'], 'readwrite')
      for (const [, info] of obsolete) { cleanup.objectStore('thumbnailInfo').delete(info.key); cleanup.objectStore('thumbnails').delete(info.key) }
      await committed(cleanup)
      for (const [id, info] of obsolete) { previews.delete(id); thumbnailBytes -= info.bytes }
    } catch { /* Keep budget accounting until a later cleanup succeeds. */ }
    return state()
  }
  if (type === 'search') {
    const result = offlineSearch(index, data.query, data.filters || {}, data.limit, data.offset)
    for (const row of result.items) priority.add(row.id)
    return { ...result, startedAt: meta.startedAt, syncedAt: meta.syncedAt }
  }
  if (type === 'item') return byId.get(data.id) || null
  if (type === 'facets') return offlineFacets(rows)
  if (type === 'thumbnail') {
    const row = byId.get(data.id), info = previews.get(data.id)
    if (!row || row.updated_at !== data.version) return null
    priority.add(row.id)
    if (!info || info.version !== data.version || !info.bytes) return null
    return await request(db.transaction('thumbnails').objectStore('thumbnails').get(info.key)) || null
  }
  if (type === 'thumbnail-candidates') {
    if (thumbnailBytes + 12 * 48 * 1024 > MAX_THUMBNAIL_BYTES) return []
    const wanted = (row: OfflineCatalogItem): boolean => !!row.has_image && (!previews.has(row.id) || previews.get(row.id)!.version !== row.updated_at || (!previews.get(row.id)!.bytes && Date.now() - previews.get(row.id)!.checkedAt > 6 * 60 * 60 * 1000))
    const candidates = [...priority].map(id => byId.get(id)).filter((row): row is OfflineCatalogItem => !!row && wanted(row))
    const ids = new Set(candidates.map(row => row.id))
    for (const row of previewRows) { if (candidates.length >= 12) break; if (!ids.has(row.id) && wanted(row)) { candidates.push(row); ids.add(row.id) } }
    return candidates.slice(0, 12).map(row => ({ id: row.id, version: row.updated_at }))
  }
  if (type === 'thumbnail-put') {
    const row = byId.get(data.id), previous = previews.get(data.id)
    if (!row?.has_image || row.updated_at !== data.version) return state()
    const image = validOfflineThumbnail(data.image) ? data.image : null
    const bytes = image ? new TextEncoder().encode(image).byteLength : 0
    if (thumbnailBytes - (previous?.bytes || 0) + bytes > MAX_THUMBNAIL_BYTES) return state()
    const info: ThumbnailInfo = { key: `${scope}:${data.id}`, scope, id: data.id, version: data.version, bytes, checkedAt: Date.now() }
    const tx = db.transaction(['thumbnailInfo', 'thumbnails'], 'readwrite')
    tx.objectStore('thumbnailInfo').put(info)
    if (image) tx.objectStore('thumbnails').put(image, info.key)
    else tx.objectStore('thumbnails').delete(info.key)
    await committed(tx)
    previews.set(data.id, info); priority.delete(data.id); thumbnailBytes += bytes - (previous?.bytes || 0)
    return state()
  }
  return null
}
// Serialize staging and metadata writes, while each page remains bounded.
let pending = Promise.resolve()
self.onmessage = (event: MessageEvent) => {
  const { id, type, data } = event.data
  pending = pending.then(async () => {
    try { self.postMessage({ id, result: await run(type, data) }) }
    catch { self.postMessage({ id, error: 'offline_cache_unavailable' }) }
  })
}
