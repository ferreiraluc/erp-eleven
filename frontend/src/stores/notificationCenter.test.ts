import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, reactive } from 'vue'
import { useNotificationCenter } from './notificationCenter'
import type { NotificationItem } from '@/services/notifications'
const mocks = vi.hoisted(() => ({
  auth: {} as { isAuthenticated: boolean; token: string | null; user: { id: string } | null },
  inbox: vi.fn(),
  preferences: vi.fn(),
  savePreferences: vi.fn(),
  read: vi.fn(),
  acknowledge: vi.fn(),
  readAll: vi.fn(),
  restore: vi.fn(),
  clear: vi.fn(),
  enable: vi.fn(),
  disable: vi.fn(),
  sound: vi.fn(),
  allowSound: vi.fn(),
  support: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/services/notifications', () => ({
  notificationsAPI: {
    inbox: mocks.inbox,
    preferences: mocks.preferences,
    savePreferences: mocks.savePreferences,
    read: mocks.read,
    acknowledge: mocks.acknowledge,
    readAll: mocks.readAll,
  },
}))
vi.mock('@/services/notificationPush', () => ({
  restoreNotificationDevice: mocks.restore,
  clearNotificationDevice: mocks.clear,
  enableNotificationDevice: mocks.enable,
  disableNotificationDevice: mocks.disable,
  playNotificationSound: mocks.sound,
  allowNotificationSound: mocks.allowSound,
  pushSupport: mocks.support,
}))
const preferences = {
  push_enabled: true,
  sound_enabled: false,
  categories: ['manual', 'sales', 'tracking', 'reminder', 'greeting'],
}
let store: ReturnType<typeof useNotificationCenter> | undefined
const item = (id: string): NotificationItem => ({
  id,
  title: 'Revisar venda',
  body: 'Informe motivo',
  category: 'sales',
  severity: 'warning',
  action_path: '/vendas-pdv',
  requires_ack: true,
  requires_response: true,
  created_at: '2026-10-26T13:00:00Z',
  published_at: '2026-10-26T13:00:00Z',
  scheduled_at: null,
  read_at: null,
  acknowledged_at: null,
  version: 2,
  cancelled_at: null,
})
const tick = async () => {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
}
beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  setActivePinia(createPinia())
  mocks.auth = reactive({ isAuthenticated: true, token: 'token-sol', user: { id: 'sol' } })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  mocks.inbox.mockResolvedValue({ items: [item('one')], total: 1, unread_count: 1 })
  mocks.preferences.mockResolvedValue(preferences)
  mocks.savePreferences.mockImplementation(async (value) => value)
  mocks.restore.mockResolvedValue(false)
  mocks.support.mockReturnValue('ready')
  mocks.enable.mockResolvedValue(undefined)
  mocks.acknowledge.mockResolvedValue({})
  mocks.read.mockResolvedValue({})
  mocks.readAll.mockResolvedValue({})
})
afterEach(() => {
  store?.$dispose()
  store = undefined
  vi.useRealTimers()
})
describe('Notification center', () => {
  it('reconnects an already permitted device on each login without invoking a permission prompt', async () => {
    mocks.restore.mockResolvedValue(true)
    store = useNotificationCenter(); await tick()
    expect(store.pushActive).toBe(true); expect(store.invitation).toBe(false)
    mocks.auth.token = 'next-login-token'; await tick()
    expect(mocks.restore).toHaveBeenLastCalledWith('sol', 'next-login-token')
    expect(store.pushActive).toBe(true); expect(mocks.enable).not.toHaveBeenCalled()
  })
  it('retries a failed restoration after reconnecting while retaining company defaults', async () => {
    vi.useFakeTimers()
    mocks.restore.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(true)
    mocks.preferences.mockResolvedValue({ push_enabled: false, sound_enabled: false, categories: [] })
    store = useNotificationCenter(); await tick()
    expect(store.pushActive).toBe(false); expect(store.pushError).toContain('reconectar')
    expect(store.prefs).toMatchObject({ push_enabled: true, sound_enabled: true, categories: preferences.categories })
    Object.defineProperty(navigator, 'onLine', { value: false }); window.dispatchEvent(new Event('offline'))
    await vi.advanceTimersByTimeAsync(45000)
    expect(mocks.restore).toHaveBeenCalledOnce()
    Object.defineProperty(navigator, 'onLine', { value: true }); window.dispatchEvent(new Event('online')); await tick()
    expect(store.pushActive).toBe(true); expect(store.pushError).toBe(''); expect(store.invitation).toBe(false)
    expect(mocks.enable).not.toHaveBeenCalled()
  })
  it('invites on the next opening and only activates permission after an explicit enable action', async () => {
    store = useNotificationCenter()
    await tick()
    expect(store.invitation).toBe(true)
    expect(mocks.enable).not.toHaveBeenCalled()
    store.enablePush()
    expect(mocks.enable).toHaveBeenCalledWith('sol', 'token-sol')
    await tick()
    expect(store.pushActive).toBe(true)
    expect(store.invitation).toBe(false)
  })
  it('dismisses only the current invitation without creating a device opt-out, and prompts a new session', async () => {
    store = useNotificationCenter()
    await tick()
    store.deferInvitation()
    expect(localStorage.getItem('eleven-push-invite-v1:sol')).toBeNull()
    mocks.auth.token = 'new-token-sol'
    await tick()
    expect(store.invitation).toBe(true)
  })
  it('discards old inbox, preference and push restore results after account switching', async () => {
    let resolveInbox!: (value: unknown) => void,
      resolveRestore!: (value: boolean) => void,
      resolvePreferences!: (value: unknown) => void
    mocks.inbox.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveInbox = resolve
      }),
    )
    mocks.restore.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRestore = resolve
      }),
    )
    mocks.preferences.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePreferences = resolve
      }),
    )
    store = useNotificationCenter()
    mocks.auth.user = { id: 'lucas' }
    mocks.auth.token = 'token-lucas'
    await tick()
    resolveInbox({ items: [item('private-sol')], total: 1, unread_count: 99 })
    resolveRestore(true)
    resolvePreferences({ ...preferences, sound_enabled: true })
    await tick()
    expect(store.items.map((value) => value.id)).toEqual(['one'])
    expect(store.unread).toBe(1)
    expect(store.pushActive).toBe(false)
    expect(store.prefs.sound_enabled).toBe(true)
    expect(mocks.clear).toHaveBeenCalled()
  })
  it('never polls while hidden or offline and resumes once visible', async () => {
    vi.useFakeTimers()
    store = useNotificationCenter()
    await tick()
    expect(mocks.inbox).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'visibilityState', { value: 'hidden' })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(90000)
    expect(mocks.inbox).toHaveBeenCalledTimes(1)
    Object.defineProperty(document, 'visibilityState', { value: 'visible' })
    Object.defineProperty(navigator, 'onLine', { value: false })
    window.dispatchEvent(new Event('offline'))
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(90000)
    expect(mocks.inbox).toHaveBeenCalledTimes(1)
    Object.defineProperty(navigator, 'onLine', { value: true })
    window.dispatchEvent(new Event('online'))
    await tick()
    expect(mocks.inbox).toHaveBeenCalledTimes(2)
  })
  it('submits acknowledgement note with the displayed version and initiating token', async () => {
    store = useNotificationCenter()
    await tick()
    await store.act('one', 'ack', 'Cliente pediu lançamento avulso', 2)
    expect(mocks.acknowledge).toHaveBeenCalledWith(
      'one',
      'Cliente pediu lançamento avulso',
      2,
      'token-sol',
    )
  })
  it('shows failures without claiming success or changing preferences', async () => {
    store = useNotificationCenter()
    await tick()
    mocks.enable.mockRejectedValueOnce(new Error('denied'))
    mocks.support.mockReturnValue('denied')
    store.enablePush()
    await tick()
    expect(store.pushActive).toBe(false)
    expect(store.pushError).toContain('bloqueadas')
    mocks.savePreferences.mockRejectedValueOnce(new Error('offline'))
    await store.preferences({ ...store.prefs, sound_enabled: true })
    expect(store.prefs.sound_enabled).toBe(true)
    expect(store.error).toContain('Não foi possível salvar')
  })
  it('does not play a startup sound, only for newly arriving unread notifications after initialization', async () => {
    mocks.preferences.mockResolvedValue({ ...preferences, sound_enabled: true })
    store = useNotificationCenter()
    await tick()
    expect(mocks.sound).not.toHaveBeenCalled()
    mocks.inbox.mockResolvedValue({ items: [item('two'), item('one')], total: 2, unread_count: 2 })
    await store.load()
    expect(mocks.sound).toHaveBeenCalledOnce()
    await store.load()
    expect(mocks.sound).toHaveBeenCalledOnce()
  })
})
