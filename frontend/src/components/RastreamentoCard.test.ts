import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import RastreamentoCard from './RastreamentoCard.vue'
import { uiText } from '@/i18n/uiText'
const { summary, push } = vi.hoisted(() => ({ summary: vi.fn(), push: vi.fn() }))
vi.mock('@/stores/rastreamento', () => ({ useRastreamentoStore: () => ({ obterResumoDashboard: summary }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: 'ADMIN' } }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
let app: App, container: HTMLDivElement
const shipment = (id: string, status = 'PENDENTE', ativo = true) => ({ id, codigo_rastreio: id, status, ativo, destinatario: id, historico_eventos: [] })
async function mount(rows: ReturnType<typeof shipment>[]) {
  summary.mockResolvedValue({ total_rastreamentos: 10, entregues: 5, rastreamentos_recentes: rows })
  container = document.createElement('div'); document.body.append(container)
  app = createApp(RastreamentoCard); app.config.globalProperties.$tr = uiText; app.mount(container)
  await Promise.resolve(); await Promise.resolve(); await nextTick()
}
afterEach(() => { app.unmount(); container.remove(); vi.clearAllMocks() })

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
})
