import { afterEach, describe, expect, it } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import type { NotificationRecipientUser } from '@/services/notifications'
import NotificationComposer, { type NotificationForm } from './NotificationComposer.vue'

let app: App | undefined, root: HTMLElement
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
})

describe('Manual notification recipients', () => {
  it('cleans an existing draft and removes a selected employee after their profile changes', async () => {
    const users = ref<NotificationRecipientUser[]>([
      { id: 'sol', nome: 'Sol' },
      { id: 'junior', nome: 'Junior', access_profile: 'standard' },
      { id: 'reseller', nome: 'Revendedor', access_profile: 'reseller' },
    ])
    const form = ref<NotificationForm>({
      name: '', title: 'Aviso', body: 'Confira no sistema.', category: 'manual', severity: 'info',
      action_path: '', requires_ack: false, requires_response: false,
      user_ids: ['sol', 'junior', 'reseller'], scheduled_at: '',
    })
    root = document.createElement('div')
    document.body.append(root)
    app = createApp({
      setup: () => () => h(NotificationComposer, {
        modelValue: form.value,
        'onUpdate:modelValue': value => { form.value = value },
        users: users.value,
      }),
    })
    app.mount(root)
    await nextTick()
    expect(form.value.user_ids).toEqual(['sol', 'junior'])
    expect(root.querySelector('input[value="reseller"]')).toBeNull()
    users.value[1].access_profile = 'reseller'
    await nextTick()
    expect(form.value.user_ids).toEqual(['sol'])
    expect(root.querySelector('input[value="junior"]')).toBeNull()
    expect(root.querySelector<HTMLInputElement>('input[value="sol"]')?.checked).toBe(true)
  })
})
