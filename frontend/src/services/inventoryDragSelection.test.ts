import { afterEach, expect, it, vi } from 'vitest'
import { startInventoryDrag } from './inventoryDragSelection'
let cleanup = () => {}
afterEach(() => { cleanup(); document.body.innerHTML = ''; vi.restoreAllMocks(); vi.useRealTimers() })
function setup(pointerType = 'mouse') {
  document.body.innerHTML = '<div id="list"><div data-item-id="one">Produto</div></div><button id="confirm">Confirmar grade</button>'
  const container = document.getElementById('list')!, card = container.firstElementChild as HTMLElement
  const select = vi.fn(), dragging = vi.fn()
  const start = new MouseEvent('pointerdown', { bubbles: true, clientX: 1, clientY: 1 })
  Object.defineProperties(start, { pointerType: { value: pointerType }, pointerId: { value: 1 } })
  card.dispatchEvent(start)
  cleanup = startInventoryDrag(start as PointerEvent, container, 'one', select, dragging)
  Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: () => card })
  return { select, dragging, card }
}
function pointer(type: string, id = 1) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: 30, clientY: 30 })
  Object.defineProperty(event, 'pointerId', { value: id }); document.dispatchEvent(event); return event
}
it('keeps touch scrolling native without leaking handlers after pointercancel', () => {
  const { select } = setup('touch')
  expect(pointer('pointermove').defaultPrevented).toBe(false)
  pointer('pointercancel'); expect(select).not.toHaveBeenCalled()
  expect(document.getElementById('confirm')!.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))).toBe(true)
})
it('does not swallow a dialog confirmation after dragging', () => {
  setup(); pointer('pointermove'); pointer('pointerup')
  const clicked = vi.fn(), button = document.getElementById('confirm')!
  button.addEventListener('click', clicked); button.click(); expect(clicked).toHaveBeenCalledOnce()
})
it('suppresses only the immediate card click and expires the listener when no click follows', () => {
  vi.useFakeTimers(); const { card } = setup(); pointer('pointermove'); pointer('pointerup')
  expect(card.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))).toBe(false)
  cleanup(); setup(); pointer('pointermove'); pointer('pointerup'); vi.runAllTimers()
  expect(document.querySelector('[data-item-id]')!.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))).toBe(true)
})
it('ignores another pointer and releases all listeners on cancellation or unmount', () => {
  const { select, dragging } = setup(); pointer('pointermove', 2); expect(select).not.toHaveBeenCalled()
  pointer('pointermove'); expect(select).toHaveBeenCalled(); pointer('pointercancel')
  expect(dragging).toHaveBeenLastCalledWith(false); select.mockClear()
  pointer('pointermove'); expect(select).not.toHaveBeenCalled(); cleanup()
})
