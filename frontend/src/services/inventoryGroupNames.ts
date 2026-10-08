import type { InventoryItem } from './api'

type GroupItem = Pick<InventoryItem, 'id' | 'name' | 'size' | 'created_at'>
const automaticKey = /^(?:grade-)?(?:[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}|[\da-f]{32})$/i

/** A grade's identity is stable; its visible title comes from the original model. */
export function inventoryGroupName(key: string, items: readonly GroupItem[], fallback: string): string {
  if (!automaticKey.test(key.trim())) return key
  // The oldest member is the source when duplicating/adding sizes. Break ties by
  // ID so filtering, size/color ordering and list refreshes cannot change the title.
  const source = [...items].filter(item => item.name?.trim()).sort((a, b) => {
    const dateA = Date.parse(a.created_at), dateB = Date.parse(b.created_at)
    return (Number.isFinite(dateA) ? dateA : Infinity) - (Number.isFinite(dateB) ? dateB : Infinity)
      || a.id.localeCompare(b.id)
  })[0]
  if (!source) return fallback
  const name = source.name.trim()
  const suffix = source.size?.trim() ? ` ${source.size.trim()}` : ''
  // Remove only the exact size token, never digits belonging to DN0281, EA7, etc.
  return suffix && name.length > suffix.length && name.toLocaleLowerCase().endsWith(suffix.toLocaleLowerCase())
    ? name.slice(0, -suffix.length).trimEnd() : name
}
