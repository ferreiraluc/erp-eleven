import { afterEach, expect, it } from 'vitest'
import { createApp, h, ref, nextTick, type App } from 'vue'
import ErpDropdown from './ErpDropdown.vue'
let app: App, root: HTMLDivElement
const flush = async () => {
  await nextTick()
  await nextTick()
}
async function mount(editable = true) {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp({
    setup() {
      const value = ref('')
      return () =>
        h('div', [
          h(ErpDropdown, {
            modelValue: value.value,
            'onUpdate:modelValue': v => (value.value = String(v ?? '')),
            options: [
              { value: 'Boss', label: 'Boss' },
              { value: 'Prada', label: 'Prada' },
            ],
            label: 'Marca',
            editable,
          }),
          h('output', value.value),
          h('button', { id: 'outside' }, 'Fora'),
        ])
    },
  })
  app.mount(root)
  await flush()
}
afterEach(() => {
  app?.unmount()
  root?.remove()
})
it('commits a tapped option after a mobile blur with no related target', async () => {
  await mount()
  root.querySelector<HTMLButtonElement>('.erp-dropdown__arrow')!.click()
  await flush()
  root
    .querySelector('input')!
    .dispatchEvent(new FocusEvent('focusout', { bubbles: true, relatedTarget: null }))
  await flush()
  const option = document.querySelector<HTMLButtonElement>('[role=option]')!
  option.click()
  await flush()
  expect(root.querySelector('output')?.textContent).toBe('Boss')
  expect(document.querySelector('[role=listbox]')).toBeNull()
  expect(root.querySelector<HTMLInputElement>('input')!.value).toBe('Boss')
})
it('allows free text, filters suggestions and isolates keyboard Enter from the parent form', async () => {
  await mount()
  const input = root.querySelector('input')!
  input.value = 'pra'
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await flush()
  expect(document.querySelector('[role=option]')?.textContent).toContain('Prada')
  const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
  input.dispatchEvent(event)
  await flush()
  expect(event.defaultPrevented).toBe(true)
  expect(root.querySelector('output')?.textContent).toBe('Prada')
})
it('supports keyboard selection and Escape without closing its parent dialog', async () => {
  await mount(false)
  const trigger = root.querySelector('.erp-dropdown__value')!
  trigger.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }),
  )
  await flush()
  expect(document.activeElement?.textContent).toContain('Boss')
  document.activeElement!.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }),
  )
  expect(document.activeElement?.textContent).toContain('Prada')
  document.activeElement!.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
  )
  await flush()
  expect(document.querySelector('[role=listbox]')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})
