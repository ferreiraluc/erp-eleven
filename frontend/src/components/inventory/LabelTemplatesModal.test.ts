import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import LabelTemplatesModal from './LabelTemplatesModal.vue'

const api = vi.hoisted(() => ({ getTemplates: vi.fn(), getBrands: vi.fn(), getTemplate: vi.fn(), deleteTemplate: vi.fn() }))
vi.mock('@/services/api', () => ({ ocrAPI: api }))
let app: App | undefined, container: HTMLDivElement
const example = { id: 'example-one', brand: 'Prada', parsed_name: 'Reviewed label', has_image: true, created_at: '2020-01-02T12:00:00Z' }
async function mount() {
  container = document.createElement('div'); document.body.append(container)
  const close = vi.fn()
  app = createApp(LabelTemplatesModal, { onClose: close }).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(container)
  await vi.waitFor(() => expect(container.querySelector('.lt-view-example')).not.toBeNull())
  return { close }
}
beforeEach(() => {
  api.getTemplates.mockResolvedValue([example])
  api.getBrands.mockResolvedValue([{ brand: 'Prada', count: 1 }])
  api.getTemplate.mockResolvedValue({ ...example, sample_image: 'data:image/jpeg;base64,TEST' })
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
})
afterEach(() => { app?.unmount(); container?.remove(); vi.restoreAllMocks(); vi.clearAllMocks() })

it('loads only the selected example image on demand and closes its preview before the gallery', async () => {
  const { close } = await mount()
  expect(api.getTemplate).not.toHaveBeenCalled()
  ;(container.querySelector('.lt-view-example') as HTMLButtonElement).click()
  await vi.waitFor(() => expect(container.querySelector('.lt-lightbox-img')).not.toBeNull())
  expect(api.getTemplate).toHaveBeenCalledExactlyOnceWith('example-one')
  const preview = container.querySelector('.lt-lightbox') as HTMLElement
  expect(preview.getAttribute('role')).toBe('dialog')
  preview.focus(); preview.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await nextTick()
  expect(container.querySelector('.lt-lightbox')).toBeNull()
  expect(container.querySelector('.lt-modal')).not.toBeNull()
  expect(close).not.toHaveBeenCalled()
})

it('shows a retryable error when an example photo cannot be loaded', async () => {
  api.getTemplate.mockRejectedValue(new Error('Network unavailable'))
  await mount()
  ;(container.querySelector('.lt-view-example') as HTMLButtonElement).click()
  await vi.waitFor(() => expect(container.querySelector('[role=alert]')?.textContent).toContain('Não foi possível abrir'))
  expect((container.querySelector('.lt-view-example') as HTMLButtonElement).disabled).toBe(false)
  expect(container.querySelector('.lt-lightbox')).toBeNull()
})
