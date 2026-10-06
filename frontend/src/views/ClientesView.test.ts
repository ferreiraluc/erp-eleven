import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import ClientesView from './ClientesView.vue'

const api = vi.hoisted(() => ({ getAll: vi.fn() }))
vi.mock('@/services/api', () => ({ clientesAPI: api }))
vi.mock('@/components/clientes/ClienteFormModal.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/logistics/CustomerLogisticsPanel.vue', () => ({ default: { render: () => null } }))
const active = { id: 'active', nome: 'Cliente ativo QA', ativo: true }
const inactive = { id: 'inactive', nome: 'Cliente inativo QA', ativo: false }
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
  i18n.global.locale.value = 'pt'
  container = document.createElement('div'); document.body.append(container)
  api.getAll.mockImplementation(async ({ ativo, include_inactive }) => include_inactive ? [active, inactive] : ativo ? [active] : [inactive])
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.resetAllMocks() })

describe('Customer status filters', () => {
  it('queries active, inactive and all customers explicitly and shows their respective records', async () => {
    await mount()
    expect(api.getAll).toHaveBeenLastCalledWith({ search: undefined, ativo: true, include_inactive: false, limit: 200 })
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(1)
    button('Inativos').click(); await settle()
    expect(api.getAll).toHaveBeenLastCalledWith({ search: undefined, ativo: false, include_inactive: false, limit: 200 })
    expect(container.querySelector('.cliente-name')?.textContent || container.textContent).toContain(inactive.nome)
    expect(container.querySelector('.cliente-card.inactive')).not.toBeNull()
    button('Todos').click(); await settle()
    expect(api.getAll).toHaveBeenLastCalledWith({ search: undefined, ativo: true, include_inactive: true, limit: 200 })
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(2)
    expect(button('Todos').getAttribute('aria-pressed')).toBe('true')
  })

  it('does not let an older active-only response replace the currently selected all filter', async () => {
    let finishOld!: (value: unknown) => void
    api.getAll.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await mount(); button('Todos').click(); await settle()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(2)
    finishOld([active]); await settle()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(2)
    expect(button('Todos').getAttribute('aria-pressed')).toBe('true')
  })

  it('shows a recoverable error instead of claiming there are no customers', async () => {
    api.getAll.mockRejectedValueOnce(new Error('offline'))
    await mount()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os clientes.')
    expect(container.textContent).not.toContain('Nenhum cliente encontrado')
    button('Tentar novamente').click(); await settle()
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelectorAll('.cliente-wrap')).toHaveLength(1)
  })
})
