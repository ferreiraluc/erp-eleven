import { afterEach, expect, it } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import StockQuantityInput from './StockQuantityInput.vue'
let app: App | undefined, root: HTMLDivElement
async function mount(value: number, min = 0) {
  root = document.createElement('div'); document.body.append(root)
  const quantity = ref(value)
  app = createApp({ setup: () => () => h(StockQuantityInput, { modelValue: quantity.value, min, max: 8, 'aria-label': 'Quantidade de teste', 'onUpdate:modelValue': (n: number) => quantity.value = n }) })
  app.mount(root); await nextTick(); return quantity
}
afterEach(() => { app?.unmount(); root?.remove() })
it('steps on touch-sized buttons without focusing the input or submitting', async () => {
  const value = await mount(3)
  const [minus, plus] = Array.from(root.querySelectorAll('button'))
  plus!.click(); await nextTick(); expect(value.value).toBe(4)
  minus!.click(); await nextTick(); expect(value.value).toBe(3)
  expect(document.activeElement).not.toBe(root.querySelector('input'))
  expect(plus!.type).toBe('button')
  expect(root.querySelector('input')!.getAttribute('aria-label')).toBe('Quantidade de teste')
})
it('respects zero and supports signed stock adjustments', async () => {
  const quantity = await mount(0)
  expect(root.querySelector('button')!.disabled).toBe(true)
  app!.unmount(); root.remove(); const delta = await mount(0, -10)
  root.querySelector('button')!.click(); await nextTick(); expect(delta.value).toBe(-1)
  expect(quantity.value).toBe(0)
})
