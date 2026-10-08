import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ProductPhotoAssistant from './ProductPhotoAssistant.vue'
const mock = vi.hoisted(() => ({ analyzePhoto: vi.fn(), generateCatalog: vi.fn(), cutoutPhoto: vi.fn(), preparePhoto: vi.fn(), catalogForStorage: vi.fn(), photoStatus: vi.fn(), photoError: vi.fn(() => 'edit_uncertain') }))
vi.mock('@/services/productPhoto', () => mock)
let app: App, root: HTMLDivElement
const button = (text: string) => Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === text)!
async function mount(props = {}, upload = true) {
  root = document.createElement('div'); document.body.append(root)
  const result = vi.fn()
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, en: {}, es: {} } })
  app = createApp(ProductPhotoAssistant, { onResult: result, ...props }).use(i18n); app.mount(root)
  await nextTick(); await nextTick()
  if (!upload) return { result, i18n }
  const file = document.querySelector('input[type=file]') as HTMLInputElement
  Object.defineProperty(file, 'files', { value: [new File(['test'], 'photo.jpg', { type: 'image/jpeg' })] })
  file.dispatchEvent(new Event('change', { bubbles: true }))
  await nextTick(); await nextTick()
  return { result, i18n }
}
async function review() {
  const checkbox = document.querySelector('input[type=checkbox]') as HTMLInputElement
  checkbox.checked = true; checkbox.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
}
beforeEach(() => {
  mock.photoStatus.mockResolvedValue({ editing_available: true, model: 'gpt-image-1-mini' })
  mock.preparePhoto.mockResolvedValue('data:image/jpeg;base64,original')
  mock.catalogForStorage.mockResolvedValue('data:image/jpeg;base64,stored')
  mock.cutoutPhoto.mockResolvedValue('data:image/jpeg;base64,cutout')
  mock.analyzePhoto.mockResolvedValue({ name: 'Camiseta azul', brand: '', size: '', category: 'Camisetas', color: 'Azul', description: '', single_product: true, brand_evidence: '', size_evidence: '' })
  mock.generateCatalog.mockResolvedValue({ image: 'data:image/jpeg;base64,generated', model: 'gpt-image-1-mini', estimated_cost_usd: 0.006 })
})
afterEach(() => { app?.unmount(); root?.remove(); vi.clearAllMocks() })
describe('Photo-assisted product form', () => {
  it('can add only a photo to the unified review without inventing a name or calling AI', async () => {
    const { result } = await mount({ draft: true })
    expect(document.querySelector('input[type=checkbox]')).toBeNull()
    button('Adicionar à conferência').click(); await nextTick(); await nextTick()
    expect(result).toHaveBeenCalledWith(expect.objectContaining({ name: '', image_data: 'data:image/jpeg;base64,stored' }))
    expect(mock.analyzePhoto).not.toHaveBeenCalled(); expect(mock.generateCatalog).not.toHaveBeenCalled()
  })

  it('never calls paid providers on upload, needs review and only fills the product form', async () => {
    const { result } = await mount()
    expect(mock.analyzePhoto).not.toHaveBeenCalled(); expect(mock.generateCatalog).not.toHaveBeenCalled()
    button('Sugerir dados').click(); await nextTick(); await nextTick()
    expect(button('Usar no cadastro').disabled).toBe(true)
    await review(); button('Usar no cadastro').click(); await nextTick(); await nextTick()
    expect(result).toHaveBeenCalledWith(expect.objectContaining({ name: 'Camiseta azul', image_data: 'data:image/jpeg;base64,stored' }))
    expect(result.mock.calls[0][0]).not.toHaveProperty('quantity')
  })
  it('edits and photo changes require fresh review, without another analysis call', async () => {
    await mount(); button('Sugerir dados').click(); await nextTick(); await nextTick(); await review()
    const input = document.querySelector('[name=photo-name]') as HTMLInputElement
    input.value = 'Nome corrigido'; input.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(button('Usar no cadastro').disabled).toBe(true)
    await review(); button('Remover fundo · grátis').click(); await nextTick(); await nextTick()
    expect(button('Usar no cadastro').disabled).toBe(true)
    expect(mock.analyzePhoto).toHaveBeenCalledTimes(1); expect(mock.generateCatalog).not.toHaveBeenCalled()
  })
  it('explicitly confirms one paid image and never repeats a failed request', async () => {
    mock.generateCatalog.mockRejectedValue(new Error('timeout'))
    await mount(); button('Gerar no cabide').click(); await nextTick()
    expect(mock.generateCatalog).not.toHaveBeenCalled()
    button('Gerar 1 imagem com créditos').click(); await nextTick(); await nextTick()
    expect(mock.generateCatalog).toHaveBeenCalledTimes(1)
    expect(button('Gerar no cabide').disabled).toBe(true)
    expect(document.body.textContent).toContain('pode ter sido cobrada')
  })
  it('translates the entire review flow', async () => {
    const { i18n } = await mount()
    i18n.global.locale.value = 'es'; await nextTick(); expect(button('Usar en el registro')).toBeDefined()
    i18n.global.locale.value = 'en'; await nextTick(); expect(button('Use in form')).toBeDefined()
  })
})

it('edits an existing image without uploading and still requires explicit paid confirmation', async () => {
  const image = 'data:image/jpeg;base64,existing'
  await mount({ draft: true, initialImage: image, startWithHanger: true }, false)
  expect(mock.preparePhoto).not.toHaveBeenCalled()
  expect(mock.generateCatalog).not.toHaveBeenCalled()
  expect((document.querySelector('.photo-comparison img') as HTMLImageElement).src).toBe(image)
  button('Remover fundo · grátis').click(); await nextTick(); await nextTick()
  expect(mock.cutoutPhoto).toHaveBeenCalledWith(image, expect.any(AbortSignal))
  button('Gerar 1 imagem com créditos').click(); await nextTick(); await nextTick()
  expect(mock.generateCatalog).toHaveBeenCalledWith(image, expect.any(AbortSignal))
})
