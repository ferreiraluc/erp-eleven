import { afterEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import DirectoryDuplicatesModal from './DirectoryDuplicatesModal.vue'
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/services/api', () => ({ default: mocks }))
let app: App, root: HTMLElement
const pair = {
  target: { id: 'one', name: 'Ana Silva', details: 'Dados principais' },
  source: { id: 'two', name: 'ANA SILVA', details: 'Dados duplicados' },
}
const flush = async () => {
  await nextTick()
  await nextTick()
  await nextTick()
}
const button = (name: string) =>
  Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(
    (button) => button.textContent?.trim() === name,
  )!
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.resetAllMocks()
})
async function mount() {
  mocks.get.mockResolvedValue({ data: { items: [pair], incomplete: false } })
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(DirectoryDuplicatesModal)
  app.mount(root)
  await flush()
}
it('requires an explicit preview and identity check before confirming the selected direction', async () => {
  await mount()
  expect(mocks.post).not.toHaveBeenCalled()
  button('Conferir par').click()
  await flush()
  button('Inverter principal').click()
  await flush()
  mocks.post.mockResolvedValueOnce({
    data: {
      state: 'ready',
      plan_token: 'x'.repeat(64),
      links_to_move: { orders: 2 },
      conflicting_fields: [],
    },
  })
  button('Revisar união').click()
  await flush()
  expect(mocks.post).toHaveBeenCalledWith(expect.stringContaining('/preview'), {
    kind: 'customers',
    target_id: 'two',
    source_id: 'one',
  })
  expect(button('Unir cadastros conferidos').disabled).toBe(true)
  document.querySelector<HTMLInputElement>('.review-check input')!.click()
  await flush()
  mocks.post.mockResolvedValueOnce({ data: { state: 'merged' } })
  button('Unir cadastros conferidos').click()
  await flush()
  expect(mocks.post).toHaveBeenLastCalledWith(
    expect.stringContaining('/confirm'),
    expect.objectContaining({
      confirm: true,
      target_id: 'two',
      source_id: 'one',
      plan_token: 'x'.repeat(64),
    }),
  )
  expect(document.body.textContent).toContain('Cadastros unidos. Históricos preservados.')
})
it('blocks conflicts and clears an obsolete preview after a stale response', async () => {
  await mount()
  button('Conferir par').click()
  await flush()
  mocks.post.mockResolvedValueOnce({
    data: { state: 'review_conflicts', conflicting_fields: ['cpf'] },
  })
  button('Revisar união').click()
  await flush()
  expect(button('Unir cadastros conferidos')).toBeUndefined()
  button('Inverter principal').click()
  await flush()
  mocks.post.mockResolvedValueOnce({ data: { state: 'ready', plan_token: 'x'.repeat(64) } })
  button('Revisar união').click()
  await flush()
  document.querySelector<HTMLInputElement>('.review-check input')!.click()
  await flush()
  mocks.post.mockRejectedValueOnce({
    response: { data: { detail: 'Os cadastros mudaram. Confira novamente.' } },
  })
  button('Unir cadastros conferidos').click()
  await flush()
  expect(button('Unir cadastros conferidos')).toBeUndefined()
  expect(button('Revisar união')).toBeDefined()
  expect(document.querySelector('[role=alert]')?.textContent).toContain('mudaram')
})

it('recovers a previously confirmed merge without submitting another confirmation', async () => {
  await mount()
  button('Conferir par').click()
  await flush()
  mocks.post.mockResolvedValueOnce({ data: { state: 'already_merged' } })
  button('Revisar união').click()
  await flush()
  expect(mocks.post).toHaveBeenCalledTimes(1)
  expect(document.body.textContent).toContain('Cadastros unidos. Históricos preservados.')
  expect(button('Unir cadastros conferidos')).toBeUndefined()
})
