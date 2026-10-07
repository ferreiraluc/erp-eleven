import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import SalesEntriesPanel from './SalesEntriesPanel.vue'
import { salesEntries, type EntriesResult } from '@/services/salesEntries'

vi.mock('@/services/salesEntries', () => ({ salesEntries: { list: vi.fn() } }))
const mounted: { app: App; node: HTMLElement }[] = []
function fixture(): EntriesResult {
  const currencies = [{ currency: 'BRL', count: 2, gross: 4500, net: 4400, net_available: 2 }]
  return {
    items: [{ id: 'entry', source_id: 'sheet', filename: 'Fixture.xlsx', sheet: 'Planilha1', row: 12, source_cell: 'Planilha1!C12',
      year: 2026, month: 9, week_index: null, week_label: null, seller: 'Lucas', currency: 'BRL', gross: 4500, net: 4400,
      payment_method: null, payment_type: 'dinheiro', customer: null, date: '2026-09-23', time: null, day_group: null, synced_at: null, stale: false }],
    total: 52, offset: 0, limit: 50, sellers: ['Lucas'], currencies: ['BRL'], dates: ['2026-09-23'],
    payment_methods: [{ value: 'maquina', label: 'Máquina' }, { value: 'dinheiro', label: 'Dinheiro' }, { value: 'pix banco a', label: 'Pix Banco A' }],
    weeks: [{ start: '2026-09-21', end: '2026-09-27', settlement_date: '2026-09-28' }],
    payments: [{ payment_type: 'maquina', label: 'Máquina', count: 2, currencies }, { payment_type: 'dinheiro', label: 'Dinheiro', count: 1, currencies }],
    summary: { count: 52, currencies, dated_count: 2, timed_count: 0, undated_count: 50, official_total_usd: 999 },
    daily: [{ date: '2026-09-23', count: 2, currencies }], hourly: [], weekdays: [], reconciliation: [],
    coverage: { source_count: 1, needs_sync: false, sources_without_entries: 0, skipped_rows: 0, undated_excluded: 0 },
    access: { scope: 'all', seller: null },
  }
}
async function mount() {
  vi.mocked(salesEntries.list).mockResolvedValue(fixture())
  const props = reactive({ year: 2026, month: 9, seller: 'Lucas' })
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  const node = document.createElement('div'); document.body.append(node)
  const app = createApp({ render: () => h(SalesEntriesPanel, props) }); app.use(i18n); app.mount(node)
  mounted.push({ app, node })
  await vi.waitFor(() => expect(node.textContent).toContain('Recebimentos por tipo'))
  return { node, props, i18n }
}
async function change(input: HTMLInputElement | HTMLSelectElement, value: string) {
  input.value = value; input.dispatchEvent(new Event(input instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
  if (input instanceof HTMLInputElement) input.dispatchEvent(new Event('change', { bubbles: true }))
  await nextTick()
  await vi.waitFor(() => expect(document.querySelector('[aria-busy="true"]')).toBeNull())
}
function button(node: HTMLElement, text: string) { return Array.from(node.querySelectorAll('button')).find(b => b.textContent?.trim() === text)! }
afterEach(() => { for (const { app, node } of mounted.splice(0)) { app.unmount(); node.remove() } vi.clearAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('payment filters and receipt summaries', () => {
  it('sends seller, currency, method and inclusive dates, resetting pagination', async () => {
    const { node } = await mount()
    button(node, 'Próxima').click(); await nextTick()
    await vi.waitFor(() => expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50 })))
    const selects = node.querySelectorAll('select'), dates = node.querySelectorAll<HTMLInputElement>('input[type=date]')
    await change(selects[0]!, 'BRL'); await change(selects[1]!, 'maquina')
    await change(dates[0]!, '2026-09-01'); await change(dates[1]!, '2026-09-30')
    expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ year: 2026, month: 9, seller: 'Lucas', currency: 'BRL', payment_method: 'maquina', date_from: '2026-09-01', date_to: '2026-09-30', offset: 0 }))
    expect(node.querySelector('.payment-card')?.getAttribute('aria-pressed')).toBe('true')
    button(node, 'Limpar').click(); await nextTick()
    expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ payment_method: undefined, date_from: undefined, date_to: undefined, currency: undefined, offset: 0 }))
  })

  it('labels empty source payments as cash and translates known types while preserving custom labels', async () => {
    const { node, i18n } = await mount()
    expect(node.querySelector('tbody tr td:nth-child(4)')?.textContent).toBe('Dinheiro')
    expect(node.textContent).toContain('Pix Banco A')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(node.querySelector('tbody tr td:nth-child(4)')?.textContent).toBe('Efectivo')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(node.querySelector('tbody tr td:nth-child(4)')?.textContent).toBe('Cash')
    expect(node.textContent).toContain('Card terminal')
  })

  it('rejects reversed dates locally and explains excluded undated rows', async () => {
    const { node } = await mount()
    vi.mocked(salesEntries.list).mockResolvedValue({ ...fixture(), coverage: { ...fixture().coverage, undated_excluded: 7 } })
    const dates = node.querySelectorAll<HTMLInputElement>('input[type=date]')
    await change(dates[0]!, '2026-09-30')
    await vi.waitFor(() => expect(node.textContent).toContain('7 lançamentos do período'))
    const calls = vi.mocked(salesEntries.list).mock.calls.length
    await change(dates[1]!, '2026-09-01')
    expect(salesEntries.list).toHaveBeenCalledTimes(calls)
    expect(node.querySelector('[role=alert]')?.textContent).toContain('data inicial')
    expect(node.querySelector('.currency-summary')).toBeNull()
  })

  it('keeps the date range when selecting another seller, resets it for a different workbook period', async () => {
    const { node, props } = await mount()
    const dates = node.querySelectorAll<HTMLInputElement>('input[type=date]')
    await change(dates[0]!, '2026-09-01'); await change(dates[1]!, '2026-09-30')
    props.seller = 'Junior'; await nextTick()
    expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ seller: 'Junior', date_from: '2026-09-01', date_to: '2026-09-30' }))
    props.month = 10; await nextTick()
    expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ month: 10, date_from: undefined, date_to: undefined }))
  })

  it('opens one recorded day as a range with matching endpoints', async () => {
    const { node } = await mount()
    node.querySelector<HTMLButtonElement>('.daily-list button')!.click(); await nextTick()
    expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ date_from: '2026-09-23', date_to: '2026-09-23' }))
  })

  it('selects Monday to Sunday and highlights the saved net for machine settlement', async () => {
    const { node } = await mount()
    const selects = node.querySelectorAll('select')
    await change(selects[1]!, 'maquina')
    await change(selects[2]!, '2026-09-21')
    expect(salesEntries.list).toHaveBeenLastCalledWith(expect.objectContaining({ payment_method: 'maquina', date_from: '2026-09-21', date_to: '2026-09-27', offset: 0 }))
    expect(node.querySelector('.settlement-summary')?.textContent).toContain('28/09/2026')
    expect(node.querySelector('.currency-summary strong')?.textContent).toContain('4.400,00')
    expect(node.querySelector('.currency-summary')?.textContent).toContain('4.500,00')
    await change(node.querySelector<HTMLInputElement>('input[type=date]')!, '2026-09-22')
    expect(selects[2]!.value).toBe('')
    expect(node.querySelector('.settlement-summary')).toBeNull()
    expect(node.querySelector('.currency-summary strong')?.textContent).toContain('4.500,00')
  })

  it('explains inferred dates, partial periods and the source of relevant incomplete rows', async () => {
    const { node } = await mount()
    const data = fixture()
    data.items[0] = { ...data.items[0]!, date_source: 'week_day' }
    data.coverage = { ...data.coverage, inferred_dates: 1, period_excluded: 2, skipped_rows: 1,
      issues: [{ filename: 'Fixture.xlsx', sheet: 'semana2', skipped_rows: 1 }] }
    vi.mocked(salesEntries.list).mockResolvedValue(data)
    button(node, 'Recarregar').click()
    await vi.waitFor(() => expect(node.textContent).toContain('Data pelo calendário semanal'))
    expect(node.textContent).toContain('2 lançamentos têm apenas um período')
    expect(node.querySelector('details.notice')?.textContent).toContain('Fixture.xlsx · semana2')
    expect(node.querySelector('.notice.info')?.textContent).toContain('semana1, semana2')
  })

  it('exports blank payment cells as cash and only exports the authorized page', async () => {
    const { node } = await mount()
    const createObjectURL = vi.fn((_blob: Blob) => 'blob:fixture')
    vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    vi.useFakeTimers()
    button(node, 'Exportar página').click()
    vi.runAllTimers(); vi.useRealTimers()
    const blob = createObjectURL.mock.calls[0]![0]
    const csv = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob) })
    expect(csv).toContain('"Dinheiro"')
    expect(csv).toContain('"4500"')
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).not.toContain('Junior')
  })
})
