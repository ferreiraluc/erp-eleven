import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App, type Component } from 'vue'
import { createI18n } from 'vue-i18n'
import InventorySearchBar from './InventorySearchBar.vue'
import InventoryViewControls from './InventoryViewControls.vue'

let app: App | undefined
let container: HTMLDivElement
async function mount(component: Component, props: Record<string, unknown>) {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(defineComponent({ setup: () => () => h(component, props) })).use(i18n)
  app.mount(container); await nextTick()
}
function button(text: string) {
  const match = Array.from(container.querySelectorAll('button')).find(item => item.textContent?.trim() === text)
  if (!match) throw new Error(`Button missing: ${text}`)
  return match
}
afterEach(() => { app?.unmount(); app = undefined; container?.remove() })

describe('Inventory toolbar controls', () => {
  it('labels the search and emits text, clear and scanner intents', async () => {
    const update = vi.fn(), clear = vi.fn(), scan = vi.fn()
    await mount(InventorySearchBar, { modelValue: 'Nike', 'onUpdate:modelValue': update, onClear: clear, onScan: scan })
    const input = container.querySelector('input') as HTMLInputElement
    expect(input.getAttribute('aria-label')).toBe('Buscar no estoque')
    input.value = 'Adidas'; input.dispatchEvent(new Event('input', { bubbles: true }))
    ;(container.querySelector('[aria-label="Limpar busca"]') as HTMLButtonElement).click()
    ;(container.querySelector('[aria-label="Escanear código"]') as HTMLButtonElement).click()
    expect(update).toHaveBeenCalledWith('Adidas'); expect(clear).toHaveBeenCalledOnce(); expect(scan).toHaveBeenCalledOnce()
  })

  it('announces results and exposes pressed view and selection states', async () => {
    const mode = vi.fn(), toggle = vi.fn()
    await mount(InventoryViewControls, { mode: 'compact', selectionMode: true, busy: false, ready: true, resultText: '42 itens', onMode: mode, 'onToggle-selection': toggle })
    expect(button('Compacto').getAttribute('aria-pressed')).toBe('true')
    expect(button('Selecionar').getAttribute('aria-pressed')).toBe('true')
    expect(container.querySelector('[role="status"]')?.textContent).toContain('42 itens')
    button('Quadrados').click(); button('Selecionar').click()
    expect(mode).toHaveBeenCalledWith('grid'); expect(toggle).toHaveBeenCalledOnce()
  })
})
