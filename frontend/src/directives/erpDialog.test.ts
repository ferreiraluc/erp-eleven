import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, nextTick, ref, type App } from 'vue'
import { vErpDialog } from './erpDialog'

let app: App | undefined
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(function (this: HTMLElement) {
    return (this.closest('[style*="display: none"],[hidden]') ? [] : [{}]) as unknown as DOMRectList
  })
})
afterEach(() => { app?.unmount(); app = undefined; document.body.innerHTML = ''; document.body.style.overflow = ''; vi.restoreAllMocks() })
const settle = async () => { await nextTick(); await Promise.resolve() }
function mount(template: string) {
  const host = document.createElement('div'); document.body.append(host)
  const shown = ref(true), nested = ref(false)
  app = createApp(defineComponent({ directives: { erpDialog: vErpDialog }, setup: () => ({ shown, nested }), template }))
  app.mount(host)
  return { shown, nested }
}
function tab(element: HTMLElement, shiftKey = false) {
  element.focus(); const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true, shiftKey })
  element.dispatchEvent(event); return event
}
const get = (id: string) => document.getElementById(id)!

describe('ERP modal keyboard and scroll lifecycle', () => {
  it('labels the dialog, focuses the surface without submitting, and wraps Tab in both directions', async () => {
    mount('<div class="erp-dialog-backdrop"><section id="dialog" v-erp-dialog><h2>Cadastro</h2><button id="first">Fechar</button><input disabled><input hidden><button id="last">Salvar</button></section></div>')
    await settle()
    expect(document.activeElement).toBe(get('dialog'))
    expect(get('dialog').getAttribute('role')).toBe('dialog')
    expect(document.getElementById(get('dialog').getAttribute('aria-labelledby')!)?.textContent).toBe('Cadastro')
    expect(tab(get('last')).defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(get('first'))
    tab(get('first'), true)
    expect(document.activeElement).toBe(get('last'))
  })

  it('keeps scroll locked and restores focus to the nested opener until the last dialog closes', async () => {
    document.body.style.overflow = 'auto'
    const { nested, shown } = mount('<button id="page">Abrir</button><div v-if="shown" class="erp-dialog-backdrop" style="z-index:1000"><section id="parent" v-erp-dialog><h2>Produto</h2><button id="open" @click="nested=true">Foto</button></section></div><div v-if="nested" class="erp-dialog-backdrop" style="z-index:500"><section id="child" v-erp-dialog><h2>Foto</h2><button id="back" @click="nested=false">Voltar</button></section></div>')
    await settle(); get('open').focus(); get('open').click(); await settle()
    expect(document.activeElement).toBe(get('child'))
    expect(Number(get('child').parentElement!.style.zIndex)).toBeGreaterThan(Number(get('parent').parentElement!.style.zIndex))
    tab(get('back')); expect(document.activeElement).toBe(get('back'))
    nested.value = false; await settle()
    expect(document.activeElement).toBe(get('open'))
    expect(document.body.style.overflow).toBe('hidden')
    shown.value = false; await settle()
    expect(document.body.style.overflow).toBe('auto')
  })

  it('releases hidden v-show surfaces and reactivates them without losing the original scroll style', async () => {
    const { shown } = mount('<div v-show="shown" class="erp-dialog-backdrop"><section v-erp-dialog="shown" id="dialog"><h2>Histórico</h2><button>Fechar</button></section></div>')
    await settle(); shown.value = false; await settle()
    expect(document.body.style.overflow).toBe('')
    shown.value = true; await settle()
    expect(document.activeElement).toBe(get('dialog'))
    expect(document.body.style.overflow).toBe('hidden')
    app?.unmount(); app = undefined
    expect(document.body.style.overflow).toBe('')
  })

  it('does not intercept confirmation Enter or Escape handled by the owning component', async () => {
    mount('<div class="erp-dialog-backdrop"><section v-erp-dialog id="dialog" role="alertdialog" aria-label="Excluir"><input id="input"><button disabled>Excluir</button></section></div>')
    await settle()
    for (const key of ['Enter', 'Escape']) {
      const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
      get('input').dispatchEvent(event)
      expect(event.defaultPrevented).toBe(false)
    }
    expect(get('dialog').getAttribute('role')).toBe('alertdialog')
    expect(get('dialog').getAttribute('aria-label')).toBe('Excluir')
  })

  it('delegates Escape to the enabled close button and respects a field consuming it', async () => {
    const { shown } = mount('<div v-if="shown" class="erp-dialog-backdrop"><section v-erp-dialog><h2>Produto</h2><button id="close" data-dialog-close @click="shown=false">Fechar</button><input id="field" @keydown.esc.stop.prevent></section></div>')
    await settle()
    get('field').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    expect(shown.value).toBe(true)
    ;(get('close') as HTMLButtonElement).disabled = true
    get('close').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    expect(shown.value).toBe(true)
    ;(get('close') as HTMLButtonElement).disabled = false
    get('close').dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    expect(shown.value).toBe(false)
  })
})
