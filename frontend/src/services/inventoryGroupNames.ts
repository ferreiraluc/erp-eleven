import type { InventoryItem } from './api'

type GroupItem = Pick<InventoryItem, 'id' | 'name' | 'size' | 'created_at'> & Pick<InventoryItem, 'color'>
const automaticKey = /^(?:grade-)?(?:[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}|[\da-f]{32})$/i

/** A grade's identity is stable; its visible title comes from the original model. */
export function inventoryGroupName(key: string, items: readonly GroupItem[], fallback: string): string {
  // The oldest member is the source when duplicating/adding sizes. Break ties by
  // ID so filtering, size/color ordering and list refreshes cannot change the title.
  const source = [...items].filter(item => item.name?.trim()).sort((a, b) => {
    const dateA = Date.parse(a.created_at), dateB = Date.parse(b.created_at)
    return (Number.isFinite(dateA) ? dateA : Infinity) - (Number.isFinite(dateB) ? dateB : Infinity)
      || a.id.localeCompare(b.id)
  })[0]
  if (!source) return automaticKey.test(key.trim()) ? fallback : key
  const name = source.name.trim()
  const suffix = source.size?.trim() ? ` ${source.size.trim()}` : ''
  // Remove only the exact size token, never digits belonging to DN0281, EA7, etc.
  const modelName = suffix && name.length > suffix.length && name.toLocaleLowerCase().endsWith(suffix.toLocaleLowerCase())
    ? name.slice(0, -suffix.length).trimEnd() : name
  const colors = new Set(items.map(item => item.color?.trim().toLocaleLowerCase()).filter(Boolean))
  const sourceColor = source.color?.trim()
  if (automaticKey.test(key.trim())) {
    // The source name may itself end with its color. Keep it for a one-color grade,
    // but remove that structured suffix when other colors join the same model.
    const colorSuffix = sourceColor ? ` ${sourceColor}` : ''
    return colors.size > 1 && colorSuffix && modelName.length > colorSuffix.length &&
      modelName.toLocaleLowerCase().endsWith(colorSuffix.toLocaleLowerCase())
      ? modelName.slice(0, -colorSuffix.length).trimEnd() : modelName
  }
  // Some legacy grade keys were generated as "model + first color". Once another
  // color joins, that key remains the stable identity but the visible title must
  // no longer claim that every piece has the first color. Custom names are kept.
  if (colors.size > 1 && sourceColor &&
      key.trim().toLocaleLowerCase() === `${modelName} ${sourceColor}`.toLocaleLowerCase()) return modelName
  return key
}
