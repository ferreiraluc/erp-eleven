import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import GradeAiModal from './GradeAiModal.vue'
import { saveGradePreview, restoreGradePreview, type GradeAnalysis, type GradePreview } from '@/services/inventoryGradeAi'
import { chooseDropdown } from '@/test/dropdown'

const ai = vi.hoisted(() => ({ analyze: vi.fn(), preview: vi.fn(), apply: vi.fn() }))
let auth = reactive({ user: { id: 'user-a' } })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/services/api', () => ({ default: { post: vi.fn() } }))
vi.mock('@/services/inventoryGradeAi', async importOriginal => ({ ...await importOriginal<typeof import('@/services/inventoryGradeAi')>(), inventoryGradeAi: ai }))
vi.mock('./ProductThumbnail.vue', () => ({ default: { props: ['item'], template: '<span class="thumbnail-test" />' } }))

const id = (n: number) => `10000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const products = () => [1, 2, 3].map(n => ({ id: id(n), name: `Camisa Boss ${n}`, brand: 'Boss', category: 'Camisas', size: ['S', 'M', 'L'][n - 1], color: 'Preto', group_key: null, version: String(n).repeat(64), is_active: true, has_image: false }))
const analysis = (): GradeAnalysis => ({ provider: 'deepseek', model: 'mock-model', analyzed_count: 3, photos_analyzed: 0, advisory_only: true, products: products(),
  suggestions: [{ item_ids: [id(1), id(2), id(3)], confidence: 'high', evidence: ['Mesmo modelo e marca, tamanhos diferentes.'], warnings: ['Confira o acabamento.'] }], warnings: ['Sugestão para conferência manual.'] })
const preview = (): GradePreview => ({ preview_token: 'signed-preview-token-for-this-account', expires_at: '2030-11-02T20:00:00Z', target_group_key: 'Boss final', items: products().slice(0, 2),
  existing_members: [{ ...products()[2], group_key: 'Boss final' }], source_groups: [{ group_key: 'Origem', moving_count: 2, remaining_count: 1 }], warnings: ['Conferir a grade de destino.'] })
let app: App | undefined, root: HTMLDivElement
async function flush() { for (let n = 0; n < 10; n++) { await Promise.resolve(); await nextTick() } }
async function mount(props: Record<string, unknown> = {}, locale = 'pt') {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale, messages: { pt: {}, es: {}, en: {} } })
  app = createApp(GradeAiModal, { itemIds: [id(1), id(2), id(3)], existingGroupKeys: ['Destino existente'], ...props }).use(i18n)
  app.mount(root); await flush(); return i18n
}
function button(text: string) {
  const found = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button')).find(el => el.textContent?.trim() === text)
  if (!found) throw new Error(`Missing button: ${text}`)
  return found
}
function setInput(input: HTMLInputElement, value: string) { input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })) }
function check(input: HTMLInputElement, checked: boolean) { input.checked = checked; input.dispatchEvent(new Event('change', { bubbles: true })) }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (reason: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
async function chooseSuggestion() { button('Analisar selecionados').click(); await flush(); button('Conferir esta sugestão').click(); await flush() }
async function prepare() {
  await chooseSuggestion()
  setInput(document.body.querySelector<HTMLInputElement>('.grade-ai-destination input[type="text"]')!, 'Boss final')
  button('Preparar conferência').click(); await flush()
}
async function confirm() { check(document.body.querySelector<HTMLInputElement>('.grade-ai-check input')!, true); await flush(); button('Confirmar vínculos').click(); await flush() }
beforeEach(() => {
  vi.restoreAllMocks(); vi.resetAllMocks(); sessionStorage.clear(); auth = reactive({ user: { id: 'user-a' } })
  ai.analyze.mockResolvedValue(analysis()); ai.preview.mockResolvedValue(preview())
  ai.apply.mockResolvedValue({ target_group_key: 'Boss final', item_ids: [id(1), id(2)], applied_count: 2, already_applied: false })
})
afterEach(() => { app?.unmount(); app = undefined; root?.remove(); vi.restoreAllMocks() })

describe('Grade AI review and confirmation', () => {
  it('does no AI work on open and sends photo opt-out or opt-in only after the explicit analysis action', async () => {
    await mount(); expect(ai.analyze).not.toHaveBeenCalled(); expect(ai.preview).not.toHaveBeenCalled(); expect(ai.apply).not.toHaveBeenCalled()
    const photos = document.body.querySelector<HTMLInputElement>('.grade-ai-check input')!
    check(photos, false); button('Analisar selecionados').click(); await flush()
    expect(ai.analyze).toHaveBeenLastCalledWith([id(1), id(2), id(3)], false, expect.any(AbortSignal))
    button('Voltar').click(); await flush()
    check(document.body.querySelector<HTMLInputElement>('.grade-ai-check input')!, true)
    button('Analisar selecionados').click(); await flush()
    expect(ai.analyze).toHaveBeenLastCalledWith([id(1), id(2), id(3)], true, expect.any(AbortSignal))
    expect(ai.apply).not.toHaveBeenCalled()
  })

  it.each([1, 25])('blocks an analysis for %i selected products', async count => {
    await mount({ itemIds: Array.from({ length: count }, (_, n) => id(n + 1)) })
    expect(button('Analisar selecionados').disabled).toBe(true)
    button('Analisar selecionados').click(); await flush()
    expect(ai.analyze).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Selecione de 2 a 24 produtos')
  })

  it.each([2, 24])('allows the explicit analysis action at the %i-product boundary', async count => {
    await mount({ itemIds: Array.from({ length: count }, (_, n) => id(n + 1)) })
    expect(button('Analisar selecionados').disabled).toBe(false)
    expect(ai.analyze).not.toHaveBeenCalled()
    button('Analisar selecionados').click(); await flush()
    expect(ai.analyze.mock.calls[0][0]).toHaveLength(count)
  })

  it('rejects a duplicate selection without sending it to the provider', async () => {
    await mount({ itemIds: [id(1), id(1)] })
    expect(button('Analisar selecionados').disabled).toBe(true)
    expect(ai.analyze).not.toHaveBeenCalled()
  })

  it('shows cluster reasons, lets the reviewer uncheck products, and previews selected versions into a new grade', async () => {
    await mount(); await chooseSuggestion()
    expect(document.body.textContent).toContain('Mesmo modelo e marca, tamanhos diferentes.')
    expect(document.body.textContent).toContain('Confira o acabamento.')
    check(document.body.querySelector<HTMLInputElement>(`[aria-label="Incluir Camisa Boss 3"]`)!, false); await flush()
    setInput(document.body.querySelector<HTMLInputElement>('.grade-ai-destination input[type="text"]')!, 'Boss final')
    button('Preparar conferência').click(); await flush()
    expect(ai.preview).toHaveBeenCalledExactlyOnceWith({ item_ids: [id(1), id(2)], new_group_name: 'Boss final', expected_versions: { [id(1)]: '1'.repeat(64), [id(2)]: '2'.repeat(64) } }, expect.any(AbortSignal))
    expect(document.body.textContent).toContain('Grade de destino: Boss final')
    expect(document.body.textContent).toContain('2 itens saem de “Origem”; 1 permanecem.')
    expect(document.body.textContent).toContain('1 itens já estão nesta grade')
    expect(button('Confirmar vínculos').disabled).toBe(true)
    expect(ai.apply).not.toHaveBeenCalled()
    await confirm()
    expect(ai.apply).toHaveBeenCalledExactlyOnceWith(preview().preview_token)
    expect(restoreGradePreview('user-a')).toBeNull()
  })

  it('requires at least two chosen products and supports an explicitly selected existing destination', async () => {
    await mount(); await chooseSuggestion()
    check(document.body.querySelector<HTMLInputElement>('[aria-label="Incluir Camisa Boss 2"]')!, false)
    check(document.body.querySelector<HTMLInputElement>('[aria-label="Incluir Camisa Boss 3"]')!, false); await flush()
    expect(button('Preparar conferência').disabled).toBe(true)
    check(document.body.querySelector<HTMLInputElement>('[aria-label="Incluir Camisa Boss 2"]')!, true); await flush()
    await chooseDropdown(document.body.querySelector('button[aria-label="Destino dos itens"]'), 'existing'); await flush()
    await chooseDropdown(document.body.querySelector('button[aria-label="Escolha a grade de destino"]'), 'Destino existente'); await flush()
    button('Preparar conferência').click(); await flush()
    expect(ai.preview.mock.lastCall?.[0]).toEqual({ item_ids: [id(1), id(2)], target_group_key: 'Destino existente', expected_versions: { [id(1)]: '1'.repeat(64), [id(2)]: '2'.repeat(64) } })
  })

  it('reviews only the explicitly chosen cluster and resets deselections when switching suggestions', async () => {
    const result = analysis()
    result.suggestions.push({ item_ids: [id(2), id(3)], confidence: 'medium', evidence: ['Outro acabamento compatível.'], warnings: [] })
    ai.analyze.mockResolvedValue(result)
    await mount(); await chooseSuggestion()
    check(document.body.querySelector<HTMLInputElement>('[aria-label="Incluir Camisa Boss 3"]')!, false); await flush()
    button('Conferir esta sugestão').click(); await flush()
    const selected = Array.from(document.body.querySelectorAll<HTMLInputElement>('.grade-ai-product input:checked')).map(input => input.getAttribute('aria-label'))
    expect(selected).toEqual(['Incluir Camisa Boss 2', 'Incluir Camisa Boss 3'])
    button('Preparar conferência').click(); await flush()
    expect(ai.preview.mock.lastCall?.[0].item_ids).toEqual([id(2), id(3)])
    expect(ai.apply).not.toHaveBeenCalled()
  })

  it('shows a provider failure without creating a preview or writing links', async () => {
    ai.analyze.mockRejectedValue({ response: { status: 503, data: { detail: 'Provedor indisponível.' } } })
    await mount(); button('Analisar selecionados').click(); await flush()
    expect(document.body.querySelector('[role="alert"]')?.textContent).toBe('Provedor indisponível.')
    expect(ai.preview).not.toHaveBeenCalled(); expect(ai.apply).not.toHaveBeenCalled()
    expect(button('Analisar selecionados').disabled).toBe(false)
  })

  it('shows an inconclusive analysis without selecting or preparing any grade automatically', async () => {
    ai.analyze.mockResolvedValue({ ...analysis(), suggestions: [] })
    await mount(); button('Analisar selecionados').click(); await flush()
    expect(document.body.textContent).toContain('A IA não encontrou uma associação suficiente')
    expect(document.body.querySelector('.grade-ai-destination')).toBeNull()
    expect(ai.preview).not.toHaveBeenCalled(); expect(ai.apply).not.toHaveBeenCalled()
  })

  it('rejects a stale preview and requires another explicit review after a stale confirmation', async () => {
    ai.preview.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Os produtos foram alterados.' } } })
    await mount(); await prepare()
    expect(document.body.querySelector('[role="alert"]')?.textContent).toBe('Os produtos foram alterados.')
    expect(ai.apply).not.toHaveBeenCalled()
    button('Preparar conferência').click(); await flush()
    ai.apply.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'A conferência expirou.' } } })
    await confirm()
    expect(document.body.querySelector('[role="alert"]')?.textContent).toBe('A conferência expirou.')
    expect(restoreGradePreview('user-a')).toBeNull()
    expect(button('Confirmar vínculos').disabled).toBe(true)
    expect(document.body.textContent).not.toContain('Conferir resultado')
  })

  it('retries an uncertain write using the same token and restores it after remount without analyzing again', async () => {
    ai.apply.mockRejectedValueOnce(new Error('timeout'))
    await mount(); await prepare(); await confirm()
    expect(restoreGradePreview('user-a')?.preview_token).toBe(preview().preview_token)
    expect(document.body.textContent).toContain('A confirmação não foi recebida.')
    expect(document.body.querySelector('.grade-ai-check input')).toBeNull()
    app!.unmount(); root.remove(); app = undefined
    const applied = vi.fn(); await mount({ onApplied: applied })
    expect(document.body.textContent).toContain('Há uma confirmação anterior para esta conta.')
    expect(ai.analyze).toHaveBeenCalledTimes(1); expect(ai.preview).toHaveBeenCalledTimes(1)
    button('Conferir resultado').click(); await flush()
    expect(ai.apply.mock.calls.map(call => call[0])).toEqual([preview().preview_token, preview().preview_token])
    expect(applied).toHaveBeenCalledWith('Boss final', 2)
    expect(restoreGradePreview('user-a')).toBeNull()
  })

  it('does not commit when this device cannot preserve the recovery token', async () => {
    await mount(); await prepare()
    vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => { throw new Error('quota') })
    await confirm()
    expect(document.body.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível guardar a confirmação neste aparelho.')
    expect(ai.apply).not.toHaveBeenCalled()
    expect(button('Confirmar vínculos').disabled).toBe(false)
  })

  it('blocks duplicate confirmation and closing while a write is in flight', async () => {
    const result = deferred<{ target_group_key: string; applied_count: number }>(); ai.apply.mockReturnValueOnce(result.promise)
    const close = vi.fn(); await mount({ onClose: close }); await prepare(); await confirm()
    const closeControl = document.body.querySelector<HTMLButtonElement>('[data-dialog-close]')!
    expect(closeControl.disabled).toBe(true)
    closeControl.click()
    document.body.querySelector<HTMLElement>('.grade-ai-backdrop')!.click()
    button('Salvando vínculos…').click(); await flush()
    expect(close).not.toHaveBeenCalled()
    expect(ai.apply).toHaveBeenCalledOnce()
    result.resolve({ target_group_key: 'Boss final', applied_count: 2 }); await flush()
  })

  it('blocks unreadable stored data until an explicit reset, without replacing the saved operation', async () => {
    sessionStorage.setItem('eleven:grade-confirmation:user-a', '{bad')
    await mount()
    expect(button('Analisar selecionados').disabled).toBe(true)
    expect(document.body.textContent).toContain('A confirmação guardada não pôde ser lida.')
    expect(ai.analyze).not.toHaveBeenCalled(); expect(ai.apply).not.toHaveBeenCalled()
    button('Conferir seleção novamente').click(); await flush()
    expect(sessionStorage.getItem('eleven:grade-confirmation:user-a')).toBeNull()
    expect(button('Analisar selecionados').disabled).toBe(false)
  })

  it('keeps another account confirmation isolated and closes on an account change while discarding a stale analysis', async () => {
    saveGradePreview('user-b', preview())
    const reply = deferred<GradeAnalysis>(); ai.analyze.mockReturnValue(reply.promise)
    const close = vi.fn(); await mount({ onClose: close })
    expect(document.body.textContent).not.toContain('Há uma confirmação anterior')
    button('Analisar selecionados').click(); await flush()
    const signal = ai.analyze.mock.calls[0][2] as AbortSignal
    auth.user.id = 'user-b'; await flush()
    expect(signal.aborted).toBe(true); expect(close).toHaveBeenCalledOnce()
    reply.resolve(analysis()); await flush()
    expect(document.body.querySelector('.grade-ai-advice')).toBeNull()
    expect(restoreGradePreview('user-b')?.preview_token).toBe(preview().preview_token)
    expect(ai.apply).not.toHaveBeenCalled()
  })

  it('aborts reads on unmount and ignores their replies and an in-flight confirmation result', async () => {
    const reply = deferred<GradeAnalysis>(); ai.analyze.mockReturnValueOnce(reply.promise)
    await mount(); button('Analisar selecionados').click(); await flush()
    const signal = ai.analyze.mock.calls[0][2] as AbortSignal
    app!.unmount(); root.remove(); app = undefined
    expect(signal.aborted).toBe(true); reply.resolve(analysis()); await flush()
    expect(document.body.querySelector('.grade-ai-advice')).toBeNull()
    const result = deferred<{ target_group_key: string; applied_count: number }>(); ai.apply.mockReturnValueOnce(result.promise)
    const applied = vi.fn(); await mount({ onApplied: applied }); await prepare(); await confirm()
    expect(restoreGradePreview('user-a')).not.toBeNull()
    app!.unmount(); root.remove(); app = undefined
    result.resolve({ target_group_key: 'Boss final', applied_count: 2 }); await flush()
    expect(applied).not.toHaveBeenCalled()
    expect(restoreGradePreview('user-a')).not.toBeNull()
  })

  it.each([['es', 'Variantes con IA', 'Analizar seleccionados'], ['en', 'AI product groups', 'Analyze selected products']])('translates the open modal in %s', async (locale, title, analyzeLabel) => {
    await mount({}, locale)
    expect(document.body.querySelector('[role="dialog"]')?.getAttribute('aria-label')).toBe(title)
    expect(button(analyzeLabel)).toBeDefined()
    button(analyzeLabel).click(); await flush()
    expect(document.body.textContent).toContain(locale === 'es' ? 'Sugerencia 1' : 'Suggestion 1')
    expect(ai.apply).not.toHaveBeenCalled()
  })
})
