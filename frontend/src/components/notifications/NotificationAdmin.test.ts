import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import NotificationAdmin from './NotificationAdmin.vue'
const mocks = vi.hoisted(() => ({
  auth: {} as { isOwner: boolean; isAuthenticated: boolean; token: string | null },
  admin: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  cancel: vi.fn(),
  template: vi.fn(),
  rule: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/services/notifications', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/notifications')>()),
  notificationsAPI: {
    admin: mocks.admin,
    create: mocks.create,
    update: mocks.update,
    cancel: mocks.cancel,
    template: mocks.template,
    rule: mocks.rule,
  },
}))
let app: App | undefined, root: HTMLElement
const initial = () => ({
  items: [],
  total: 0,
  users: [
    { id: 'sol', nome: 'Sol' },
    { id: 'junior', nome: 'Junior' },
  ],
  templates: [],
  rules: [],
})
async function mount() {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(NotificationAdmin)
  app.mount(root)
  await vi.waitFor(() => expect(mocks.admin).toHaveBeenCalled())
  await nextTick()
}
function button(text: string) {
  const value = Array.from(root.querySelectorAll('button')).find((node) =>
    node.textContent?.includes(text),
  )
  expect(value, `button ${text}`).toBeTruthy()
  return value!
}
function input(node: HTMLInputElement | HTMLTextAreaElement, value: string) {
  node.value = value
  node.dispatchEvent(new Event('input', { bubbles: true }))
}
async function compose() {
  button('Novo recado').click()
  await nextTick()
  const form = root.querySelector('form')!
  input(form.querySelector('input[maxlength="120"]')!, 'Venda sem vínculo')
  input(form.querySelector('textarea')!, 'Informe o motivo do lançamento avulso.')
  const recipient = form.querySelector<HTMLInputElement>('input[type="checkbox"][value="sol"]')!
  recipient.checked = true
  recipient.dispatchEvent(new Event('change', { bubbles: true }))
  await nextTick()
  return form
}
beforeEach(() => {
  vi.resetAllMocks()
  mocks.auth = reactive({ isOwner: true, isAuthenticated: true, token: 'lucas-token' })
  mocks.admin.mockResolvedValue(initial())
  mocks.create.mockResolvedValue({})
  mocks.update.mockResolvedValue({})
})
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
})
describe('Owner notification editor', () => {
  it('requires title, content and recipient before sending', async () => {
    await mount()
    button('Novo recado').click()
    await nextTick()
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await nextTick()
    expect(mocks.create).not.toHaveBeenCalled()
    expect(root.textContent).toContain('pelo menos um destinatário')
  })
  it('sends plain text and preserves an idempotency key when retrying an uncertain result', async () => {
    await mount()
    mocks.create.mockRejectedValueOnce(new Error('network timeout'))
    const form = await compose()
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(root.textContent).toContain('Não foi possível salvar'))
    const original = mocks.create.mock.calls[0][0]
    expect(original).toMatchObject({
      title: 'Venda sem vínculo',
      user_ids: ['sol'],
      requires_ack: false,
      scheduled_at: null,
    })
    expect(mocks.create.mock.calls[0][1]).toBe('lucas-token')
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2))
    expect(mocks.create.mock.calls[1][0].request_id).toBe(original.request_id)
  })
  it('uses labelled destinations without asking the owner to copy a URL', async () => {
    await mount()
    const form = await compose()
    expect(form.querySelector('input[maxlength="500"]')).toBeNull()
    expect(form.querySelector('button[aria-label="Ao abrir o aviso"]')).toBeTruthy()
  })
  it('keeps the current draft mounted and locks authoring navigation during a slow send', async () => {
    let finish!: (value: unknown) => void
    mocks.create.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    await mount()
    const form = await compose()
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1))
    const tabs = Array.from(root.querySelectorAll<HTMLButtonElement>('button[role=tab]'))
    expect(tabs.every(tab => tab.disabled)).toBe(true)
    tabs[1].click()
    await nextTick()
    expect(root.querySelector('form')).toBe(form)
    expect(form.querySelector<HTMLTextAreaElement>('textarea')!.value).toContain('lançamento avulso')
    finish({})
    await vi.waitFor(() => expect(root.querySelector('form')).toBeNull())
    expect(tabs.every(tab => !tab.disabled)).toBe(true)
  })
  it('makes a mandatory response also require acknowledgement', async () => {
    await mount()
    const form = await compose(),
      checks = form.querySelectorAll<HTMLInputElement>('input[type=checkbox]')
    checks[1].checked = true
    checks[1].dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    expect(checks[0].checked).toBe(true)
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0]).toMatchObject({
      requires_ack: true,
      requires_response: true,
    })
  })
  it('clears private editor state and ignores a late owner request after switching users', async () => {
    let finish!: (value: unknown) => void
    mocks.admin.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    await mount()
    mocks.auth.isOwner = false
    mocks.auth.token = 'sol-token'
    finish({ ...initial(), items: [{ id: 'private', title: 'Private owner notice' }] })
    await nextTick()
    await Promise.resolve()
    expect(root.textContent).toBe('')
    expect(mocks.create).not.toHaveBeenCalled()
  })
})
