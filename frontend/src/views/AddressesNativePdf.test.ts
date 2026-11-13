import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import AddressesView from './AddressesView.vue'

const mock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), share: vi.fn(), auth: { isOwner: false, token: 'qa-session' } }))
vi.mock('@/services/api', async original => ({ ...await original<typeof import('@/services/api')>(), default: { get: mock.get, post: mock.post } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mock.auth }))
vi.mock('@/services/nativeFiles', async original => ({ ...await original<typeof import('@/services/nativeFiles')>(), usesNativeFiles: () => true, shareNativePdf: mock.share }))
vi.mock('@/components/ModuleHeader.vue', () => ({ default: { template: '<header><slot /></header>' } }))
let app: App | undefined, root: HTMLDivElement
const settle = async () => { for (let i = 0; i < 16; i++) { await Promise.resolve(); await nextTick() } }
const button = (text: string) => Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === text)!
async function mount(query = { action: 'print' } as Record<string, string>) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] })
  await router.push({ path: '/', query }); await router.isReady()
  app = createApp(AddressesView).use(router).use(i18n); app.mount(root); await settle()
}
beforeEach(() => {
  vi.resetAllMocks(); vi.useFakeTimers(); mock.auth.token = 'qa-session'; i18n.global.locale.value = 'pt'
  root = document.createElement('div'); document.body.append(root)
  const pdf = new Blob(['%PDF-1.4\nfixture\n%%EOF'], { type: 'application/pdf' })
  mock.get.mockImplementation(async (url: string) => ({ data: url.endsWith('/pdf') ? pdf
    : url.endsWith('/overview') ? { addresses: 0, statuses: {}, devices: [] }
      : url.endsWith('/senders') || url.endsWith('/layouts') ? []
        : url === '/api/freight/orders/qa-freight' ? { id: 'qa-freight', pdf_available: true, state: 'released', recipient: 'Synthetic' }
          : url.endsWith('/status') ? { configured: false, environment: 'sandbox', availability: 'configuration' }
            : { items: [], total: 0 } }))
  mock.post.mockResolvedValue({ data: pdf }); mock.share.mockResolvedValue('opened')
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:forbidden'); vi.spyOn(window, 'open').mockImplementation(() => null)
})
afterEach(() => { app?.unmount(); app = undefined; root.remove(); vi.restoreAllMocks(); vi.useRealTimers() })

it('opens address PDF options only after a tap, preserving the separate store print confirmation', async () => {
  await mount()
  expect(mock.share).not.toHaveBeenCalled(); expect(mock.post).not.toHaveBeenCalled()
  button('Opções do PDF').click(); await settle()
  expect(mock.post).toHaveBeenCalledTimes(1); expect(mock.post.mock.calls[0]![0]).toBe('/api/address-manager/preview')
  expect(mock.share).toHaveBeenCalledTimes(1); expect(mock.share.mock.calls[0]![0]).toMatchObject({ name: 'eleven-endereco.pdf', type: 'application/pdf' })
  expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(window.open).not.toHaveBeenCalled()
  expect(button('Enviar à impressora')).toBeDefined()
})

it('allows cancelling and retrying a shipping-label share without buying or printing', async () => {
  mock.share.mockResolvedValueOnce('cancelled').mockResolvedValueOnce('opened')
  await mount({ tab: 'freight', freight_id: 'qa-freight' })
  button('Opções do PDF').click(); await settle()
  expect(document.body.textContent).toContain('Compartilhamento cancelado')
  button('Opções do PDF').click(); await settle()
  expect(mock.share).toHaveBeenCalledTimes(2); expect(mock.post).not.toHaveBeenCalled()
  const current = mock.share.mock.calls[1]![1] as () => boolean
  expect(current()).toBe(true); mock.auth.token = 'other-session'; expect(current()).toBe(false)
})

it('does not open an old-session address PDF after the account changes during preparation', async () => {
  let finish!: (value: unknown) => void
  mock.post.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  await mount(); button('Opções do PDF').click(); await settle()
  mock.auth.token = 'other-session'; finish({ data: new Blob(['%PDF-1.4\n%%EOF']) }); await settle()
  expect(mock.share).not.toHaveBeenCalled(); expect(URL.createObjectURL).not.toHaveBeenCalled()
})
