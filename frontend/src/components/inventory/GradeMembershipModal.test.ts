import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import type { InventoryItem } from '@/services/api'
import GradeMembershipModal from './GradeMembershipModal.vue'

const api = vi.hoisted(() => ({
  getItemGradeSuggestions: vi.fn(), getGradeDirectory: vi.fn(), getGroupItemSuggestions: vi.fn(),
  getItems: vi.fn(), getGradeMembers: vi.fn(), attachItemToGrade: vi.fn(), removeFromGroup: vi.fn(), ungroup: vi.fn(),
}))
vi.mock('@/services/api', () => ({ inventoryAPI: api }))

let app: App | undefined
let mountPoint: HTMLDivElement
const item = (id: string, group_key: string | null = null) => ({
  id, name: 'Boné Boss 2001020', color: 'Azul', size: 'UN', inventory_code: `INV-${id}`,
  group_key, sku_internal: `SKU-${id}`, created_at: '2026-10-01T10:00:00Z',
}) as InventoryItem
const grade = (group_key: string) => ({ group_key, display_name: 'Boné Boss 2001020', member_count: 4, match_reason: 'same_model' })

function button(label: string): HTMLButtonElement {
  const found = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button')).find(node => node.textContent?.trim() === label)
  if (!found) throw new Error(`Button missing: ${label}`)
  return found
}
function chooseOption(label: string) {
  const found = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.grade-manager-option')).find(node => node.textContent?.includes(label))
  if (!found) throw new Error(`Option missing: ${label}`)
  found.click()
}
async function mount(props: Record<string, unknown> = {}) {
  mountPoint = document.createElement('div'); document.body.append(mountPoint)
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(GradeMembershipModal, props).use(i18n)
  app.mount(mountPoint)
  await nextTick()
}

beforeEach(() => {
  vi.resetAllMocks()
  api.getItemGradeSuggestions.mockResolvedValue({ groups: [] })
  api.getGradeDirectory.mockResolvedValue({ groups: [] })
  api.getGroupItemSuggestions.mockResolvedValue({ items: [] })
  api.getItems.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 12, total_pages: 0 })
  api.getGradeMembers.mockResolvedValue({ items: [item('member', 'target')], total: 1, page: 1, limit: 100 })
  api.attachItemToGrade.mockResolvedValue({ item_id: 'loose', group_key: 'target', previous_group_key: null })
  api.removeFromGroup.mockResolvedValue({ message: 'ok' })
  api.ungroup.mockResolvedValue({ message: 'ok' })
})
afterEach(() => { app?.unmount(); mountPoint?.remove(); vi.useRealTimers() })

describe('Grade membership panel', () => {
  it('suggests the same model without linking until an explicit confirmation', async () => {
    api.getItemGradeSuggestions.mockResolvedValue({ groups: [grade('grade-blue')] })
    const changed = vi.fn()
    await mount({ item: item('loose'), onChanged: changed })
    await vi.waitFor(() => expect(document.body.textContent).toContain('Mesmo modelo ou características'))
    expect(api.attachItemToGrade).not.toHaveBeenCalled()
    chooseOption('Boné Boss 2001020'); await nextTick()
    expect(api.attachItemToGrade).not.toHaveBeenCalled()
    button('Vincular à grade').click()
    await vi.waitFor(() => expect(api.attachItemToGrade).toHaveBeenCalledExactlyOnceWith('loose', 'grade-blue', null))
    expect(changed).toHaveBeenCalledOnce()
  })

  it('searches a specific existing grade and requires confirmation before moving a grouped item', async () => {
    api.getGradeDirectory.mockResolvedValue({ groups: [grade('grade-black')] })
    await mount({ item: item('old', 'grade-blue'), groupName: 'Boné Boss Azul' })
    await vi.waitFor(() => expect(api.getGradeDirectory).toHaveBeenCalledWith(''))
    chooseOption('Boné Boss 2001020'); await nextTick()
    expect(document.body.textContent).toContain('moverá a peça da grade atual')
    expect(api.attachItemToGrade).not.toHaveBeenCalled()
    button('Confirmar transferência').click()
    await vi.waitFor(() => expect(api.attachItemToGrade).toHaveBeenCalledExactlyOnceWith('old', 'grade-black', 'grade-blue'))
  })

  it('keeps the panel open when the chosen grade already contains this size and color', async () => {
    api.getItemGradeSuggestions.mockResolvedValue({ groups: [grade('target')] })
    api.attachItemToGrade.mockRejectedValue(Object.assign(new Error('Grade conflict'), {
      isAxiosError: true,
      response: { data: { detail: 'A grade já contém esta combinação de tamanho e cor.' } },
    }))
    const changed = vi.fn()
    await mount({ item: item('loose'), onChanged: changed })
    await vi.waitFor(() => expect(document.body.textContent).toContain('Mesmo modelo ou características'))
    chooseOption('Boné Boss 2001020'); await nextTick()
    button('Vincular à grade').click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('A grade já contém esta combinação'))
    expect(changed).not.toHaveBeenCalled()
    expect(document.body.querySelector('.grade-manager')).not.toBeNull()
  })

  it('adds an ungrouped candidate to a grade only after confirmation', async () => {
    api.getGroupItemSuggestions.mockResolvedValue({ items: [item('loose')] })
    const member = item('member', 'target')
    await mount({ groupKey: 'target', groupName: 'Boné Boss 2001020', members: [member] })
    await vi.waitFor(() => expect(document.body.textContent).toContain('INV-loose'))
    chooseOption('INV-loose'); await nextTick()
    expect(api.attachItemToGrade).not.toHaveBeenCalled()
    button('Vincular à grade').click()
    await vi.waitFor(() => expect(api.attachItemToGrade).toHaveBeenCalledExactlyOnceWith('loose', 'target', null))
  })

  it('removes one member after confirming the exact grade', async () => {
    await mount({ groupKey: 'target', groupName: 'Boné Boss 2001020', members: [item('member', 'target')] })
    button('Remover').click(); await nextTick()
    expect(api.removeFromGroup).not.toHaveBeenCalled()
    button('Confirmar').click()
    await vi.waitFor(() => expect(api.removeFromGroup).toHaveBeenCalledExactlyOnceWith('member', 'target'))
  })

  it('shows a second confirmation before ungrouping every member', async () => {
    await mount({ groupKey: 'target', groupName: 'Boné Boss 2001020', members: [item('member', 'target')] })
    await vi.waitFor(() => expect(button('Desagrupar toda a grade').disabled).toBe(false))
    button('Desagrupar toda a grade').click(); await nextTick()
    expect(api.ungroup).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('Os produtos e saldos permanecem')
    button('Confirmar').click()
    await vi.waitFor(() => expect(api.ungroup).toHaveBeenCalledExactlyOnceWith('target'))
  })

  it('loads the full grade separately from a filtered card before offering whole-grade removal', async () => {
    api.getGradeMembers.mockResolvedValue({ items: [item('visible', 'target'), item('other-lot', 'target')], total: 2, page: 1, limit: 100 })
    await mount({ groupKey: 'target', groupName: 'Boné Boss 2001020', members: [item('visible', 'target')] })
    await vi.waitFor(() => expect(document.body.textContent).toContain('INV-other-lot'))
    expect(api.getGradeMembers).toHaveBeenCalledWith('target', 1)
    expect(document.body.textContent).toContain('2/2')
    button('Desagrupar toda a grade').click(); await nextTick()
    expect(document.body.textContent).toContain('remover 2 vínculos')
  })
})
