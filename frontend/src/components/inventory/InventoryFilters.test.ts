import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryFilters from './InventoryFilters.vue'
import { chooseDropdown, openDropdown } from '@/test/dropdown'

let app: App | undefined
let container: HTMLDivElement

async function mount(props: Record<string, unknown>) {
  container = document.createElement('div')
  document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(defineComponent({ setup: () => () => h(InventoryFilters, props as never) })).use(i18n)
  app.mount(container)
  await nextTick()
}

function button(text: string) {
  const found = Array.from(document.querySelectorAll('button')).find(item => item.textContent?.trim().startsWith(text))
  if (!found) throw new Error(`Button missing: ${text}`)
  return found
}

afterEach(() => {
  app?.unmount()
  app = undefined
  container?.remove()
})

describe('Inventory filters', () => {
  it('groups stock states in one dropdown and emits operational filter changes', async () => {
    const onStatus = vi.fn(), onLocation = vi.fn(), onToggleGroups = vi.fn()
    await mount({
      statusChips: [{ value: '', label: 'Todos', count: 12 }, { value: 'low_stock', label: 'Baixo', count: 2 }],
      status: 'low_stock', brands: [], brand: '', categories: [], category: '', location: 'loja',
      hasGroups: true, groupMode: false, counts: { loja_count: 7, deposito_count: 5, group_count: 3 },
      onStatus, onLocation, 'onToggle-groups': onToggleGroups,
    })
    const status = document.querySelector<HTMLButtonElement>('[aria-label="Status do estoque"]')!
    expect(status.textContent).toContain('Baixo')
    expect(document.querySelectorAll('[aria-label="Status do estoque"]')).toHaveLength(1)
    const options = await openDropdown(status)
    expect(options.map(option => option.value)).toEqual(['', 'low_stock'])
    expect(options[1].getAttribute('aria-selected')).toBe('true')
    expect(button('Loja').getAttribute('aria-pressed')).toBe('true')
    await chooseDropdown(status, '')
    button('Depósito').click(); button('Ver grades').click()
    expect(onStatus).toHaveBeenCalledWith('')
    expect(onLocation).toHaveBeenCalledWith('deposito')
    expect(onToggleGroups).toHaveBeenCalledOnce()
  })

  it('offers uncategorized products even when there are no category facets', async () => {
    const onCategory = vi.fn()
    await mount({
      statusChips: [{ value: '', label: 'Todos' }], status: '', brands: [], brand: '',
      categories: [], category: '__uncategorized__', location: '', hasGroups: false, groupMode: false, onCategory,
    })
    const category = document.querySelector<HTMLButtonElement>('[aria-label="Categoria"]')!
    expect(category.textContent).toContain('Sem categoria')
    await chooseDropdown(category, '__uncategorized__')
    expect(onCategory).toHaveBeenCalledWith('__uncategorized__')
  })

  it('searches dropdown options and closes after selecting one', async () => {
    const onBrand = vi.fn()
    await mount({
      statusChips: [], status: '', brands: ['Adidas', 'Nike'], brand: '', categories: [], category: '', location: '',
      hasGroups: false, groupMode: false, onBrand,
    })
    button('Marca').click(); await nextTick()
    const search = document.querySelector('input[type="search"]') as HTMLInputElement
    search.value = 'nik'; search.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(document.body.textContent).toContain('Nike')
    expect(document.body.textContent).not.toContain('Adidas')
    button('Nike').click(); await nextTick()
    expect(onBrand).toHaveBeenCalledWith('Nike')
    expect(document.querySelector('.erp-dropdown__menu')).toBeNull()
  })
})
