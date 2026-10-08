import { inventoryAPI } from '@/services/api'

// Shared across all product cards: entering a large grid must not flood the API.
const queue: (() => void)[] = []
let active = 0
const MAX_ACTIVE = 2

function drain() {
  while (active < MAX_ACTIVE && queue.length) queue.shift()!()
}

export function loadThumbnail(id: string, isCurrent: () => boolean): Promise<{ image_data: string | null } | null> {
  return new Promise((resolve, reject) => {
    queue.push(() => {
      if (!isCurrent()) { resolve(null); return }
      active++
      inventoryAPI.getThumbnail(id).then(resolve, reject).finally(() => { active--; drain() })
    })
    drain()
  })
}
