import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import RastreamentoView from './RastreamentoView.vue'
import type { Rastreamento, RastreamentoResumo } from '@/stores/rastreamento'
import { chooseDropdown } from '@/test/dropdown'

const api = vi.hoisted(() => ({ list: vi.fn(), summary: vi.fn(), consultAndSave: vi.fn() }))
const store = reactive({
  rastreamentosAtivos: [] as Rastreamento[],
  resumoDashboard: null as RastreamentoResumo | null,
  listarRastreamentos: api.list,
  obterResumoDashboard: api.summary,
  consultarESalvarRastreamento: api.consultAndSave,
  formatarData: (value: string) => value,
})
vi.mock('@/stores/rastreamento', () => ({ useRastreamentoStore: () => store }))
vi.mock('@/services/api', () => ({ pedidosAPI: { getAll: vi.fn(async () => []) } }))

let app: App | undefined, container: HTMLDivElement
const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await nextTick() }
const shipment: Rastreamento = {
  id: 'shipment-qa', codigo_rastreio: 'QA123456789BR', status: 'EM_TRANSITO',
  destinatario: 'Cliente QA', historico_eventos: [], ativo: true,
  data_criacao: '2026-11-01T12:00:00Z', created_at: '2026-11-01T12:00:00Z', updated_at: '2026-11-01T12:00:00Z',
}
const summary: RastreamentoResumo = { total_rastreamentos: 1, em_transito: 1, entregues: 0, pendentes: 0, com_erro: 0, rastreamentos_recentes: [shipment] }
const button = (label: string) => Array.from(container.querySelectorAll('button')).find(el => el.textContent?.trim() === label)!
async function mount(path = '/') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] })
  await router.push(path); await router.isReady()
  app = createApp(RastreamentoView).use(router).use(i18n)
  app.config.globalProperties.$tr = uiText
  app.mount(container); await settle()
  return router
}
beforeEach(() => {
  i18n.global.locale.value = 'pt'
  container = document.createElement('div'); document.body.append(container)
  store.rastreamentosAtivos = []; store.resumoDashboard = null
  api.list.mockImplementation(async () => { store.rastreamentosAtivos = [shipment]; return [shipment] })
  api.summary.mockImplementation(async () => { store.resumoDashboard = summary; return summary })
  api.consultAndSave.mockResolvedValue(undefined)
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.resetAllMocks() })

describe('Tracking loading and empty states', () => {
  it('hides stale rows and counters on failure, and restores confirmed data on retry', async () => {
    store.rastreamentosAtivos = [{ ...shipment, destinatario: 'Nome antigo QA' }]
    store.resumoDashboard = { ...summary, total_rastreamentos: 999 }
    api.list.mockRejectedValueOnce(new Error('offline'))
    await mount()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os rastreamentos.')
    expect(container.querySelector('.stats-section')).toBeNull()
    expect(container.querySelector('.rastreamentos-section')).toBeNull()
    expect(container.textContent).not.toContain('Nome antigo QA')
    expect(container.textContent).not.toContain('Nenhum rastreamento encontrado')
    button('Tentar novamente').click(); await settle()
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('.stats-section')).not.toBeNull()
    expect(container.querySelector('.rastreamentos-section')?.textContent).toContain('Cliente QA')
  })

  it('keeps a successful list visible when only its summary fails', async () => {
    store.resumoDashboard = { ...summary, total_rastreamentos: 999 }
    api.summary.mockRejectedValueOnce(new Error('summary offline'))
    await mount()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar o resumo dos rastreamentos.')
    expect(container.querySelector('.stats-section')).toBeNull()
    expect(container.querySelector('.rastreamentos-section')?.textContent).toContain('Cliente QA')
    button('Tentar novamente').click(); await settle()
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('.stats-section')).not.toBeNull()
  })

  it('clears search and status without querying the carrier or offering a duplicate creation', async () => {
    const router = await mount('/?search=Outro&keep=1')
    await chooseDropdown(container.querySelector('.filter-select'), 'ENTREGUE')
    expect(container.querySelector('.empty-state')?.textContent).toContain('Nenhum rastreamento corresponde aos filtros aplicados.')
    expect(container.querySelector('.empty-state')?.textContent).not.toContain('Adicionar Rastreamento')
    button('Limpar Filtros').click(); await settle()
    expect(container.querySelector<HTMLInputElement>('input[type="search"]')?.value).toBe('')
    expect(container.querySelector('.rastreamentos-section')?.textContent).toContain('Cliente QA')
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ keep: '1' }))
    expect(api.list).toHaveBeenCalledOnce()
  })

  it('finishes both initial reads before exposing retry after one failure', async () => {
    let resolveSummary!: (value: RastreamentoResumo) => void
    api.list.mockRejectedValueOnce(new Error('offline'))
    api.summary.mockImplementationOnce(() => new Promise(resolve => { resolveSummary = resolve }))
    await mount()
    expect(container.querySelector('[role="status"]')?.textContent).toContain('Carregando rastreamentos...')
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('.stats-section')).toBeNull()
    resolveSummary(summary); await settle()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os rastreamentos.')
  })

  it('keeps the newer reload failure visible when the initial read resolves after saving', async () => {
    let resolveList!: (value: Rastreamento[]) => void
    let resolveSummary!: (value: RastreamentoResumo) => void
    api.list.mockImplementationOnce(() => new Promise(resolve => { resolveList = resolve }))
      .mockRejectedValueOnce(new Error('new reload offline'))
    api.summary.mockImplementationOnce(() => new Promise(resolve => { resolveSummary = resolve }))
      .mockRejectedValueOnce(new Error('new summary offline'))
    await mount()
    container.querySelector<HTMLButtonElement>('[aria-label="Adicionar Rastreamento"]')!.click(); await settle()
    const code = container.querySelector<HTMLInputElement>('#codigo')!
    code.value = shipment.codigo_rastreio; code.dispatchEvent(new Event('input', { bubbles: true })); await settle()
    button('Consultar e Salvar').click(); await settle()
    expect(api.list).toHaveBeenCalledTimes(2)
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os rastreamentos.')
    resolveList([shipment]); resolveSummary(summary); await settle()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar os rastreamentos.')
    expect(container.querySelector('.stats-section')).toBeNull()
    expect(container.querySelector('.rastreamentos-section')).toBeNull()
    expect(container.querySelector('.empty-state')).toBeNull()
  })
})
