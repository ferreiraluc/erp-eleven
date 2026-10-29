import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import Panel from './WoncaMonitoringPanel.vue'
const mocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), auth: { token: 'synthetic', isOwner: true } }))
vi.mock('@/services/api', () => ({ default: mocks }))
let auth = reactive(mocks.auth)
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/components/ui/ErpSelect.vue', () => ({ default: { props: ['modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' } }))
let app: App, root: HTMLElement
const flush = async () => { await nextTick(); await nextTick(); await nextTick() }
const state = { configured: true, enabled: true, api_key_configured: true, endpoint_id: 'endpoint', profile_id: 'profile', interval_hours: 2, daytime_only: true, subscriptions: { active: 3, paused: 2 }, failed_subscriptions: 0 }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(Panel).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root); await flush()
}
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks(); auth.token = 'synthetic'; auth.isOwner = true })
it('shows the overnight window and requires consumption consent before enabling', async () => {
  mocks.get.mockResolvedValue({ data: state }); mocks.put.mockResolvedValue({ data: state })
  await mount()
  expect(root.textContent).toContain('21h às 07h')
  const submit = root.querySelector<HTMLButtonElement>('button')!
  expect(submit.disabled).toBe(true)
  const checkboxes = root.querySelectorAll<HTMLInputElement>('[type=checkbox]')
  expect(checkboxes[1].checked).toBe(true)
  checkboxes[2].click(); await flush(); expect(submit.disabled).toBe(false)
  root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush()
  expect(mocks.put).toHaveBeenCalledWith('/api/tracking-monitor/config', expect.objectContaining({ enabled: true, interval_hours: 2, daytime_only: true, monitor_days: 30, confirm_monitoring: true }), expect.anything())
  expect(mocks.put.mock.calls[0][1]).not.toHaveProperty('signing_secret')
})
it('clears a newly entered secret after save and never renders it as text', async () => {
  mocks.get.mockResolvedValue({ data: state }); mocks.put.mockResolvedValue({ data: state })
  await mount()
  const password = root.querySelector<HTMLInputElement>('[type=password]')!
  password.value = 'synthetic-private-secret'; password.dispatchEvent(new Event('input'))
  root.querySelectorAll<HTMLInputElement>('[type=checkbox]')[2].click(); await flush()
  root.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush()
  expect(mocks.put.mock.calls[0][1].signing_secret).toBe('synthetic-private-secret')
  expect(password.value).toBe(''); expect(root.textContent).not.toContain('synthetic-private-secret')
})
it('discards late responses and secret fields after account changes', async () => {
  let resolve!: (value: unknown) => void
  mocks.get.mockReturnValue(new Promise(r => { resolve = r }))
  await mount(); auth.token = 'different-user'; await flush()
  resolve({ data: state }); await flush()
  expect(root.querySelector('form')).toBeNull()
  expect(root.textContent).not.toContain('endpoint')
})
it('offers a visible error instead of pretending configuration was saved', async () => {
  mocks.get.mockRejectedValue(new Error('offline')); await mount()
  expect(root.querySelector('[role=alert]')).not.toBeNull()
  expect(root.querySelector('form')).toBeNull()
})
