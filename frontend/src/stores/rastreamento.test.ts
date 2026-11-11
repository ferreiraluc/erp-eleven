import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useRastreamentoStore, type Rastreamento, type RastreamentoResumo } from './rastreamento'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/services/api', () => ({ default: api }))
function deferred() {
  let resolve!: (value: { data: unknown }) => void
  const promise = new Promise<{ data: unknown }>(done => { resolve = done })
  return { promise, resolve }
}
const row = { id: 'confirmed' } as Rastreamento
const summary = { total_rastreamentos: 1 } as RastreamentoResumo
beforeEach(() => { vi.resetAllMocks(); setActivePinia(createPinia()) })

describe('Tracking read generations', () => {
  it.each(['list', 'summary'] as const)('does not let an older %s response override a newer failed read', async kind => {
    const store = useRastreamentoStore()
    store.rastreamentos = [row]; store.resumoDashboard = summary
    const old = deferred()
    api.get.mockReturnValueOnce(old.promise).mockRejectedValueOnce({ response: { data: { detail: 'Newest request failed' } } })
    const read = () => kind === 'list' ? store.listarRastreamentos() : store.obterResumoDashboard()
    const first = read()
    await expect(read()).rejects.toBeDefined()
    old.resolve({ data: kind === 'list' ? [{ id: 'obsolete' }] : { total_rastreamentos: 999 } })
    await first
    expect(store.rastreamentos).toEqual([row])
    expect(store.resumoDashboard).toEqual(summary)
    expect(store.error).toBe('Newest request failed')
  })

  it.each(['list', 'summary'] as const)('keeps the newest successful %s response when replies arrive out of order', async kind => {
    const store = useRastreamentoStore()
    const old = deferred()
    api.get.mockReturnValueOnce(old.promise).mockResolvedValueOnce({ data: kind === 'list' ? [row] : summary })
    const read = () => kind === 'list' ? store.listarRastreamentos() : store.obterResumoDashboard()
    const first = read()
    await read()
    old.resolve({ data: kind === 'list' ? [{ id: 'obsolete' }] : { total_rastreamentos: 999 } })
    await first
    expect(kind === 'list' ? store.rastreamentos : store.resumoDashboard).toEqual(kind === 'list' ? [row] : summary)
  })
})
