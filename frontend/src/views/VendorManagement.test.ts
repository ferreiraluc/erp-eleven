import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import VendorManagement from './VendorManagement.vue'

const api = vi.hoisted(() => ({ getAll: vi.fn(), update: vi.fn(), create: vi.fn() }))
vi.mock('@/services/api', () => ({ vendorsAPI: api }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: vi.fn() }) }))
vi.mock('@/components/vendors/VendorActivityPanel.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/components/ColorPicker.vue', () => ({ default: { template: '<div />' } }))

const vendor = { id: 'fixture-a', nome: 'Vendedor exemplo', ativo: true, taxa_comissao: 10, meta_semanal: 0, created_at: '2026-10-01' }
let app: App | undefined
let container: HTMLDivElement
const flush = async () => { for (let n = 0; n < 6; n++) await Promise.resolve(); await nextTick() }
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}
async function mount() {
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(VendorManagement).use(i18n)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(container)
  await flush()
  return i18n
}
beforeEach(() => {
  container = document.createElement('div')
  document.body.append(container)
  api.getAll.mockResolvedValue([{ ...vendor }])
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.resetAllMocks() })

describe('Vendor management feedback', () => {
  it('reports and translates a failed load, then retries without presenting a first-registration prompt', async () => {
    api.getAll.mockRejectedValueOnce(new Error('offline'))
    const i18n = await mount()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os vendedores.')
    expect(container.textContent).not.toContain('Cadastre seu primeiro vendedor')
    for (const [locale, message] of [['es', 'No se pudieron cargar los vendedores.'], ['en', 'Unable to load sellers.']] as const) {
      i18n.global.locale.value = locale
      await nextTick()
      expect(container.querySelector('[role="alert"]')?.textContent).toContain(message)
    }
    container.querySelector<HTMLButtonElement>('.load-error button')!.click()
    await flush()
    expect(api.getAll).toHaveBeenCalledTimes(2)
    expect(container.querySelector('.load-error')).toBeNull()
    expect(container.querySelector('tbody')?.textContent).toContain(vendor.nome)
  })

  it('offers to clear an unmatched search instead of suggesting a first seller', async () => {
    await mount()
    const search = container.querySelector<HTMLInputElement>('.search-input input')!
    search.value = 'sem correspondência'
    search.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    expect(container.querySelector('.empty-state')?.textContent).toContain('Nenhum vendedor corresponde aos filtros aplicados')
    expect(container.textContent).not.toContain('Cadastre seu primeiro vendedor')
    container.querySelector<HTMLButtonElement>('.empty-state button')!.click()
    await nextTick()
    expect(search.value).toBe('')
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1)
    expect(api.getAll).toHaveBeenCalledOnce()
  })

  it('serializes each seller update, preserves failed status and keeps other seller updates independent', async () => {
    const second = { ...vendor, id: 'fixture-b', nome: 'Outro exemplo' }
    api.getAll.mockResolvedValueOnce([{ ...vendor }, second])
    const firstUpdate = deferred<typeof vendor>()
    const secondUpdate = deferred<typeof second>()
    api.update.mockImplementation((id: string) => id === vendor.id ? firstUpdate.promise : secondUpdate.promise)
    const i18n = await mount()
    const buttons = container.querySelectorAll<HTMLButtonElement>('.action-button.deactivate')
    buttons[0]!.click()
    buttons[0]!.click()
    await nextTick()
    expect(api.update).toHaveBeenCalledTimes(1)
    expect(buttons[0]!.disabled).toBe(true)
    expect(buttons[1]!.disabled).toBe(false)
    expect(container.querySelector('[role="status"]')?.textContent).toContain('Salvando...')
    buttons[1]!.click()
    secondUpdate.resolve({ ...second, ativo: false })
    await flush()
    firstUpdate.reject(new Error('offline'))
    await flush()
    const rows = container.querySelectorAll('tbody tr')
    expect(rows[0]!.querySelector('.status-badge.active')).not.toBeNull()
    expect(rows[1]!.querySelector('.status-badge.inactive')).not.toBeNull()
    expect(rows[0]!.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível alterar o status.')
    i18n.global.locale.value = 'en'
    await nextTick()
    expect(rows[0]!.querySelector('[role="alert"]')?.textContent).toContain('Unable to change the status.')
    expect(rows[0]!.querySelector<HTMLButtonElement>('.deactivate')!.disabled).toBe(false)
    expect(api.update).toHaveBeenCalledTimes(2)
    expect(api.getAll).toHaveBeenCalledOnce()
  })
})
