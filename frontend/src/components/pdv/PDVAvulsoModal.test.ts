import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import PDVAvulsoModal from './PDVAvulsoModal.vue'
let app: App | undefined, container: HTMLDivElement
function input(selector: string, value: string) {
  const field = container.querySelector(selector) as HTMLInputElement
  field.value = value; field.dispatchEvent(new Event('input', { bubbles: true }))
}
afterEach(() => { app?.unmount(); container?.remove() })
describe('Manual PDV quantity form', () => {
  it('retains invalid precision for correction and emits a valid fraction without rounding', async () => {
    const add = vi.fn()
    const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
    container = document.createElement('div'); document.body.append(container)
    app = createApp(PDVAvulsoModal, { onAdd: add }).use(i18n); app.mount(container); await nextTick()
    input('input[type="text"]', 'Serviço'); input('.avulso-row input', '100'); input('input[step="0.001"]', '0.1234'); await nextTick()
    ;(container.querySelector('.avulso-btn-add') as HTMLButtonElement).click(); await nextTick()
    expect(add).not.toHaveBeenCalled()
    expect((container.querySelector('input[step="0.001"]') as HTMLInputElement).value).toBe('0.1234')
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('3 casas decimais')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('3 decimal places')
    input('input[step="0.001"]', '0.125'); await nextTick()
    ;(container.querySelector('.avulso-btn-add') as HTMLButtonElement).click(); await nextTick()
    expect(add).toHaveBeenCalledOnce()
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ quantity: .125, is_avulso: true, item_id: null }))
  })
})
