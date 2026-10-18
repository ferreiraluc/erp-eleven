import { afterEach, expect, it, vi } from 'vitest'
import { createApp, h, Fragment, nextTick, ref, type App } from 'vue'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import ErpSelect from './ErpSelect.vue'
import ErpDropdown from './ErpDropdown.vue'
import type { DropdownValue } from './dropdownOptions'
import { chooseDropdown, openDropdown } from '@/test/dropdown'
import { vErpDialog } from '@/directives/erpDialog'
import { withDirectives } from 'vue'
let app: App, root: HTMLDivElement
const tick = async () => {
  await nextTick()
  await nextTick()
}
function mount(render: () => ReturnType<typeof h>) {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp({ render })
  app.mount(root)
}
afterEach(() => {
  app?.unmount()
  root?.remove()
  vi.restoreAllMocks()
})
it('preserves false, zero, null and numeric values and emits one change with the updated model', async () => {
  const value = ref<DropdownValue>(null),
    change = vi.fn((v) => expect(value.value).toBe(v))
  mount(() =>
    h(
      ErpSelect,
      {
        modelValue: value.value,
        'onUpdate:modelValue': (v) => (value.value = v),
        onChange: change,
        label: 'Valor',
      },
      {
        default: () => [
          h(Fragment, [
            h('option', { value: null }, 'Todos'),
            h('option', { value: false }, 'Arquivados'),
            h('option', { value: 0 }, 'Zero'),
            h('option', { value: 25 }, '25 itens'),
          ]),
        ],
      },
    ),
  )
  for (const [serialized, expected] of [
    ['false', false],
    ['0', 0],
    ['25', 25],
    ['', null],
  ] as const) {
    await chooseDropdown(root, serialized)
    expect(value.value).toBe(expected)
  }
  expect(change).toHaveBeenCalledTimes(4)
  expect(root.querySelector('select')).toBeNull()
})
it('refreshes asynchronous options, translations and disabled groups without losing selection', async () => {
  const rows = ref<string[]>([]),
    label = ref('Todos'),
    value = ref<DropdownValue>('')
  mount(() =>
    h(
      ErpSelect,
      { modelValue: value.value, 'onUpdate:modelValue': (v) => (value.value = v) },
      {
        default: () => [
          h('option', { value: '' }, label.value),
          h(
            Fragment,
            rows.value.map((v) => h('option', { value: v }, v)),
          ),
          h('optgroup', { label: 'Inativos', disabled: true }, [
            h('option', { value: 'hidden' }, 'Oculto'),
          ]),
        ],
      },
    ),
  )
  rows.value = ['Lucas', 'Wissam']
  await tick()
  await chooseDropdown(root, 'Wissam')
  expect(value.value).toBe('Wissam')
  const options = await openDropdown(root)
  expect(options.at(-1)?.disabled).toBe(true)
  label.value = 'All'
  await tick()
  expect(document.querySelector('[role=option]')?.textContent).toBe('All')
  expect(root.textContent).toContain('Wissam')
})
it('keeps required validation, named form data, disabled controls and keyboard focus', async () => {
  const value = ref<DropdownValue>(''),
    disabled = ref(false)
  mount(() =>
    h('form', [
      h(
        ErpSelect,
        {
          required: true,
          name: 'seller',
          disabled: disabled.value,
          modelValue: value.value,
          'onUpdate:modelValue': (v) => (value.value = v),
          label: 'Vendedor',
        },
        {
          default: () => [
            h('option', { value: '' }, 'Selecione'),
            h('option', { value: 'seller-1' }, 'Lucas'),
          ],
        },
      ),
    ]),
  )
  const form = root.querySelector('form')!
  expect(form.checkValidity()).toBe(false)
  await tick()
  expect(document.activeElement).toBe(root.querySelector('button'))
  expect(root.querySelector('[role=alert]')).not.toBeNull()
  await chooseDropdown(root, 'seller-1')
  expect(form.checkValidity()).toBe(true)
  expect(new FormData(form).get('seller')).toBe('seller-1')
  disabled.value = true
  await tick()
  expect(root.querySelector('button')?.disabled).toBe(true)
  expect(new FormData(form).has('seller')).toBe(false)
})
it('puts a searchable menu above a clipped modal, keeps pointer selection and closes only that popup on Escape', async () => {
  const value = ref<DropdownValue>('1'),
    close = vi.fn()
  mount(() =>
    h('div', { class: 'erp-dialog-backdrop', style: 'z-index:3100' }, [
      withDirectives(
        h('form', { style: 'overflow:hidden' }, [
          h('button', { type: 'button', 'data-dialog-close': '', onClick: close }, 'Fechar'),
          h(
            ErpSelect,
            {
              label: 'Modelo',
              modelValue: value.value,
              'onUpdate:modelValue': (v) => (value.value = v),
            },
            {
              default: () =>
                Array.from({ length: 12 }, (_, i) =>
                  h('option', { value: String(i) }, `Modelo ${i}`),
                ),
            },
          ),
        ]),
        [[vErpDialog]],
      ),
    ]),
  )
  await tick()
  const control = root.querySelector('.erp-dropdown')!
  vi.spyOn(control, 'getBoundingClientRect').mockReturnValue({
    left: 300,
    right: 400,
    top: 650,
    bottom: 690,
    width: 100,
    height: 40,
  } as DOMRect)
  await openDropdown(control)
  const menu = document.querySelector<HTMLElement>('.erp-dropdown__menu')!
  expect(menu.parentElement).toBe(document.body)
  expect(menu.dataset.erpDialogOwner).toBe(root.querySelector('form')!.id)
  expect(Number(menu.style.zIndex)).toBeGreaterThan(3100)
  expect(menu.style.bottom).not.toBe('')
  expect(document.activeElement?.tagName).not.toBe('INPUT')
  const search = menu.querySelector('input')!
  search.value = 'Modelo 11'
  search.dispatchEvent(new Event('input', { bubbles: true }))
  await tick()
  expect(menu.querySelectorAll('[role=option]')).toHaveLength(1)
  menu.querySelector<HTMLButtonElement>('[role=option]')!.click()
  await tick()
  expect(value.value).toBe('11')
  await openDropdown(control)
  document
    .querySelector('[role=option]')!
    .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  await tick()
  expect(document.querySelector('.erp-dropdown__menu')).toBeNull()
  expect(close).not.toHaveBeenCalled()
})
it('wraps Tab from a popup on the last modal field back to the first control', async () => {
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
  mount(() =>
    withDirectives(
      h('section', [
        h('button', { id: 'first' }, 'Fechar'),
        h(ErpSelect, { modelValue: 'a' }, { default: () => [h('option', { value: 'a' }, 'A')] }),
      ]),
      [[vErpDialog]],
    ),
  )
  await tick()
  const options = await openDropdown(root.querySelector('.erp-dropdown'))
  options[0]!.focus()
  const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
  options[0]!.dispatchEvent(event)
  await tick()
  expect(event.defaultPrevented).toBe(true)
  expect(document.activeElement).toBe(root.querySelector('#first'))
  expect(document.querySelector('.erp-dropdown__menu')).toBeNull()
})
it('shows one popup at a time, searches accents and closes on outside touch', async () => {
  mount(() =>
    h(
      'div',
      [1, 2].map((id) =>
        h(ErpDropdown, {
          options: [{ value: 'calca', label: 'Calça' }],
          label: `Campo ${id}`,
          searchable: true,
        }),
      ),
    ),
  )
  await openDropdown(root.querySelectorAll('.erp-dropdown')[0])
  await openDropdown(root.querySelectorAll('.erp-dropdown')[1])
  expect(document.querySelectorAll('.erp-dropdown__menu')).toHaveLength(1)
  const search = document.querySelector<HTMLInputElement>('.erp-dropdown__search input')!
  search.value = 'calca'
  search.dispatchEvent(new Event('input', { bubbles: true }))
  await tick()
  expect(document.querySelector('[role=option]')?.textContent).toBe('Calça')
  document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
  await tick()
  expect(document.querySelector('.erp-dropdown__menu')).toBeNull()
})
it('keeps native select/datalist pickers out of all application Vue templates', () => {
  const base = resolve(process.cwd(), 'src')
  function scan(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((f) =>
      f.isDirectory()
        ? scan(`${dir}/${f.name}`)
        : f.name.endsWith('.vue')
          ? [`${dir}/${f.name}`]
          : [],
    )
  }
  expect(
    scan(base).filter((file) => /<(select|datalist)\b/i.test(readFileSync(file, 'utf8'))),
  ).toEqual([])
})
