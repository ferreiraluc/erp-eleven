import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryRelatedProducts from './InventoryRelatedProducts.vue'
const mocks = vi.hoisted(() => ({ getRelated: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: mocks }))
vi.mock('./ProductThumbnail.vue', () => ({ default: { template: '<img />' } }))
let app: App, root: HTMLElement
const flush = async () => {
  await nextTick()
  await nextTick()
  await nextTick()
}
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.resetAllMocks()
})
const item = (id: string, color = 'Black') => ({
  id,
  name: `Produto ${id}`,
  color,
  inventory_code: `INV-${id}`,
  current_stock: 1,
  is_active: true,
})
async function mount() {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(InventoryRelatedProducts, { source: item('source', 'Preto') }).use(
    createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }),
  )
  app.mount(root)
  await flush()
}
it('keeps suggestions separate, deduplicates pages and opens the chosen product', async () => {
  mocks.getRelated.mockResolvedValueOnce({
    items: [{ item: item('one'), relation: 'family' }],
    next_cursor: { after_rank: 0, after_id: 'one' },
  })
  await mount()
  expect(root.textContent).toContain('Mesma cor')
  expect(mocks.getRelated).toHaveBeenCalledTimes(1)
  mocks.getRelated.mockResolvedValueOnce({
    items: [
      { item: item('one'), relation: 'family' },
      { item: item('two'), relation: 'brand' },
    ],
    next_cursor: null,
  })
  root.querySelector<HTMLButtonElement>('.erp-button')!.click()
  await flush()
  expect(root.querySelectorAll('.related-card')).toHaveLength(2)
  expect(root.querySelector('.erp-button')).toBeNull()
})
it('does not retry automatically and aborts pending suggestions when the query changes', async () => {
  mocks.getRelated.mockRejectedValueOnce(new Error('offline'))
  await mount()
  expect(root.querySelector('[role=alert]')).not.toBeNull()
  expect(mocks.getRelated).toHaveBeenCalledTimes(1)
  const signal = mocks.getRelated.mock.calls[0][2] as AbortSignal
  app.unmount()
  expect(signal.aborted).toBe(true)
})
