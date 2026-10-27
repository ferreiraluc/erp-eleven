export interface BulkPhoto {
  image: string
  preview: string
  operation?: 'replace' | 'add'
}
export type PhotoDraft = Record<string, BulkPhoto>
export const MAX_BATCH_PHOTOS = 20

/** One image per request group, never a base64 copy per size. */
export function photoAssignments(draft: PhotoDraft, selectedIds: string[]) {
  const groups = new Map<string, { image_data: string; item_ids: string[]; operation?: 'add' }>()
  for (const id of selectedIds) {
    const photo = draft[id]
    if (!photo) continue
    const key = `${photo.operation || 'replace'}:${photo.image}`
    if (!groups.has(key))
      groups.set(key, {
        image_data: photo.image,
        item_ids: [],
        ...(photo.operation === 'add' ? { operation: 'add' as const } : {}),
      })
    groups.get(key)!.item_ids.push(id)
  }
  return [...groups.values()]
}
