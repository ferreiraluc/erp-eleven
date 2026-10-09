import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryFilters from './InventoryFilters.vue'

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
  const found = Array.from(container.querySelectorAll('button')).find(item => item.textContent?.trim().startsWith(text))
  if (!found) throw new Error(`Button missing: ${text}`)
  return found
}

afterEach(() => {
  app?.unmount()
  app = undefined
  container?.remove()
})

describe('Inventory filters', () => {
  it('exposes pressed states and emits operational filter changes', async () => {
    const onStatus = vi.fn(), onLocation = vi.fn(), onToggleGroups = vi.fn()
    await mount({
      statusChips: [{ value: '', label: 'Todos', count: 12 }, { value: 'low_stock', label: 'Baixo', count: 2 }],
      status: 'low_stock', brands: [], brand: '', categories: [], category: '', location: 'loja',
      hasGroups: true, groupMode: false, counts: { loja_count: 7, deposito_count: 5, group_count: 3 },
      onStatus, onLocation, 'onToggle-groups': onToggleGroups,
    })
    expect(button('Baixo').getAttribute('aria-pressed')).toBe('true')
    expect(button('Loja').getAttribute('aria-pressed')).toBe('true')
    button('Todos').click(); button('Depósito').click(); button('Ver grades').click()
    expect(onStatus).toHaveBeenCalledWith('')
    expect(onLocation).toHaveBeenCalledWith('deposito')
    expect(onToggleGroups).toHaveBeenCalledOnce()
  })

  it('searches dropdown options and closes after selecting one', async () => {
    const onBrand = vi.fn()
    await mount({
      statusChips: [], status: '', brands: ['Adidas', 'Nike'], brand: '', categories: [], category: '', location: '',
      hasGroups: false, groupMode: false, onBrand,
    })
    button('Marca').click(); await nextTick()
    const search = container.querySelector('input[type="search"]') as HTMLInputElement
    search.value = 'nik'; search.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(container.textContent).toContain('Nike')
    expect(container.textContent).not.toContain('Adidas')
    button('Nike').click(); await nextTick()
    expect(onBrand).toHaveBeenCalledWith('Nike')
    expect(container.querySelector('.chip-dropdown')).toBeNull()
  })
})
