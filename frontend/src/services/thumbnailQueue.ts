import { inventoryAPI } from '@/services/api'
import { storedToken } from '@/services/sessionStorage'

type Preview = { image_data: string | null }
type Waiting = { current: () => boolean; resolve: (value: Preview | null) => void; reject: (reason: unknown) => void }
type Job = { key: string; id: string; scope: string | null; waiting: Waiting[]; attempts: number }
const queue: Job[] = []
const pending = new Map<string, Job>()
const cache = new Map<string, { value: Preview; expires: number }>()
const MAX_CACHE = 128 // <= 6 MiB of 48 KiB previews, never original photos.
const MAX_ACTIVE = 2
const BATCH_SIZE = 12
let active = 0
let scope = storedToken()
let timer: ReturnType<typeof setTimeout> | undefined

function schedule() {
  if (!timer) timer = setTimeout(() => { timer = undefined; drain() }, 8)
}
function finish(job: Job, value: Preview | null, error?: unknown) {
  if (pending.get(job.key) === job) pending.delete(job.key)
  for (const waiter of job.waiting) {
    if (!waiter.current() || storedToken() !== job.scope) waiter.resolve(null)
    else if (error) waiter.reject(error)
    else waiter.resolve(value)
  }
}
function drain() {
  while (active < MAX_ACTIVE && queue.length) {
    const batch: Job[] = []
    while (queue.length && batch.length < BATCH_SIZE) {
      const job = queue.shift()!
      if (job.scope !== storedToken() || !job.waiting.some(w => w.current())) finish(job, null)
      else batch.push(job)
    }
    if (!batch.length) continue
    active++
    inventoryAPI.getThumbnails([...new Set(batch.map(job => job.id))]).then(result => {
      for (const job of batch) {
        if (result.retry_ids.includes(job.id) && job.attempts++ < 1 && job.scope === storedToken()) {
          setTimeout(() => { queue.push(job); schedule() }, 2000)
          continue
        }
        const value = result.thumbnails[job.id] || null
        if (value && job.scope === storedToken()) {
          cache.delete(job.key)
          cache.set(job.key, { value, expires: Date.now() + 300000 })
          while (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value!)
        }
        finish(job, value)
      }
    }, error => batch.forEach(job => finish(job, null, error)))
      .finally(() => { active--; schedule() })
  }
}

export function loadThumbnail(id: string, isCurrent: () => boolean, version = ''): Promise<Preview | null> {
  const currentScope = storedToken()
  if (scope !== currentScope) { scope = currentScope; cache.clear(); pending.clear() }
  const key = `${id}:${version}`
  const hit = cache.get(key)
  if (hit && hit.expires > Date.now()) {
    cache.delete(key); cache.set(key, hit)
    return Promise.resolve(isCurrent() ? hit.value : null)
  }
  return new Promise((resolve, reject) => {
    const waiting = { current: isCurrent, resolve, reject }
    const existing = pending.get(key)
    if (existing) { existing.waiting.push(waiting); return }
    const job: Job = { key, id, scope: currentScope, waiting: [waiting], attempts: 0 }
    pending.set(key, job); queue.push(job); schedule()
  })
}
