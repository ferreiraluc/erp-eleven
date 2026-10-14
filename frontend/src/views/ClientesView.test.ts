import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import ClientesView from './ClientesView.vue'

const api = vi.hoisted(() => ({ getPage: vi.fn(), delete: vi.fn() }))
vi.mock('@/services/api', () => ({ clientesAPI: api }))
vi.mock('@/components/clientes/ClienteFormModal.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/logistics/CustomerLogisticsPanel.vue', () => ({ default: { render: () => null } }))
const active = { id: 'active', nome: 'Cliente ativo QA', ativo: true }
const inactive = { id: 'inactive', nome: 'Cliente inativo QA', ativo: false }
const pageResult = (items = [active], page = 1, total = items.length) => ({ items, page, page_size: 20, total })
let app: App | undefined, container: HTMLDivElement
const settle = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); await nextTick() }
async function mount() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] })
  await router.push('/'); await router.isReady()
  app = createApp(ClientesView).use(createPinia()).use(router).use(i18n)
  app.mount(container); await settle()
}
function button(text: string) {
  return Array.from(container.querySelectorAll('button')).find(button => button.textContent?.trim() === text)!
}
beforeEach(() => {
  vi.useFakeTimers()
  i18n.global.locale.value = 'pt'
  container = document.createElement('div'); document.body.append(container)
  api.getPage.mockImplementation(async ({ ativo, include_inactive, page }) => pageResult(include_inactive ? [active, inactive] : ativo ? [active] : [inactive], page))
  api.delete.mockResolvedValue({ message: 'OK' })
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.useRealTimers(); vi.resetAllMocks() })

describe('Customer status filters', () => {
  it('queries active, inactive and all customers explicitly and shows their respective records', async () => {
    await mount()
    expect(api.getPage).toHaveBeenLastCalledWith({ search: undefined, ativo: true, include_inactive: false, page: 1, page_size: 20 })
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(1)
    button('Inativos').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith({ search: undefined, ativo: false, include_inactive: false, page: 1, page_size: 20 })
    expect(container.querySelector('.cliente-name')?.textContent || container.textContent).toContain(inactive.nome)
    expect(container.querySelector('.cliente-card.inactive')).not.toBeNull()
    button('Todos').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith({ search: undefined, ativo: true, include_inactive: true, page: 1, page_size: 20 })
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(2)
    expect(button('Todos').getAttribute('aria-pressed')).toBe('true')
  })

  it('does not let an older active-only response replace the currently selected all filter', async () => {
    let finishOld!: (value: unknown) => void
    api.getPage.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await mount(); button('Todos').click(); await settle()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(2)
    finishOld(pageResult()); await settle()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(2)
    expect(button('Todos').getAttribute('aria-pressed')).toBe('true')
  })

  it('shows a recoverable error instead of claiming there are no customers', async () => {
    api.getPage.mockRejectedValueOnce(new Error('offline'))
    await mount()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os clientes.')
    expect(container.textContent).not.toContain('Nenhum cliente encontrado')
    button('Tentar novamente').click(); await settle()
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(1)
  })

  it('shows the server total and replaces pages without truncating the directory', async () => {
    api.getPage.mockImplementation(async ({ page }) => pageResult([{ ...active, id: `page-${page}`, nome: `Página ${page}` }], page, 225))
    await mount()
    expect(container.querySelector('.total-count')?.textContent).toBe('225 clientes')
    expect(container.querySelector('.customer-pagination')?.textContent).toContain('Página 1 de 12')
    expect(button('Anterior').disabled).toBe(true)
    button('Próxima').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 20 }))
    expect(container.querySelector('.cliente-name')?.textContent).toBe('Página 2')
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(1)
    expect(button('Anterior').disabled).toBe(false)
  })

  it('resets the page for search and status, applying the search on the server', async () => {
    api.getPage.mockImplementation(async ({ page }) => pageResult([active], page, 225))
    await mount()
    button('Próxima').click(); await settle()
    const search = container.querySelector('input')!
    search.value = '  cliente antigo  '; search.dispatchEvent(new Event('input')); await nextTick()
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, search: 'cliente antigo' }))
    button('Próxima').click(); await settle()
    button('Inativos').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, search: 'cliente antigo', ativo: false }))
  })

  it('keeps the focused pagination button mounted and disabled while fetching', async () => {
    api.getPage.mockResolvedValueOnce(pageResult([active], 1, 45))
    await mount()
    let finishPage!: (value: ReturnType<typeof pageResult>) => void
    api.getPage.mockImplementationOnce(() => new Promise(resolve => { finishPage = resolve }))
    const next = button('Próxima')
    next.focus(); next.click(); await settle()
    expect(button('Próxima')).toBe(next)
    expect(document.activeElement).toBe(next)
    expect(next.disabled).toBe(true)
    expect(button('Anterior').disabled).toBe(true)
    finishPage(pageResult([inactive], 2, 45)); await settle()
    expect(button('Próxima')).toBe(next)
    expect(document.activeElement).toBe(next)
    expect(next.disabled).toBe(false)
    expect(button('Anterior').disabled).toBe(false)
  })

  it('invalidates a pending response as soon as search changes, before debounce', async () => {
    let finishOld!: (value: unknown) => void
    api.getPage.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await mount()
    const search = container.querySelector('input')!
    search.value = 'novo'; search.dispatchEvent(new Event('input')); await nextTick()
    finishOld(pageResult([{ ...active, nome: 'Resposta antiga' }])); await settle()
    expect(container.textContent).not.toContain('Resposta antiga')
    expect(container.querySelector('[role="status"]')).not.toBeNull()
    expect(container.querySelector('.total-count')).toBeNull()
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, search: 'novo' }))
    expect(container.textContent).toContain(active.nome)
  })

  it('retries the failed page and keeps errors distinct from empty results', async () => {
    api.getPage.mockImplementation(async ({ page }) => pageResult([active], page, 25))
    await mount()
    api.getPage.mockRejectedValueOnce(new Error('offline'))
    button('Próxima').click(); await settle()
    expect(container.querySelector('[role="alert"]')).not.toBeNull()
    expect(container.querySelector('.total-count')).toBeNull()
    expect(container.textContent).not.toContain('Nenhum cliente encontrado')
    button('Tentar novamente').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
    expect(container.querySelector('.customer-pagination')?.textContent).toContain('Página 2 de 2')
    expect(button('Próxima').disabled).toBe(true)
  })

  it('returns to the last existing page after inactivating its final customer', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.getPage.mockImplementation(async ({ page }) => pageResult([active], page, 21))
    await mount()
    button('Próxima').click(); await settle()
    api.getPage.mockResolvedValueOnce(pageResult([], 2, 20)).mockResolvedValueOnce(pageResult([active], 1, 20))
    container.querySelector<HTMLButtonElement>('[title="Inativar"]')!.click(); await settle()
    expect(api.delete).toHaveBeenCalledWith(active.id)
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }))
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.textContent).not.toContain('Nenhum cliente encontrado')
    expect(container.querySelector('.total-count')?.textContent).toBe('20 clientes')
  })
})
