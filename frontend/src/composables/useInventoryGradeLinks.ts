import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'
import { gradeLinks, type GradeLink } from '@/services/inventoryGradeLinks'

export function useInventoryGradeLinks(container: Ref<HTMLElement | undefined>, revision: Ref<unknown>, enabled: Ref<boolean>) {
  const links = ref<GradeLink[]>([])
  let observer: ResizeObserver | undefined, frame = 0, disposed = false
  function schedule() {
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      const element = container.value
      if (!element || !enabled.value || disposed) { links.value = []; return }
      const bounds = element.getBoundingClientRect()
      links.value = gradeLinks(Array.from(element.querySelectorAll<HTMLElement>(':scope > .item-card')).map(card => {
        const rect = card.getBoundingClientRect()
        return { id: card.dataset.itemId!, group: card.dataset.gradeKey || null,
          left: rect.left - bounds.left, right: rect.right - bounds.left,
          top: rect.top - bounds.top, bottom: rect.bottom - bounds.top }
      }))
    })
  }
  watch([container, revision, enabled], async () => {
    await nextTick()
    if (disposed) return
    observer?.disconnect()
    if (container.value && enabled.value && typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(schedule)
      observer.observe(container.value)
      container.value.querySelectorAll<HTMLElement>(':scope > .item-card').forEach(card => observer!.observe(card))
    }
    schedule()
  }, { flush: 'post', immediate: true })
  onUnmounted(() => { disposed = true; observer?.disconnect(); cancelAnimationFrame(frame) })
  return links
}
