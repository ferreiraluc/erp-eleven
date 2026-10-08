import type { ObjectDirective } from 'vue'

// No interception of submissions or confirmation handlers. A nested dialog
// owns Tab; Escape uses only an explicitly marked, enabled close control.
type Entry = { element: HTMLElement; opener: HTMLElement | null; backdrop: HTMLElement | null; zIndex: string }
const dialogs: Entry[] = []
const entries = new WeakMap<HTMLElement, Entry>()
let previousOverflow = ''
let sequence = 0
const focusable = 'a[href],button,input,select,textarea,summary,[tabindex],[contenteditable="true"]'

function visible(element: HTMLElement) {
  return element.isConnected && !element.closest('[hidden],[inert]') && element.getClientRects().length > 0
}
function top() { return dialogs.filter(entry => visible(entry.element)).at(-1) }
function controls(element: HTMLElement) {
  return Array.from(element.querySelectorAll<HTMLElement>(focusable))
    .filter(node => node.tabIndex >= 0 && !node.matches(':disabled,[aria-disabled="true"]') && visible(node))
}
function layers() {
  let level = 0
  for (const entry of dialogs) {
    if (!entry.backdrop) continue
    entry.backdrop.style.zIndex = entry.zIndex
    level = Math.max(level + 10, Number(getComputedStyle(entry.backdrop).zIndex) || 1000)
    entry.backdrop.style.zIndex = String(level)
  }
}
function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Tab' || event.defaultPrevented) return
  const current = top()
  if (!current || !current.element.contains(event.target as Node)) return
  const nodes = controls(current.element)
  const first = nodes[0], last = nodes.at(-1)
  const focused = document.activeElement
  if (!first || focused === current.element || (event.shiftKey ? focused === first : focused === last)) {
    event.preventDefault()
    event.stopPropagation()
    ;(event.shiftKey ? last : first)?.focus()
    if (!first) current.element.focus()
  }
}
function onEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape' || event.defaultPrevented) return
  const current = top()
  if (!current || current.element.getAttribute('role') === 'alertdialog' || !current.element.contains(event.target as Node)) return
  const close = current.element.querySelector<HTMLButtonElement>('[data-dialog-close]')
  if (close && !close.disabled && visible(close)) {
    event.preventDefault()
    close.click()
  }
}
function activate(element: HTMLElement) {
  if (entries.has(element)) return
  const backdrop = element.closest<HTMLElement>('.erp-dialog-backdrop')
  const entry = { element, backdrop, zIndex: backdrop?.style.zIndex ?? '', opener: document.activeElement as HTMLElement | null }
  entries.set(element, entry)
  if (!dialogs.length) {
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeydown, true)
    document.addEventListener('keydown', onEscape)
  }
  // Vue mounts descendants first. Keep an already mounted child above its parent.
  const child = dialogs.findIndex(item => element.contains(item.element))
  dialogs.splice(child < 0 ? dialogs.length : child, 0, entry)
  if (!element.hasAttribute('role')) element.setAttribute('role', 'dialog')
  element.setAttribute('aria-modal', 'true')
  if (!element.hasAttribute('tabindex')) element.tabIndex = -1
  if (!element.hasAttribute('aria-label') && !element.hasAttribute('aria-labelledby')) {
    const heading = element.querySelector<HTMLElement>('h1,h2,h3,h4')
    if (heading) {
      heading.id ||= `erp-dialog-title-${++sequence}`
      element.setAttribute('aria-labelledby', heading.id)
    }
  }
  layers()
  queueMicrotask(() => {
    if (top() === entry && !element.contains(document.activeElement)) element.focus({ preventScroll: true })
  })
}
function deactivate(element: HTMLElement) {
  const entry = entries.get(element)
  if (!entry) return
  const ownedFocus = element.contains(document.activeElement)
  dialogs.splice(dialogs.indexOf(entry), 1)
  entries.delete(element)
  if (entry.backdrop) entry.backdrop.style.zIndex = entry.zIndex
  layers()
  if (!dialogs.length) {
    document.body.style.overflow = previousOverflow
    document.removeEventListener('keydown', onKeydown, true)
    document.removeEventListener('keydown', onEscape)
  }
  queueMicrotask(() => {
    if (!ownedFocus) return
    const current = top()
    if (entry.opener && visible(entry.opener) && (!current || current.element.contains(entry.opener))) {
      entry.opener.focus({ preventScroll: true })
    } else current?.element.focus({ preventScroll: true })
  })
}

// Pass false for a v-show dialog while its content is hidden.
export const vErpDialog: ObjectDirective<HTMLElement, boolean | undefined> = {
  mounted(element, binding) { if (binding.value !== false) activate(element) },
  updated(element, binding) { if (binding.value === false) deactivate(element); else activate(element) },
  beforeUnmount: deactivate,
}
