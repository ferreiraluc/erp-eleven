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
afterEach(() => { app?.unmount(); app = undefined; container?.remove(); vi.unstubAllGlobals() })

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

  it('discloses mobile zoom from Squares, keeps it open while adjusting and dismisses outside or by keyboard', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    const update = vi.fn()
    await mount(InventoryViewControls, { mode: 'grid', selectionMode: false, busy: false, ready: true, resultText: '42 itens', zoomEnabled: true, gridZoom: 1, 'onUpdate:gridZoom': update })
    const trigger = button('Quadrados')
    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({ left: 80, bottom: 240, width: 34 } as DOMRect)
    expect(container.querySelector('[type="range"]')).toBeNull()
    trigger.click(); await nextTick(); await nextTick()
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    const range = container.querySelector<HTMLInputElement>('[type="range"]')!
    range.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    range.value = '0'; range.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(update).toHaveBeenCalledWith(0)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true })); await nextTick()
    expect(container.querySelector('[type="range"]')).toBeNull()
    trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true })); await nextTick(); await nextTick()
    const openedRange = container.querySelector<HTMLInputElement>('[type="range"]')!
    expect(document.activeElement).toBe(openedRange)
    openedRange.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await nextTick()
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(trigger)
    trigger.click(); await nextTick(); await nextTick()
    button('Lista').click(); await nextTick()
    expect(container.querySelector('[type="range"]')).toBeNull()
  })

  it('keeps the desktop Squares control as a plain view selector', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    const mode = vi.fn()
    await mount(InventoryViewControls, { mode: 'compact', selectionMode: false, busy: false, ready: true, resultText: '42 itens', zoomEnabled: true, onMode: mode })
    button('Quadrados').click(); await nextTick()
    expect(mode).toHaveBeenCalledWith('grid')
    expect(button('Quadrados').hasAttribute('aria-expanded')).toBe(false)
    expect(container.querySelector('[type="range"]')).toBeNull()
  })
})
