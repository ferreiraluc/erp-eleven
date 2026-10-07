import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import RastreamentoCard from './RastreamentoCard.vue'
import { uiText } from '@/i18n/uiText'
const { summary, push } = vi.hoisted(() => ({ summary: vi.fn(), push: vi.fn() }))
vi.mock('@/stores/rastreamento', () => ({ useRastreamentoStore: () => ({ obterResumoDashboard: summary }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: 'ADMIN' } }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
let app: App | undefined, container: HTMLDivElement
let media: { matches: boolean; addEventListener: ReturnType<typeof vi.fn>; removeEventListener: ReturnType<typeof vi.fn> }
let resize: (event: { matches: boolean }) => void
beforeEach(() => {
  media = { matches: true, addEventListener: vi.fn((_name, listener) => { resize = listener }), removeEventListener: vi.fn() }
  vi.stubGlobal('matchMedia', vi.fn(() => media))
})
const shipment = (id: string, status = 'PENDENTE', ativo = true) => ({ id, codigo_rastreio: id, status, ativo, destinatario: id, historico_eventos: [] })
async function mount(rows: ReturnType<typeof shipment>[], pending?: ReturnType<typeof shipment>[]) {
  summary.mockResolvedValue({ total_rastreamentos: 10, entregues: 5, rastreamentos_recentes: rows, rastreamentos_pendentes: pending })
  container = document.createElement('div'); document.body.append(container)
  app = createApp(RastreamentoCard); app.config.globalProperties.$tr = uiText; app.mount(container)
  await Promise.resolve(); await Promise.resolve(); await nextTick()
}
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.clearAllMocks(); vi.unstubAllGlobals() })

describe('dashboard pending shipments', () => {
  it('keeps only three active undelivered rows even with an older backend response', async () => {
    await mount([shipment('delivered','ENTREGUE'), shipment('archived','PENDENTE',false), shipment('one'), shipment('two','EM_TRANSITO'), shipment('three','ERRO'), shipment('four')])
    expect(Array.from(container.querySelectorAll('.track-name'), el => el.textContent)).toEqual(['one','two','three'])
    expect(container.querySelector('.rstat-entregue .rstat-num')?.textContent).toBe('5')
    container.querySelector<HTMLElement>('.rastreamento-card')!.click()
    expect(push).toHaveBeenCalledWith('/rastreamento')
  })
  it('shows the pending-delivery empty state when only delivered parcels remain', async () => {
    await mount([shipment('delivered','ENTREGUE')])
    expect(container.querySelectorAll('.track-card')).toHaveLength(0)
    expect(container.querySelector('.empty-text')?.textContent).toBe('Nenhum envio pendente de entrega')
  })
  it('restores the desktop list including delivered parcels and switches without another request', async () => {
    media.matches = false
    const recent = Array.from({length: 12}, (_, i) => shipment(`delivered-${i}`, 'ENTREGUE'))
    const pending = [shipment('older-pending'), shipment('older-transit', 'EM_TRANSITO')]
    await mount(recent, pending)
    expect(container.querySelectorAll('.track-card')).toHaveLength(12)
    expect(container.querySelector('.recentes-title')?.textContent).toBe('Últimos Rastreamentos')
    resize({matches: true}); await nextTick()
    expect(Array.from(container.querySelectorAll('.track-name'), el => el.textContent)).toEqual(['older-pending','older-transit'])
    expect(container.querySelector('.recentes-title')?.textContent).toBe('Últimos envios pendentes')
    resize({matches: false}); await nextTick()
    expect(container.querySelectorAll('.track-card')).toHaveLength(12)
    expect(summary).toHaveBeenCalledOnce()
    app!.unmount(); app = undefined
    expect(media.removeEventListener).toHaveBeenCalledWith('change', resize)
  })
  it('honors an explicitly empty mobile list rather than falling back to desktop records', async () => {
    await mount([shipment('desktop')], [])
    expect(container.querySelectorAll('.track-card')).toHaveLength(0)
  })

})
