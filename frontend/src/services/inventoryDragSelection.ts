/** Mouse drag selection only. Touch keeps native scrolling and selects by tap.
 * Every global listener belongs to one gesture; no pending listener may swallow
 * a later click in a product dialog after a cancelled drag. */
export function startInventoryDrag(
  event: PointerEvent,
  container: HTMLElement,
  startId: string,
  select: (id: string) => void,
  dragging: (active: boolean) => void,
): () => void {
  if (event.pointerType !== 'mouse' || event.button !== 0 ||
      (event.target as Element)?.closest('button,a,input,select,textarea')) return () => {}
  const { pointerId, clientX, clientY } = event
  let moved = false
  let timeout: ReturnType<typeof setTimeout> | undefined
  function clear() {
    document.removeEventListener('pointermove', move)
    document.removeEventListener('pointerup', up)
    document.removeEventListener('pointercancel', cancel)
    window.removeEventListener('blur', clear)
    document.removeEventListener('click', suppress, true)
    if (timeout) clearTimeout(timeout)
    dragging(false)
  }
  function suppress(click: MouseEvent) {
    // Suppress only the synthesized click on a card in this same list.
    if (container.contains(click.target as Node) && !(click.target as Element).closest('button,a,input,select,textarea')) {
      click.preventDefault(); click.stopPropagation()
    }
    clear()
  }
  function move(next: PointerEvent) {
    if (next.pointerId !== pointerId || Math.hypot(next.clientX - clientX, next.clientY - clientY) < 10) return
    next.preventDefault()
    if (!moved) { moved = true; dragging(true); select(startId) }
    const card = document.elementFromPoint(next.clientX, next.clientY)?.closest<HTMLElement>('[data-item-id]')
    if (card?.dataset.itemId && container.contains(card)) select(card.dataset.itemId)
  }
  function up(next: PointerEvent) {
    if (next.pointerId !== pointerId) return
    clear()
    if (moved) {
      document.addEventListener('click', suppress, true)
      // Mouse click follows pointerup synchronously; expire if the browser emits none.
      timeout = setTimeout(clear, 0)
    }
  }
  function cancel(next: PointerEvent) { if (next.pointerId === pointerId) clear() }
  document.addEventListener('pointermove', move, { passive: false })
  document.addEventListener('pointerup', up)
  document.addEventListener('pointercancel', cancel)
  window.addEventListener('blur', clear)
  return clear
}
