import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import OcrScanner from './OcrScanner.vue'
import type { OcrParsedLabel } from '@/services/ocr'

const mocked = vi.hoisted(() => ({ parseLabel: vi.fn(), getBrands: vi.fn(), saveTemplate: vi.fn() }))
vi.mock('@/services/api', () => ({ ocrAPI: mocked }))
const example: OcrParsedLabel = { nome: 'Air Max', marca: null, tamanho: '42', cor: null,
  codigo_barras: '4006381333931', preco: 150, moeda: 'BRL', texto_bruto: 'Air Max 42 R$ 150',
  qualidade: 'legivel', evidencias: { nome: 'Air Max', tamanho: '42', preco: 'R$ 150', moeda: 'R$' },
  avisos: [], requires_review: true, matches: [], matches_total: 0 }
let app: App | undefined, container: HTMLDivElement
function button(text: string): HTMLButtonElement {
  const found = Array.from(container.querySelectorAll('button')).find(item => item.textContent?.trim() === text)
  if (!found) throw new Error(`Button not found: ${text}`)
  return found
}
async function mount(props = {}) {
  container = document.createElement('div'); document.body.append(container)
  const result = vi.fn()
  const propsState = reactive<Record<string, unknown>>({ ...props })
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp({ render: () => h(OcrScanner, { onResult: result, ...propsState }) }).use(i18n); app.mount(container)
  await nextTick()
  return { result, i18n, propsState }
}
async function upload() {
  const file = container.querySelector('input[type=file]') as HTMLInputElement
  Object.defineProperty(file, 'files', { configurable: true, value: [new File(['synthetic-image'], 'label.png', { type: 'image/png' })] })
  file.dispatchEvent(new Event('change', { bubbles: true }))
  await vi.waitFor(() => expect(container.querySelector('#ocr-name')).not.toBeNull())
  await nextTick()
}
beforeEach(() => {
  mocked.getBrands.mockResolvedValue([]); mocked.parseLabel.mockResolvedValue({ ...example }); mocked.saveTemplate.mockResolvedValue({ id: 'test' })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockRejectedValue(new Error('camera unavailable')) } })
})
afterEach(() => { app?.unmount(); container?.remove(); vi.clearAllMocks() })

describe('OCR review', () => {
  it('uses the product brand as reference through an alias, never as detected data', async () => {
    mocked.getBrands.mockResolvedValue([{ brand: 'Dolce & Gabbana', count: 8 }])
    mocked.parseLabel.mockResolvedValue({ ...example, examples_used: 3 })
    await mount({ referenceBrand: 'DG' }); await nextTick()
    expect((container.querySelector('.brand-picker input') as HTMLInputElement).value).toBe('Dolce & Gabbana')
    await upload()
    expect(mocked.parseLabel.mock.calls[0]?.[1]).toBe('Dolce & Gabbana')
    expect((container.querySelector('#ocr-brand') as HTMLInputElement).value).toBe('')
    expect(container.textContent).toContain('Exemplos usados nesta leitura: 3')
  })
  it('preserves an explicit cleared reference when the product changes or the reader reopens', async () => {
    mocked.getBrands.mockResolvedValue([{ brand: 'Prada', count: 2 }])
    mocked.parseLabel.mockResolvedValue({ ...example, examples_used: 0 })
    const { propsState } = await mount({ referenceBrand: 'Prada' }); await nextTick()
    const brand = container.querySelector('.brand-picker input') as HTMLInputElement
    brand.value = ''; brand.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    propsState.open = false; propsState.referenceBrand = 'Boss'; await nextTick()
    propsState.open = true; await nextTick()
    expect(brand.value).toBe('')
    await upload()
    expect(mocked.parseLabel.mock.calls[0]?.[1]).toBeUndefined()
    expect(container.textContent).toContain('Exemplos usados nesta leitura: 0')
  })
  it('does not substitute an alias embedded inside a different brand', async () => {
    mocked.getBrands.mockResolvedValue([{ brand: 'Dolce & Gabbana Sport', count: 4 }])
    await mount({ referenceBrand: 'DG Sport' }); await nextTick()
    expect((container.querySelector('.brand-picker input') as HTMLInputElement).value).toBe('DG Sport')
    expect(container.querySelector('.brand-trained-badge')).toBeNull()
    await upload()
    expect(mocked.parseLabel.mock.calls[0]?.[1]).toBe('DG Sport')
  })
  it('adds draft fields to unified review while still requiring review to save an example', async () => {
    const { result } = await mount({ draft: true }); await upload()
    expect(button('Salvar exemplo revisado').disabled).toBe(true)
    button('Adicionar à conferência').click(); await nextTick()
    expect(result).toHaveBeenCalledWith(expect.objectContaining({ name: 'Air Max', sale_price: 150, currency: 'BRL' }))
    expect(mocked.saveTemplate).not.toHaveBeenCalled()
  })

  it('requires human review and never uses the reference brand as an extracted value', async () => {
    const { result } = await mount()
    const brand = container.querySelector('.brand-picker input') as HTMLInputElement
    brand.value = 'Context brand'; brand.dispatchEvent(new Event('input', { bubbles: true }))
    await upload()
    expect((container.querySelector('#ocr-brand') as HTMLInputElement).value).toBe('')
    expect(button('Usar no formulário').disabled).toBe(true)
    expect(result).not.toHaveBeenCalled(); expect(mocked.saveTemplate).not.toHaveBeenCalled()
    const reviewed = container.querySelector('input[type=checkbox]') as HTMLInputElement
    reviewed.checked = true; reviewed.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    button('Usar no formulário').click(); await nextTick()
    expect(result).toHaveBeenCalledWith(expect.objectContaining({ name: 'Air Max', sale_price: 150, currency: 'BRL' }))
    expect(result.mock.calls[0]?.[0]).not.toHaveProperty('brand')
    expect(result.mock.calls[0]?.[0]).not.toHaveProperty('quantity')
    expect(mocked.saveTemplate).not.toHaveBeenCalled()
  })
  it('keeps a selected trained brand and sends it as OCR context', async () => {
    mocked.getBrands.mockResolvedValue([{ brand: 'Prada', count: 3 }])
    await mount()
    await nextTick()
    const trigger = container.querySelector('.brand-picker button') as HTMLButtonElement
    trigger.click(); await nextTick()
    const option = document.querySelector('[role=option]') as HTMLButtonElement
    expect(option).not.toBeNull()
    option.click(); await nextTick()
    expect((container.querySelector('.brand-picker input') as HTMLInputElement).value).toBe('Prada')
    await upload()
    expect(mocked.parseLabel.mock.calls[0]?.[1]).toBe('Prada')
  })
  it('changing a reviewed field requires another review and preserves locale switching', async () => {
    const { i18n } = await mount(); await upload()
    const reviewed = container.querySelector('input[type=checkbox]') as HTMLInputElement
    reviewed.checked = true; reviewed.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    const price = container.querySelector('#ocr-sale_price') as HTMLInputElement
    price.value = '200'; price.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(button('Usar no formulário').disabled).toBe(true)
    i18n.global.locale.value = 'es'; await nextTick(); expect(container.textContent).toContain('Usar en el formulario')
    i18n.global.locale.value = 'en'; await nextTick(); expect(container.textContent).toContain('Use in form')
  })
  it('does not apply a price with an unknown currency', async () => {
    mocked.parseLabel.mockResolvedValue({ ...example, moeda: null })
    const { result } = await mount(); await upload()
    const reviewed = container.querySelector('input[type=checkbox]') as HTMLInputElement
    reviewed.checked = true; reviewed.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    button('Usar no formulário').click(); await nextTick()
    expect(result).not.toHaveBeenCalled(); expect(container.textContent).toContain('selecione a moeda')
  })
})
