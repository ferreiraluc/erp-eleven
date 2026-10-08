import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ItemFormModal from './ItemFormModal.vue'

const mock = vi.hoisted(() => ({ createItem: vi.fn(), getByBarcode: vi.fn(), analyzePhoto: vi.fn(),
  generateCatalog: vi.fn(), cutoutPhoto: vi.fn(), preparePhoto: vi.fn(), catalogForStorage: vi.fn(),
  photoStatus: vi.fn(), photoError: vi.fn(() => 'edit_uncertain') }))
vi.mock('@/services/productPhoto', () => mock)
vi.mock('@/services/api', () => ({ inventoryAPI: mock, ocrAPI: {} }))
let app: App, root: HTMLDivElement
const button = (text: string, scope: ParentNode = document) => {
  const found = Array.from(scope.querySelectorAll('button')).find(b => b.textContent?.trim() === text)
  if (!found) throw Error(`Missing button: ${text}`)
  return found
}
async function click(text: string, scope?: ParentNode) { button(text, scope).click(); await nextTick(); await nextTick() }
async function upload() {
  const file = document.querySelector('.photo-dialog input[type=file]') as HTMLInputElement
  Object.defineProperty(file, 'files', { value: [new File(['fixture'], 'garment.jpg', { type: 'image/jpeg' })] })
  file.dispatchEvent(new Event('change', { bubbles: true })); await nextTick(); await nextTick()
}
beforeEach(async () => {
  mock.photoStatus.mockResolvedValue({ editing_available: true, model: 'gpt-image-1-mini' })
  mock.preparePhoto.mockResolvedValue('data:image/jpeg;base64,original')
  mock.catalogForStorage.mockImplementation(async image => image)
  mock.generateCatalog.mockResolvedValue({ image: 'data:image/jpeg;base64,hanger', estimated_cost_usd: null })
  mock.getByBarcode.mockResolvedValue([])
  mock.createItem.mockResolvedValue({ id: 'fixture', name: 'Polo manual', sku_internal: 'TEST-1' })
  root = document.createElement('div'); document.body.append(root)
  app = createApp(ItemFormModal).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root); await nextTick()
})
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks(); vi.restoreAllMocks() })

describe('Hanger image in unified intake', () => {
  it('opens from capture, requests a photo then paid confirmation, and stores the chosen image after manual review', async () => {
    await click('Gerar foto no cabide')
    expect(button('Gerar no cabide').disabled).toBe(true)
    expect(document.body.textContent).toContain('Escolha ou tire uma foto')
    await upload()
    expect(button('Gerar 1 imagem com créditos').disabled).toBe(false)
    expect(mock.generateCatalog).not.toHaveBeenCalled()
    await click('Gerar 1 imagem com créditos')
    expect(mock.generateCatalog).toHaveBeenCalledWith('data:image/jpeg;base64,original', expect.any(AbortSignal))
    await click('Adicionar à conferência')
    expect(root.querySelector('.intake-thumbnail')?.getAttribute('src')).toBe('data:image/jpeg;base64,hanger')
    expect(mock.createItem).not.toHaveBeenCalled()
    await click('Conferir dados')
    const name = root.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement
    name.value = 'Polo manual'; name.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    const review = root.querySelector('.intake-review-check input') as HTMLInputElement
    review.checked = true; review.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    await click('Continuar para estoque'); await click('Criar')
    expect(mock.createItem).toHaveBeenCalledWith(expect.objectContaining({ name: 'Polo manual', image_data: 'data:image/jpeg;base64,hanger' }))
    expect(mock.analyzePhoto).not.toHaveBeenCalled()
  })

  it('reuses the original from review, retains manual fields and does not repeat generation when reopened', async () => {
    await click('Adicionar foto'); await upload(); await click('Adicionar à conferência'); await click('Conferir dados')
    const name = root.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement
    name.value = 'Minha correção'; name.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    await click('Gerar foto no cabide', root)
    expect(mock.preparePhoto).toHaveBeenCalledTimes(1)
    await click('Gerar 1 imagem com créditos'); await click('Adicionar à conferência'); await click('Conferir dados')
    expect((root.querySelector('input[placeholder="Nome do produto"]') as HTMLInputElement).value).toBe('Minha correção')
    await click('Gerar foto no cabide', root)
    expect(button('Gerar no cabide').disabled).toBe(true)
    expect(document.querySelector('.photo-paid')).toBeNull()
    expect(document.querySelector('.photo-options button[aria-pressed=true]')?.textContent).toBe('No cabide · IA')
    expect(mock.generateCatalog).toHaveBeenCalledTimes(1)
  })

  it('keeps the shortcut visible but does not offer paid confirmation when editing is unavailable', async () => {
    mock.photoStatus.mockResolvedValue({ editing_available: false, model: '' })
    await click('Gerar foto no cabide'); await upload()
    expect(button('Gerar no cabide').disabled).toBe(true)
    expect(document.querySelector('.photo-paid')).toBeNull()
    expect(document.body.textContent).toContain('A edição não está disponível')
    expect(mock.generateCatalog).not.toHaveBeenCalled()
  })
})

it('reopens the photo overlay above the product and restores focus and scroll on close', async () => {
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(function (this: HTMLElement) {
    return (this.closest('[style*="display: none"],[hidden]') ? [] : [{}]) as unknown as DOMRectList
  })
  const opener = button('Adicionar foto', root)
  for (let i = 0; i < 2; i++) {
    opener.focus(); await click('Adicionar foto', root)
    const dialog = document.querySelector<HTMLElement>('.photo-dialog')!
    expect(document.activeElement).toBe(dialog)
    expect(document.body.style.overflow).toBe('hidden')
    dialog.querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await nextTick(); await nextTick()
    expect(document.activeElement).toBe(opener)
    expect(document.querySelector<HTMLElement>('.photo-overlay')!.style.display).toBe('none')
  }
  app.unmount()
  expect(document.body.style.overflow).toBe('')
})
