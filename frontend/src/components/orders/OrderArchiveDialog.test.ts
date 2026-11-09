import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import i18n from '@/i18n'
import OrderArchiveDialog from './OrderArchiveDialog.vue'
const api = vi.hoisted(() => ({ preview: vi.fn(), confirm: vi.fn() }))
vi.mock('@/services/orderArchive', () => ({ orderArchive: api }))
const auth = reactive({ isOwner: true, user: { id: 'lucas' } })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
let app: App | undefined, container: HTMLDivElement
const archived = vi.fn()
const tick = async () => { for (let n = 0; n < 6; n++) { await Promise.resolve(); await nextTick() } }
const preview = { total: 3, eligible_count: 3, blocked_count: 0, allowed: true, plan_token: 'snapshot-exact', sample: [{ id: 'old', numero_pedido: 'PED-OLD', cliente_nome: 'Gustavo', commerce_status: 'completed' }], blockers: [] }
async function mount() { container = document.createElement('div'); document.body.append(container); app = createApp(OrderArchiveDialog, { onArchived: archived }).use(i18n); app.mount(container); await tick() }
const button = (text: string) => Array.from(document.querySelectorAll('button')).find(node => node.textContent?.trim() === text)!
beforeEach(() => { vi.resetAllMocks(); sessionStorage.clear(); auth.isOwner = true; i18n.global.locale.value = 'pt'; api.preview.mockResolvedValue(preview); archived.mockReset() })
afterEach(() => { app?.unmount(); app = undefined; container?.remove() })
it('previews without mutation and confirms only the exact reviewed snapshot', async () => {
  api.confirm.mockResolvedValue({ archived_count: 3 }); await mount()
  expect(api.confirm).not.toHaveBeenCalled(); expect(button('Arquivar lista').disabled).toBe(true)
  document.querySelector<HTMLInputElement>('.archive-confirm input')!.click(); await tick(); button('Arquivar lista').click(); await tick()
  expect(api.confirm.mock.calls[0][0]).toMatchObject({ confirm: true, plan_token: 'snapshot-exact', expected_count: 3 }); expect(archived).toHaveBeenCalledOnce()
})
it('blocks the batch when any active reservation or trial order exists', async () => {
  api.preview.mockResolvedValue({ ...preview, eligible_count: 2, blocked_count: 1, allowed: false, blockers: [{ id: 'active', numero_pedido: 'PED-ACTIVE', cliente_nome: 'Sol', commerce_status: 'conditional' }] })
  await mount(); expect(document.body.textContent).toContain('PED-ACTIVE'); expect(button('Arquivar lista').disabled).toBe(true); expect(document.querySelector('.archive-confirm')).toBeNull(); expect(api.confirm).not.toHaveBeenCalled()
})
it('preserves confirmation identity after a lost response and remount', async () => {
  api.confirm.mockRejectedValueOnce(new Error('lost')).mockResolvedValueOnce({ archived_count: 3 }); await mount()
  document.querySelector<HTMLInputElement>('.archive-confirm input')!.click(); await tick(); button('Arquivar lista').click(); await tick()
  const first = structuredClone(api.confirm.mock.calls[0][0]); app!.unmount(); container.remove(); await mount()
  button('Repetir confirmação').click(); await tick(); expect(api.confirm.mock.calls[1][0]).toEqual(first); expect(sessionStorage.getItem('eleven.order-archive.lucas')).toBeNull()
})
it('does not query archival data for a seller', async () => { auth.isOwner = false; await mount(); expect(api.preview).not.toHaveBeenCalled(); expect(button('Arquivar lista').disabled).toBe(true) })
