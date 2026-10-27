import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import QualityPanel from './QualityPanel.vue'
import type { QualityConfig, QualityOverview, QualityRunDetail } from '@/services/systemQuality'
const mocks = vi.hoisted(() => ({
  auth: {} as {
    isOwner: boolean
    isAuthenticated: boolean
    token: string | null
  },
  overview: vi.fn(),
  detail: vi.fn(),
  configure: vi.fn(),
  scan: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/services/systemQuality', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/systemQuality')>()),
  systemQualityAPI: {
    overview: mocks.overview,
    detail: mocks.detail,
    configure: mocks.configure,
    scan: mocks.scan,
  },
}))
const runId = '00000000-0000-4000-8000-000000000001'
const config: QualityConfig = {
  enabled: true,
  ai_enabled: true,
  local_time: '08:30',
  timezone: 'America/Sao_Paulo',
  first_run_on: '2026-10-27',
  version: 2,
  updated_at: null,
  ai_reserved_on: null,
}
const detail = (): QualityRunDetail => ({
  id: runId,
  run_day: '2026-10-26',
  kind: 'daily',
  status: 'partial',
  created_at: '2026-10-26T11:30:00Z',
  started_at: '2026-10-26T11:30:00Z',
  finished_at: '2026-10-26T11:30:10Z',
  attempts: 1,
  ai_attempted: true,
  ai_status: 'completed',
  provider_calls: 1,
  input_tokens: 100,
  output_tokens: 50,
  request_id: null,
  requested_by: null,
  summary: 'Foram encontradas pendências nos dados conferidos.',
  ai_summary: 'Confira os avulsos antes das demais pendências.',
  provider: 'deepseek',
  error_category: null,
  counters: { sale_avulso_without_reason: 2 },
  coverage: {
    inventory: { checked: 500, complete: false, window: 'last_24_hours' },
    customers: {
      checked: 20,
      complete: true,
      comparison: 'changed_cohort_only',
    },
  },
  findings: [
    {
      key: 'sale_avulso_without_reason',
      entity_type: 'pdv_sale',
      entity_id: runId,
      severity: 'warning',
    },
  ],
  findings_total: 1,
  findings_offset: 0,
  findings_limit: 30,
})
const overview = (): QualityOverview => ({
  config: { ...config },
  latest: detail(),
  runs: [detail()],
  total: 1,
  offset: 0,
  limit: 10,
  limits: { manual_scans_per_day: 3, max_provider_calls_per_day: 2 },
})
let app: App | undefined, root: HTMLElement
beforeEach(() => {
  vi.resetAllMocks()
  mocks.auth = reactive({
    isOwner: true,
    isAuthenticated: true,
    token: 'owner-token',
  })
  mocks.overview.mockResolvedValue(overview())
  mocks.detail.mockResolvedValue(detail())
  mocks.configure.mockImplementation(async (value) => ({
    ...config,
    ...value,
    version: 3,
  }))
  mocks.scan.mockResolvedValue({
    ...detail(),
    status: 'queued',
    finished_at: null,
  })
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: 'visible',
  })
  Object.defineProperty(navigator, 'onLine', {
    configurable: true,
    value: true,
  })
})
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
  vi.useRealTimers()
})
async function mount(props: Record<string, unknown> = {}) {
  root = document.createElement('div')
  document.body.append(root)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/vendas-pdv', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  app = createApp(QualityPanel, props).use(router)
  app.mount(root)
  await nextTick()
}
async function open() {
  const disclosure = root.querySelector('details')!
  disclosure.open = true
  disclosure.dispatchEvent(new Event('toggle'))
  await vi.waitFor(() => expect(mocks.overview).toHaveBeenCalled())
  await nextTick()
}
function button(text: string) {
  const value = Array.from(root.querySelectorAll('button')).find((node) =>
    node.textContent?.includes(text),
  )
  expect(value).toBeTruthy()
  return value!
}
describe('Daily quality review owner panel', () => {
  it('starts collapsed without querying or starting a scan', async () => {
    await mount()
    expect(root.querySelector('details')?.open).toBe(false)
    expect(mocks.overview).not.toHaveBeenCalled()
    expect(mocks.scan).not.toHaveBeenCalled()
    await open()
    expect(root.textContent).toContain('Cobertura parcial')
    expect(mocks.scan).not.toHaveBeenCalled()
  })
  it('shows bounded coverage, cohort restrictions and separately labelled AI interpretation', async () => {
    await mount()
    await open()
    expect(root.textContent).toContain('verificações incompletas')
    expect(root.textContent).toContain('Comparação limitada aos cadastros recentes ou alterados')
    expect(root.textContent).toContain('Resumo das verificações do sistema')
    expect(root.textContent).toContain('Interpretação com IA')
    expect(root.querySelector('.quality-findings a')?.getAttribute('href')).toBe(
      '/vendas-pdv?sale_id=' + runId,
    )
  })
  it('saves schedule and AI preferences with CAS, without running a diagnostic', async () => {
    await mount()
    await open()
    const input = root.querySelector<HTMLInputElement>('input[type=time]')!
    input.value = '09:15'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(mocks.configure).toHaveBeenCalled())
    expect(mocks.configure).toHaveBeenCalledWith(
      {
        enabled: true,
        ai_enabled: true,
        local_time: '09:15',
        expected_version: 2,
      },
      'owner-token',
    )
    expect(mocks.scan).not.toHaveBeenCalled()
  })
  it('reuses an anonymous scan request ID after an uncertain network result', async () => {
    await mount()
    await open()
    mocks.scan.mockRejectedValueOnce(new Error('timeout'))
    button('Analisar agora').click()
    await vi.waitFor(() => expect(root.textContent).toContain('mesmo pedido será reutilizado'))
    const key = mocks.scan.mock.calls[0][0]
    button('Analisar agora').click()
    await vi.waitFor(() => expect(mocks.scan).toHaveBeenCalledTimes(2))
    expect(mocks.scan.mock.calls[1]).toEqual([key, 'owner-token'])
    expect(key).toMatch(/^[a-f0-9-]{36}$/)
  })
  it('opens a report from an explicit safe reference without scheduling or paid calls', async () => {
    await mount({ runId })
    await vi.waitFor(() => expect(mocks.overview).toHaveBeenCalled())
    expect(root.querySelector('details')?.open).toBe(true)
    expect(mocks.scan).not.toHaveBeenCalled()
    expect(root.textContent).toContain('Foram encontradas pendências')
  })
  it('discards private reports and late responses when the owner logs out', async () => {
    let finish!: (value: unknown) => void
    mocks.overview.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    await mount()
    await open()
    mocks.auth.isOwner = false
    mocks.auth.token = 'other-token'
    finish(overview())
    await Promise.resolve()
    await nextTick()
    expect(root.textContent).toBe('')
    expect(mocks.scan).not.toHaveBeenCalled()
  })
  it('reports a reached manual limit without claiming that a scan was queued', async () => {
    await mount()
    await open()
    mocks.scan.mockRejectedValueOnce({ response: { status: 429 } })
    button('Analisar agora').click()
    await vi.waitFor(() => expect(root.textContent).toContain('limite de revisões manuais do dia'))
    expect(root.textContent).not.toContain('Análise solicitada.')
  })
  it('polls pending reports only while the panel is visible and online', async () => {
    vi.useFakeTimers()
    mocks.overview.mockResolvedValue({
      ...overview(),
      latest: { ...detail(), status: 'running', created_at: new Date().toISOString() },
      runs: [{ ...detail(), status: 'running', created_at: new Date().toISOString() }],
    })
    await mount()
    const disclosure = root.querySelector('details')!
    disclosure.open = true
    disclosure.dispatchEvent(new Event('toggle'))
    await Promise.resolve()
    await nextTick()
    expect(mocks.overview).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'visibilityState', { value: 'hidden' })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(45000)
    expect(mocks.overview).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'visibilityState', { value: 'visible' })
    document.dispatchEvent(new Event('visibilitychange'))
    await Promise.resolve()
    await nextTick()
    expect(mocks.overview).toHaveBeenCalledTimes(2)
  })
})
