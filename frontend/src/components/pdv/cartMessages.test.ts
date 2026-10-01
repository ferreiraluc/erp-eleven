import { afterEach, describe, expect, it } from 'vitest'
import { createApp, defineComponent, h, nextTick, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { usePdvCartText } from './cartMessages'
let app: App | undefined, container: HTMLDivElement
afterEach(() => { app?.unmount(); container?.remove() })
describe('PDV stock conflict translations', () => {
  it('reacts to locale changes while preserving product names and formats known and unexpected details', async () => {
    const detail = ref<unknown>('Estoque não informado para "Loja". Confira os três saldos antes de concluir esta operação.')
    const Harness = defineComponent({ setup() { const { cartErrorText } = usePdvCartText()
      return () => h('p', cartErrorText({ response: { status: 409, data: { detail: detail.value } } }))
    } })
    const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
    container = document.createElement('div'); document.body.append(container)
    app = createApp(Harness).use(i18n); app.mount(container)
    expect(container.textContent).toContain('Estoque não informado para "Loja"')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.textContent).toContain('Stock no informado para "Loja"')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.textContent).toContain('Stock is missing for "Loja"')
    detail.value = 'Produto inativo: "Loja". Selecione um produto ativo para vender.'; await nextTick()
    expect(container.textContent).toContain('Inactive product: "Loja"')
    detail.value = 'Saldo insuficiente no local de origem: disponível 2, solicitado 8.'; await nextTick()
    expect(container.textContent).toContain('Insufficient source stock: available 2, requested 8.')
    detail.value = 'Local inválido no item da venda. Confira o local original; use loja ou deposito.'; await nextTick()
    expect(container.textContent).toContain('Check the original location')
    detail.value = 'Quantidade inválida no item da venda. Informe uma quantidade finita e positiva.'; await nextTick()
    expect(container.textContent).toContain('Invalid quantity on the sale line')
    detail.value = [{ loc: ['quantity'], msg: 'Invalid' }]; await nextTick()
    expect(container.textContent).toBe('Review the sale fields before trying again.')
    detail.value = 'Future server detail'; await nextTick()
    expect(container.textContent).toContain('The server rejected the operation.')
    expect(container.textContent).toContain('Future server detail')
  })
})
