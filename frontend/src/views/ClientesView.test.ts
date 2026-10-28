import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import ClientesView from './ClientesView.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({ getPage: vi.fn(), delete: vi.fn() }))
const history = vi.hoisted(() => ({ mount: vi.fn() }))
vi.mock('@/services/api', () => ({ clientesAPI: api }))
vi.mock('@/components/clientes/ClienteFormModal.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/logistics/CustomerLogisticsPanel.vue', async () => {
  const { h } = await import('vue')
  return { default: { emits: ['changed'], mounted: history.mount, render() { return h('button', { class: 'history-refresh', onClick: () => (this as unknown as { $emit: (event: string) => void }).$emit('changed') }, 'Atualizar resumo QA') } } }
})
const activity = { purchase_count: 4, shipment_count: 2, print_count: 3, order_count: 1, submitted_print_count: 1, pending_print_count: 1, uncertain_print_count: 1, own_sales_only: true, last_purchase_at: '2026-10-27T15:30:00Z', last_print_at: '2026-10-27T16:00:00Z' }
const active = { id: 'active', nome: 'Cliente ativo QA', ativo: true, activity }
const inactive = { id: 'inactive', nome: 'Cliente inativo QA', ativo: false, activity: { ...activity, purchase_count: 0 } }
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
    expect(api.getPage).toHaveBeenLastCalledWith({ search: undefined, ativo: true, include_inactive: false, sort: 'nome', page: 1, page_size: 20 })
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(1)
    button('Inativos').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith({ search: undefined, ativo: false, include_inactive: false, sort: 'nome', page: 1, page_size: 20 })
    expect(container.querySelector('.cliente-name')?.textContent || container.textContent).toContain(inactive.nome)
    expect(container.querySelector('.cliente-card.inactive')).not.toBeNull()
    button('Todos').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith({ search: undefined, ativo: true, include_inactive: true, sort: 'nome', page: 1, page_size: 20 })
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
    container.querySelector<HTMLButtonElement>('.customer-expand')!.click(); await settle()
    container.querySelector<HTMLButtonElement>('[title="Inativar"]')!.click(); await settle()
    expect(api.delete).toHaveBeenCalledWith(active.id)
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 }))
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.textContent).not.toContain('Nenhum cliente encontrado')
    expect(container.querySelector('.total-count')?.textContent).toBe('20 clientes')
  })

  it('loads activity with one directory request and mounts details only for the expanded customer', async () => {
    api.getPage.mockResolvedValue(pageResult([active, { ...active, id: 'second', nome: 'Outro cliente' }]))
    await mount()
    expect(api.getPage).toHaveBeenCalledTimes(1)
    expect(history.mount).not.toHaveBeenCalled()
    expect(container.querySelectorAll('.customer-movements')).toHaveLength(2)
    expect(Array.from(container.querySelectorAll('.customer-movements:first-child .movement strong')).slice(0, 3).map(item => item.textContent)).toEqual(['4', '2', '3'])
    expect(container.textContent).toContain('1 na fila')
    expect(container.textContent).toContain('1 para conferir')
    const expand = container.querySelector<HTMLButtonElement>('.customer-expand')!
    expect(expand.getAttribute('aria-expanded')).toBe('false')
    expand.click(); await settle()
    expect(history.mount).toHaveBeenCalledTimes(1)
    expect(expand.getAttribute('aria-expanded')).toBe('true')
    expect(container.querySelectorAll('.historico-section')).toHaveLength(1)
    expect(container.querySelector('section')?.id).toBe(expand.getAttribute('aria-controls'))
    container.querySelectorAll<HTMLButtonElement>('.customer-expand')[1].click(); await settle()
    expect(history.mount).toHaveBeenCalledTimes(2)
    expect(container.querySelectorAll('.historico-section')).toHaveLength(1)
    expect(expand.getAttribute('aria-expanded')).toBe('false')
    expect(api.getPage).toHaveBeenCalledTimes(1)
  })

  it('orders the full directory on the server, resets pagination and uses the standard dropdown', async () => {
    api.getPage.mockImplementation(async ({ page }) => pageResult([active], page, 225))
    await mount(); button('Próxima').click(); await settle()
    container.querySelector<HTMLButtonElement>('[aria-label="Organizar clientes"]')!.click(); await settle()
    const option = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="option"]')).find(row => row.textContent?.trim() === 'Últimas compras')!
    option.click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, sort: 'ultima_compra' }))
    expect(container.querySelector('.customer-pagination')?.textContent).toContain('Página 1 de 12')
    container.querySelector<HTMLButtonElement>('[aria-label="Organizar clientes"]')!.click(); await settle()
    Array.from(document.querySelectorAll<HTMLButtonElement>('[role="option"]')).find(row => row.textContent?.trim() === 'Últimas impressões')!.click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, sort: 'ultima_impressao' }))
  })

  it('refreshes the summary after a changed association without unmounting its open history', async () => {
    await mount()
    container.querySelector<HTMLButtonElement>('.customer-expand')!.click(); await settle()
    const refresh = container.querySelector<HTMLButtonElement>('.history-refresh')!
    api.getPage.mockResolvedValueOnce(pageResult([{ ...active, activity: { ...activity, shipment_count: 7 } }]))
    refresh.click(); await settle()
    expect(history.mount).toHaveBeenCalledTimes(1)
    expect(container.querySelector('.history-refresh')).toBe(refresh)
    expect(container.querySelectorAll('.movement strong')[1].textContent).toBe('7')
    expect(container.querySelector('.customer-expand')?.getAttribute('aria-expanded')).toBe('true')
  })


  it('clears the former account and rejects its late directory response after a new login', async () => {
    let finishOld!: (value: unknown) => void
    api.getPage.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await mount()
    const auth = useAuthStore()
    auth.token = 'new-account-session'; await settle()
    expect(container.textContent).toContain(active.nome)
    finishOld(pageResult([{ ...active, nome: 'Cliente da conta anterior' }])); await settle()
    expect(container.textContent).not.toContain('Cliente da conta anterior')
    auth.token = null; await settle()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(0)
  })

})
