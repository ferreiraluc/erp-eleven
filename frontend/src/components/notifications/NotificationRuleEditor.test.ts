import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, ref, type App } from 'vue'
import i18n from '@/i18n'
import type { NotificationRule, NotificationTemplate } from '@/services/notifications'
import NotificationRuleEditor from './NotificationRuleEditor.vue'

const mocks = vi.hoisted(() => ({
  auth: {} as { isOwner: boolean; token: string | null },
  rule: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/services/notifications', () => ({ notificationsAPI: { rule: mocks.rule } }))

let app: App | undefined, root: HTMLElement
const currentRule = ref<NotificationRule>()
const saved = vi.fn()
const users = [
  { id: 'lucas', nome: 'Lucas' },
  { id: 'sol', nome: 'Sol' },
  { id: 'junior', nome: 'Junior' },
]
const template: NotificationTemplate = {
  id: 'template', name: 'Aviso de teste', title: 'Aviso', body: 'Confira no sistema.',
  category: 'sales', severity: 'info', requires_ack: false, requires_response: false,
  action_path: null, version: 1,
}
function fixture(event = 'sale_completed', ids: string[] = []): NotificationRule {
  return {
    event_key: event, enabled: true, template_id: template.id, user_ids: ids,
    local_time: '09:00', weekdays: [0, 1, 2, 3, 4, 5, 6], version: 3,
  }
}
async function mount(event?: string, ids?: string[]) {
  currentRule.value = fixture(event, ids)
  root = document.createElement('div')
  document.body.append(root)
  app = createApp({
    setup: () => () => h(NotificationRuleEditor, {
      rule: currentRule.value!, templates: [template], users, onSaved: saved,
    }),
  })
  app.mount(root)
  await nextTick()
}
function recipient(id: string) {
  return root.querySelector<HTMLInputElement>(`input[type="checkbox"][value="${id}"]`)!
}
async function select(id: string, value = true) {
  const input = recipient(id)
  input.checked = value
  input.dispatchEvent(new Event('change', { bubbles: true }))
  await nextTick()
}
function saveButton() {
  return Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(
    button => button.textContent?.trim() === 'Salvar alterações',
  )!
}
beforeEach(() => {
  vi.resetAllMocks()
  i18n.global.locale.value = 'pt'
  mocks.auth = reactive({ isOwner: true, token: 'owner-session' })
  mocks.rule.mockResolvedValue({})
})
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
  i18n.global.locale.value = 'pt'
})

describe('Notification rule recipients', () => {
  it('sends every selected user and retains the selection when the saved rule reloads', async () => {
    await mount('tracking_status_changed', ['lucas'])
    await select('sol')
    await select('junior')
    saved.mockImplementation(() => {
      const payload = mocks.rule.mock.calls[0][1]
      currentRule.value = { ...fixture('tracking_status_changed'), ...payload, version: 4 }
    })
    saveButton().click()
    await vi.waitFor(() => expect(saved).toHaveBeenCalledOnce())
    await nextTick()
    expect(mocks.rule).toHaveBeenCalledWith('tracking_status_changed', {
      expected_version: 3, enabled: true, template_id: 'template', local_time: '09:00',
      weekdays: [0, 1, 2, 3, 4, 5, 6], user_ids: ['lucas', 'sol', 'junior'],
    }, 'owner-session')
    expect(users.every(user => recipient(user.id).checked)).toBe(true)
    expect(root.querySelector('summary')?.textContent).toContain('3')
    expect(saveButton().disabled).toBe(true)
  })

  it('sends an empty selection to restore event defaults', async () => {
    await mount('sale_completed', ['lucas', 'sol'])
    await select('lucas', false)
    await select('sol', false)
    saveButton().click()
    await vi.waitFor(() => expect(mocks.rule).toHaveBeenCalledOnce())
    expect(mocks.rule.mock.calls[0][1].user_ids).toEqual([])
    expect(root.querySelector('summary')?.textContent).toContain('Padrão do evento')
  })

  it('keeps selected users visible after a version conflict rather than showing saved state', async () => {
    mocks.rule.mockRejectedValueOnce({ response: { status: 409 } })
    await mount()
    await select('sol')
    saveButton().click()
    await vi.waitFor(() => expect(root.querySelector('[role="alert"]')).toBeTruthy())
    expect(recipient('sol').checked).toBe(true)
    expect(saved).not.toHaveBeenCalled()
    expect(saveButton().disabled).toBe(false)
  })

  it.each([
    ['sale_completed', 'somente Lucas recebe', true],
    ['sale_avulso_without_reason', 'Lucas e o vendedor daquela venda', true],
    ['sale_receipt_problem', 'Lucas e o vendedor daquela venda', true],
    ['tracking_status_changed', 'Lucas e quem cadastrou o rastreio', false],
    ['morning_greeting', 'todos os usuários ativos', false],
  ])('explains defaults and sales scope for %s', async (event, defaultText, sales) => {
    await mount(event)
    const help = root.querySelector('details')!.textContent!
    expect(help).toContain('Os usuários marcados substituem os destinatários padrão')
    expect(help).toContain(defaultText)
    expect(help.includes('quem consulta apenas as próprias vendas')).toBe(sales)
    expect(help.includes('quem tem acesso geral')).toBe(sales)
    expect(help.includes('Marcar um usuário não altera suas permissões')).toBe(sales)
  })

  it.each([
    ['es', 'sustituyen a los destinatarios predeterminados', 'no cambia sus permisos'],
    ['en', 'replace the default recipients', 'does not change their permissions'],
  ] as const)('explains explicit selection and scope in %s', async (locale, selection, scope) => {
    i18n.global.locale.value = locale
    await mount()
    expect(root.querySelector('details')!.textContent).toContain(selection)
    expect(root.querySelector('details')!.textContent).toContain(scope)
  })
})
