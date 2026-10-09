import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import messages from './salesBi.messages.json'
import entryMessages from './salesEntries.messages.json'
import SalesBiView from '@/views/SalesBiView.vue'
import SalesSummaryCard from '@/components/dashboard/SalesSummaryCard.vue'

const state = vi.hoisted(() => ({ ownSales: true, user: { role: 'GERENTE', sales_seller: 'Junior' } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => state }))
vi.mock('vue-chartjs', async () => {
  const { h } = await import('vue')
  const chart = { props: ['data'], setup: (props: { data: { labels: string[] } }) => () => h('div', { class: 'chart-labels' }, props.data.labels.join(' ')) }
  return { Line: chart, Bar: chart }
})
vi.mock('@/services/salesBi', () => ({
  salesBi: {
    overview: vi.fn(async () => ({
      access: { scope: state.ownSales ? 'own' : 'all', seller: state.ownSales ? 'Junior' : null },
      years: [2026], sellers: state.ownSales ? ['Junior'] : ['Junior', 'Lucas'], latest: { year: 2026, month: 9 },
      selected: { total_usd: 100, available_months: 1, source_months: 1, partial: false },
      months: [{ year: 2026, month: 9, total_usd: 100, source_id: 'source', filename: 'Setembro.xlsx', source_cell: 'Planilha1!D8', synced_at: '2026-09-30T18:00:00Z', stale: false, warnings: [], partial: false }],
      annual: [{ year: 2026, total_usd: 100, available_months: 1, source_months: 1, partial: false }],
      ranking: [{ name: 'Junior', total_usd: 100, available_months: 1, source_months: 1 }],
      weeks: [{ year: 2026, month: 9, index: 1, label: 'Semana 1', total_usd: 100, partial: false }],
      currencies: [{ currency: 'USD', value: 100, available_months: 1, source_months: 1 }],
      comparison_month: 9, comparison: [], coverage: { months: 1, files: 1, warnings: 0 },
    })),
    status: vi.fn(async () => ({ configured: true, enabled: true, running: false, finished_at: '2026-09-30T18:00:00Z', error: null, sources: [] })),
    sync: vi.fn(), config: vi.fn(), save: vi.fn(),
  },
}))

const mounted: { app: App; node: HTMLElement }[] = []
async function mount(component: typeof SalesBiView | typeof SalesSummaryCard, locale = 'pt') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/bi-vendas', component: { render: () => null } }, { path: '/dashboard', component: { render: () => null } }] })
  await router.push('/bi-vendas')
  const i18n = createI18n({ legacy: false, locale, fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  const node = document.createElement('div'); document.body.append(node)
  const app = createApp({ render: () => h(component) }); app.use(i18n); app.use(router); app.mount(node)
  mounted.push({ app, node })
  await vi.waitFor(() => expect(node.textContent).toContain('Junior'))
  return { node, i18n }
}
afterEach(() => { for (const { app, node } of mounted.splice(0)) { app.unmount(); node.remove() } state.ownSales = true })

function flatten(record: object, prefix = ''): Record<string, string> {
  return Object.fromEntries(Object.entries(record).flatMap(([key, value]) => typeof value === 'string' ? [[prefix + key, value]] : Object.entries(flatten(value, prefix + key + '.'))))
}
describe('BI translations and personal sales rendering', () => {
  it('keeps all locale keys and interpolation parameters aligned', () => {
    for (const catalog of [messages, entryMessages]) {
      const pt = flatten(catalog.pt)
      for (const locale of ['es', 'en'] as const) {
        const other = flatten(catalog[locale])
        expect(Object.keys(other).sort()).toEqual(Object.keys(pt).sort())
        for (const [key, value] of Object.entries(pt)) {
          expect(other[key], key).not.toBe('')
          expect(other[key].match(/\{\w+\}/g)?.sort() || [], key).toEqual(value.match(/\{\w+\}/g)?.sort() || [])
        }
      }
    }
  })

  it('changes page labels and calendar/chart months when the language changes', async () => {
    const { node, i18n } = await mount(SalesBiView)
    expect(node.querySelector('h1')?.textContent).toBe('Minhas vendas')
    expect(node.querySelector('.chart-labels')?.textContent).toContain('Set')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(node.querySelector('h1')?.textContent).toBe('Mis ventas')
    expect(node.textContent).toContain('Ventas mes a mes')
    expect(node.textContent).not.toContain('Vendas mês a mês')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(node.querySelector('h1')?.textContent).toBe('My sales')
    expect(node.querySelector('.chart-labels')?.textContent).toContain('Sep')
    expect(node.textContent).toContain('Monthly sales')
  })

  it('never presents the only authorized seller as the global number one', async () => {
    const { node } = await mount(SalesBiView, 'en')
    const metrics = node.querySelector('.metrics') as HTMLElement
    expect(metrics.classList.contains('own-sales')).toBe(true)
    expect(metrics.getAttribute('style')).toBeNull()
    expect(node.querySelector('.ranking-panel h2')?.textContent).toBe('Your results')
    expect(node.querySelector('.ranking-panel .rank-index')).toBeNull()
    expect(node.querySelector('.tabs')?.textContent).not.toContain('Sources')
    expect(node.textContent).not.toContain('Seller ranking')
    expect(node.querySelector('select[disabled]')?.textContent).toBe('Junior')
  })

  it('keeps full-store labels and source navigation for unrestricted accounts', async () => {
    state.ownSales = false
    const { node } = await mount(SalesBiView, 'es')
    expect(node.querySelector('h1')?.textContent).toBe('Análisis de ventas')
    expect(node.querySelector('.tabs')?.textContent).toContain('Fuentes')
    expect(node.textContent).toContain('Clasificación de vendedores')
  })

  it('translates the dashboard card and omits the seller position for personal access', async () => {
    const { node, i18n } = await mount(SalesSummaryCard, 'es')
    expect(node.querySelector('h3')?.textContent).toBe('Mis ventas')
    expect(node.querySelector('.seller-position')).toBeNull()
    expect(node.textContent).toContain('Tu resultado')
    expect(node.textContent).not.toContain('Ver clasificación')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(node.querySelector('h3')?.textContent).toBe('My sales')
    expect(node.textContent).toContain('Open analysis')
    expect(node.textContent).toContain('September 2026')
  })
})
