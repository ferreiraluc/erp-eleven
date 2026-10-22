import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App, type Component } from 'vue'
import { createI18n } from 'vue-i18n'
import InventorySummaryStats from './InventorySummaryStats.vue'
import InventoryGroupingSuggestions from './InventoryGroupingSuggestions.vue'

let app: App | undefined, container: HTMLDivElement
async function mount(component: Component, props: Record<string, unknown>) {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(defineComponent({ setup: () => () => h(component, props) })).use(i18n)
  app.mount(container); await nextTick()
}
afterEach(() => { app?.unmount(); app = undefined; container?.remove() })

describe('Inventory summary controls', () => {
  it('shows stock totals without duplicate status buttons and keeps the ungrouped filter', async () => {
    const toggle = vi.fn()
    await mount(InventorySummaryStats, { summary: { total_active_items: 20, grouped_items_count: 12, group_count: 3, low_stock_count: 2, out_of_stock_count: 1, overstocked_count: 0, inactive_count: 0, unknown_stock_count: 0, loja_count: 10, deposito_count: 10 }, ungroupedOnly: false, 'onToggle-ungrouped': toggle })
    expect(container.textContent).toContain('8sem grade')
    expect(container.textContent).toContain('2baixo')
    expect(container.querySelector('[aria-label="Filtrar estoque baixo"]')).toBeNull()
    ;(container.querySelector('[aria-label="Filtrar itens sem grade"]') as HTMLButtonElement).click()
    expect(toggle).toHaveBeenCalledOnce()
  })

  it('limits visible suggestions and emits the selected object', async () => {
    const select = vi.fn()
    const suggestions = Array.from({ length: 5 }, (_, index) => ({ name: `Grupo ${index + 1}`, items: [{ id: `item-${index}` }] }))
    await mount(InventoryGroupingSuggestions, { suggestions, onSelect: select })
    expect(container.querySelectorAll('button')).toHaveLength(4)
    ;(container.querySelector('button') as HTMLButtonElement).click()
    expect(select).toHaveBeenCalledWith(suggestions[0])
  })
})
