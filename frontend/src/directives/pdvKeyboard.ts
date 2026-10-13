import type { ObjectDirective } from 'vue'

/** Actions should dismiss an existing keyboard, never redirect focus into text. */
function dismissPdvActionKeyboard(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element) || target.closest('input, textarea, select, label, [contenteditable="true"]')) return
  if (!target.closest('button, .pdv-result-row, .pdv-result-avulso')) return
  const focused = document.activeElement
  if (focused instanceof HTMLElement && focused.matches('input, textarea, [contenteditable="true"]')) {
    focused.blur()
  }
}

export const vPdvActionKeyboard: ObjectDirective<HTMLElement> = {
  mounted(element) { element.addEventListener('click', dismissPdvActionKeyboard, true) },
  beforeUnmount(element) { element.removeEventListener('click', dismissPdvActionKeyboard, true) },
}
