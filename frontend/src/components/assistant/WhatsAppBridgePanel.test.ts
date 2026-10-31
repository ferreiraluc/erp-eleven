import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import WhatsAppBridgePanel from './WhatsAppBridgePanel.vue'
import type { WhatsAppBridgeConfig } from '@/services/whatsappBridge'

const mocks = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn(), credential: vi.fn(), pairing: vi.fn(), reset: vi.fn() }))
vi.mock('@/services/whatsappBridge', () => ({ getWhatsAppBridge: mocks.get, saveWhatsAppBridge: mocks.save, createWhatsAppBridgeCredential: mocks.credential, getWhatsAppBridgePairing: mocks.pairing, resetWhatsAppBridgeSession: mocks.reset }))
vi.mock('@/components/ui/ErpSelect.vue', () => ({ default: { props: ['modelValue'], emits: ['update:modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' } }))
vi.mock('@/i18n/uiText', () => ({ uiText: (s: string) => s, uiLocale: () => 'pt-BR' }))
const base: WhatsAppBridgeConfig = { name: 'WhatsApp Eleven', enabled: false, allow_private: true, notify_tracking: false, group_mode: 'mention', allowed_groups: [], discovered_groups: [{ id: '1234567890@g.us', name: 'Equipe Eleven' }], state: 'disconnected', account_phone: null, last_seen_at: null, credential_configured: false }
let app: App, root: HTMLElement
const settle = async () => { await Promise.resolve(); await nextTick(); await Promise.resolve(); await nextTick() }
const button = (text: string) => Array.from(root.querySelectorAll('button')).find(b => b.textContent?.includes(text))!
async function mount() { root = document.createElement('div'); document.body.append(root); app = createApp(WhatsAppBridgePanel); app.mount(root); await settle() }
beforeEach(() => { vi.useFakeTimers(); vi.resetAllMocks(); vi.spyOn(document, 'hidden', 'get').mockReturnValue(false); mocks.get.mockResolvedValue(structuredClone(base)); mocks.save.mockImplementation(async (body) => ({ ...base, ...body })); mocks.pairing.mockResolvedValue({ qr_image: null, expires_at: null }) })
afterEach(() => { app?.unmount(); root?.remove(); vi.restoreAllMocks(); vi.useRealTimers() })

describe('WhatsApp team connection', () => {
  it('discovers new groups while preserving unsaved group and response settings', async () => {
    await mount()
    root.querySelector<HTMLInputElement>('fieldset input')!.click()
    const mode = root.querySelector<HTMLSelectElement>('select')!
    mode.value = 'all_authorized'; mode.dispatchEvent(new Event('change')); await nextTick()
    mocks.get.mockResolvedValue({ ...base, discovered_groups: [...base.discovered_groups, { id: '9876543210@g.us', name: 'Pedidos e Endereços' }] })
    await vi.advanceTimersByTimeAsync(10000)
    expect(root.textContent).toContain('Pedidos e Endereços')
    const groups = root.querySelectorAll<HTMLInputElement>('fieldset input')
    expect(groups[0].checked).toBe(true)
    expect(groups[1].checked).toBe(false)
    expect(mode.value).toBe('all_authorized')
    expect(mocks.save).not.toHaveBeenCalled()
    button('Atualizar').click(); await settle()
    expect(groups[0].checked).toBe(true)
    root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle()
    expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({ group_mode: 'all_authorized', allowed_groups: ['1234567890@g.us'] }))
  })
  it('pauses polling when hidden and stops after unmount', async () => {
    await mount()
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(30000)
    expect(mocks.get).toHaveBeenCalledTimes(1)
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    document.dispatchEvent(new Event('visibilitychange')); await settle()
    expect(mocks.get).toHaveBeenCalledTimes(2)
    app.unmount()
    await vi.advanceTimersByTimeAsync(30000)
    expect(mocks.get).toHaveBeenCalledTimes(2)
  })
  it('retains known groups on failure and explains automatic retry without showing provider details', async () => {
    await mount()
    mocks.get.mockRejectedValue(new Error('private provider detail'))
    await vi.advanceTimersByTimeAsync(10000)
    expect(root.textContent).toContain('Equipe Eleven')
    expect(root.textContent).toContain('A lista anterior foi mantida')
    expect(root.textContent).not.toContain('private provider detail')
    mocks.get.mockResolvedValue({ ...base, error_code: 'group_sync_retry' })
    await vi.advanceTimersByTimeAsync(10000)
    expect(root.textContent).not.toContain('A lista anterior foi mantida')
    expect(root.textContent).toContain('O agente tentará novamente automaticamente')
  })
  it('clears an initial connection error after polling recovers', async () => {
    mocks.get.mockRejectedValueOnce(new Error('network'))
    await mount()
    expect(root.textContent).toContain('Não foi possível atualizar a conexão')
    await vi.advanceTimersByTimeAsync(10000)
    expect(root.textContent).toContain('Equipe Eleven')
    expect(root.textContent).not.toContain('Não foi possível atualizar a conexão')
  })
  it('ignores a background response started before a configuration save', async () => {
    await mount()
    let resolve!: (value: WhatsAppBridgeConfig) => void
    mocks.get.mockReturnValueOnce(new Promise(r => { resolve = r }))
    await vi.advanceTimersByTimeAsync(10000)
    root.querySelector<HTMLInputElement>('fieldset input')!.click(); await nextTick()
    root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle()
    resolve({ ...base, discovered_groups: [] }); await settle()
    expect(root.textContent).toContain('Equipe Eleven')
    expect(root.querySelector<HTMLInputElement>('fieldset input')!.checked).toBe(true)
  })
  it('cannot revert credential confirmation after a stale background response', async () => {
    await mount()
    let resolve!: (value: WhatsAppBridgeConfig) => void
    mocks.get.mockReturnValueOnce(new Promise(r => { resolve = r }))
    await vi.advanceTimersByTimeAsync(10000)
    mocks.credential.mockResolvedValue({ token: 'isolated-test-token' })
    root.querySelector('details')!.open = true
    button('Gerar credencial').click(); await settle()
    expect(button('Substituir credencial').disabled).toBe(true)
    resolve({ ...base, credential_configured: false }); await settle()
    expect(button('Substituir credencial').disabled).toBe(true)
    expect(mocks.credential).toHaveBeenCalledTimes(1)
  })
  it('keeps groups disabled until selected and saves only configuration fields', async () => {
    await mount()
    expect(root.textContent).toContain('Equipe Eleven')
    expect(mocks.pairing).not.toHaveBeenCalled()
    const group = root.querySelector<HTMLInputElement>('fieldset input')!
    expect(group.checked).toBe(false)
    group.click(); await nextTick()
    root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle()
    expect(mocks.save).toHaveBeenCalledWith({ name: base.name, enabled: false, allow_private: true, notify_tracking: false, group_mode: 'mention', allowed_groups: ['1234567890@g.us'] })
    expect(root.textContent).toContain('Configuração salva.')
  })
  it('shows QR only on request and erases it on expiry', async () => {
    mocks.pairing.mockResolvedValue({ qr_image: 'data:image/png;base64,fixture', expires_at: new Date(Date.now() + 1000).toISOString() })
    await mount(); button('Mostrar QR Code').click(); await settle()
    expect(root.querySelector('.wa-qr')?.getAttribute('src')).toBe('data:image/png;base64,fixture')
    await vi.advanceTimersByTimeAsync(1001)
    expect(root.querySelector('.wa-qr')).toBeNull()
    button('Ocultar QR Code').click(); await nextTick()
    await vi.advanceTimersByTimeAsync(10000)
    expect(mocks.pairing).toHaveBeenCalledTimes(1)
  })
  it('does not show a late QR after the user closes it or unmounts', async () => {
    let resolve!: (value: unknown) => void
    mocks.pairing.mockReturnValue(new Promise(r => { resolve = r }))
    await mount(); button('Mostrar QR Code').click(); await nextTick()
    button('Ocultar QR Code').click(); await nextTick()
    resolve({ qr_image: 'data:image/png;base64,fixture', expires_at: new Date(Date.now() + 60000).toISOString() }); await settle()
    expect(root.querySelector('.wa-qr')).toBeNull()
    expect(root.textContent).toContain('Mostrar QR Code')
  })
  it('requires explicit replacement of an existing credential and clears the one-time secret when hidden', async () => {
    mocks.get.mockResolvedValue({ ...base, credential_configured: true }); mocks.credential.mockResolvedValue({ token: 'isolated-test-token' })
    await mount()
    const details = root.querySelector('details')!; details.open = true
    expect(button('Substituir credencial').disabled).toBe(true)
    details.querySelector<HTMLInputElement>('input')!.click(); await nextTick()
    button('Substituir credencial').click(); await settle()
    expect(root.querySelector('textarea')?.value).toBe('isolated-test-token')
    expect(button('Substituir credencial').disabled).toBe(true)
    details.open = false; details.dispatchEvent(new Event('toggle')); await nextTick()
    expect(root.querySelector('textarea')).toBeNull()
  })
  it('rejects arbitrary QR URLs and shows connection failures without exposing stale images', async () => {
    mocks.pairing.mockResolvedValue({ qr_image: 'https://external.example/qr', expires_at: new Date(Date.now() + 60000).toISOString() })
    await mount(); button('Mostrar QR Code').click(); await settle()
    expect(root.querySelector('.wa-qr')).toBeNull()
    mocks.pairing.mockRejectedValue(new Error('private network detail'))
    await vi.advanceTimersByTimeAsync(5000)
    expect(root.textContent).toContain('Não foi possível atualizar')
    expect(root.textContent).not.toContain('private network detail')
  })
  it('closes pairing when the agent reports a recent connection', async () => {
    await mount()
    mocks.get.mockResolvedValue({ ...base, state: 'connected', last_seen_at: new Date().toISOString() })
    button('Mostrar QR Code').click(); await settle()
    expect(root.querySelector('.wa-qr')).toBeNull()
    expect(root.textContent).toContain('WhatsApp conectado.')
    await vi.advanceTimersByTimeAsync(10000)
    expect(mocks.pairing).toHaveBeenCalledTimes(1)
  })
  it('requires a deliberate reset and requests a new QR without changing access settings', async () => {
    mocks.reset.mockResolvedValue({ status: 'reset_requested' })
    await mount()
    const details = root.querySelectorAll('details')[1]
    expect(button('Preparar novo vínculo').disabled).toBe(true)
    details.querySelector<HTMLInputElement>('input')!.click(); await nextTick()
    button('Preparar novo vínculo').click(); await settle()
    expect(mocks.reset).toHaveBeenCalledTimes(1)
    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.pairing).toHaveBeenCalledTimes(1)
    expect(button('Preparar novo vínculo').disabled).toBe(true)
  })
})
