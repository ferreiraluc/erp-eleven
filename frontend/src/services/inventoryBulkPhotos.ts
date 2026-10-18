export interface BulkPhoto { image: string; preview: string }
export type PhotoDraft = Record<string, BulkPhoto>
export const MAX_BATCH_PHOTOS = 20

/** One image per request group, never a base64 copy per size. */
export function photoAssignments(draft: PhotoDraft, selectedIds: string[]) {
  const groups = new Map<string, { image_data: string; item_ids: string[] }>()
  for (const id of selectedIds) {
    const photo = draft[id]
    if (!photo) continue
    if (!groups.has(photo.image)) groups.set(photo.image, { image_data: photo.image, item_ids: [] })
    groups.get(photo.image)!.item_ids.push(id)
  }
  return [...groups.values()]
}
