import { searchable, searchCatalog, type CatalogRow, type Searchable } from './catalogSearch'
const DB = 'eleven-catalog-v1',
  MAX_ROWS = 75000,
  MAX_BYTES = 64 * 1024 * 1024
let db: IDBDatabase,
  scope = '',
  generation = '',
  stage = '',
  count = 0,
  bytes = 0,
  index: Searchable[] = []
let stageRows: CatalogRow[] = []
const request = <T>(r: IDBRequest<T>) =>
  new Promise<T>((resolve, reject) => {
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error)
  })
const committed = (tx: IDBTransaction) =>
  new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onabort = tx.onerror = () => reject(tx.error || new Error('storage'))
  })
async function open() {
  const r = indexedDB.open(DB, 1)
  r.onupgradeneeded = () => {
    r.result.createObjectStore('entries', { keyPath: 'key' }).createIndex('batch', 'batch')
    r.result.createObjectStore('meta')
  }
  db = await request(r)
  db.onversionchange = () => db.close()
}
async function eraseBatch(batch: string) {
  if (!batch) return
  const tx = db.transaction('entries', 'readwrite'),
    store = tx.objectStore('entries')
  const cursor = store.index('batch').openCursor(IDBKeyRange.only(batch))
  cursor.onsuccess = () => {
    if (cursor.result) {
      cursor.result.delete()
      cursor.result.continue()
    }
  }
  await committed(tx)
}
async function run(type: string, data: any) {
  if (type === 'init') {
    if (!db) await open()
    scope = data.scope
    const meta: any = await request(db.transaction('meta').objectStore('meta').get(scope))
    generation = meta?.generation || ''
    const rows: any[] = generation
      ? await request(
          db.transaction('entries').objectStore('entries').index('batch').getAll(generation),
        )
      : []
    index = rows.map((entry) => searchable(entry.row))
    return meta || { count: 0, bytes: 0, syncedAt: 0 }
  }
  if (type === 'begin') {
    stage = scope + ':' + data.generation
    count = bytes = 0
    stageRows = []
    // A previous interrupted staging batch is disposable; the active one stays intact.
    const previous: any = await request(
      db
        .transaction('meta')
        .objectStore('meta')
        .get(scope + ':stage'),
    )
    if (previous && previous !== generation) await eraseBatch(previous)
    const tx = db.transaction('meta', 'readwrite')
    tx.objectStore('meta').put(stage, scope + ':stage')
    await committed(tx)
    return true
  }
  if (type === 'put') {
    const added: CatalogRow[] = data.rows
    count += added.length
    bytes += new TextEncoder().encode(JSON.stringify(added)).byteLength
    if (count > MAX_ROWS || bytes > MAX_BYTES) throw new Error('limit')
    const tx = db.transaction('entries', 'readwrite'),
      store = tx.objectStore('entries')
    for (const row of added) store.put({ key: stage + ':' + row.id, batch: stage, row })
    await committed(tx)
    stageRows.push(...added)
    return { count, bytes }
  }
  if (type === 'finish') {
    const old = generation,
      meta = { generation: stage, count, bytes, syncedAt: Date.now() }
    const tx = db.transaction('meta', 'readwrite')
    tx.objectStore('meta').put(meta, scope)
    tx.objectStore('meta').delete(scope + ':stage')
    await committed(tx)
    generation = stage
    index = stageRows.map(searchable)
    stageRows = []
    void eraseBatch(old).catch(() => {})
    return meta
  }
  if (type === 'search') return searchCatalog(index, data.query, data.filters, data.limit)
  if (type === 'close') {
    db?.close()
    index = []
    stageRows = []
    return true
  }
  return null
}
self.onmessage = async (event: MessageEvent) => {
  const { id, type, data } = event.data
  try {
    self.postMessage({ id, result: await run(type, data) })
  } catch {
    self.postMessage({ id, error: 'cache_unavailable' })
  }
}
