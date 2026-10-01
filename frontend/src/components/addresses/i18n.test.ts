import { describe, expect, it } from 'vitest'
import { createAddressI18n } from './i18n'

describe('address module language and safe errors', () => {
  it('reacts to locale changes without changing business values or the currency', () => {
    let locale = 'pt'
    const ui = createAddressI18n(() => locale)
    expect(ui.tr('Agenda de endereços')).toBe('Agenda de endereços')
    locale = 'es'
    expect(ui.tr('Agenda de endereços')).toBe('Agenda de direcciones')
    locale = 'en'
    expect(ui.tr('Agenda de endereços')).toBe('Address book')
    expect(ui.tr('Izabela · Rua das Flores, 12')).toBe('Izabela · Rua das Flores, 12')
    expect(ui.money('1234.50')).toBe(new Intl.NumberFormat('en-US', { style: 'currency', currency: 'BRL' }).format(1234.5))
    expect(ui.date('2026-09-30T00:30:00Z')).toBe(new Date('2026-09-30T00:30:00Z').toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' }))
    expect(ui.money(null)).toBe('—')
    expect(ui.date('invalid')).toBe('—')
  })

  it('translates actionable server field errors and preserves postal conflict values', () => {
    const ui = createAddressI18n(() => 'en')
    const missing = 'Complete no remetente: nome, rua, CEP válido com 8 dígitos.'
    expect(ui.errorKey({ response: { status: 400, data: { detail: missing } } })).toBe(missing)
    expect(ui.tr(missing)).toBe('Complete the sender details: name, street, valid 8-digit postal code.')
    expect(ui.serviceMessage('SuperFrete: confira bairro, peso.')).toBe('SuperFrete: check district, weight.')
    expect(ui.serviceMessage('CEP 85865-310: rua informada ‘Rua do Comércio’; ViaCEP retorna ‘Rua Mem de Sá’. Confira antes de confirmar.')).toBe('Postal code 85865-310: provided street “Rua do Comércio”; ViaCEP returns “Rua Mem de Sá”. Review before confirming.')
    expect(ui.serviceMessage('SuperFrete retornou HTTP 503 ao baixar o PDF. Nova tentativa automática; não pague novamente.')).toContain('do not pay again')
    expect(ui.serviceMessage('Pagamento sem confirmação. Consulte o estado; não efetue outro pagamento.')).toContain('do not make another payment')
  })

  it('never echoes unknown API details, schemas, prototype keys or diagnostics', () => {
    for (const locale of ['pt','es','en']) {
      const ui = createAddressI18n(() => locale)
      for (const detail of ['unavailable', 'private-provider-response', '__proto__', { query: 'secret' }, [{ msg: 'secret', input: 'private' }]]) {
        const text = ui.tr(ui.errorKey({ response: { status: 502, data: { detail } } }))
        expect(text).toBe(ui.tr('Serviço temporariamente indisponível. Tente consultar novamente mais tarde.'))
        expect(ui.serviceMessage(detail)).toBe(text)
      }
      expect(ui.serviceMessage('Complete no remetente: private-provider-response.')).toBe(ui.tr('Serviço temporariamente indisponível. Tente consultar novamente mais tarde.'))
    }
  })

  it('returns safe authentication and validation hints even when detail is unavailable', () => {
    const ui = createAddressI18n(() => 'es')
    expect(ui.tr(ui.errorKey({ response: { status: 401 } }))).toBe('Su sesión venció. Inicie sesión de nuevo.')
    expect(ui.tr(ui.errorKey({ response: { status: 403 } }))).toBe('No tiene permiso para esta operación.')
    expect(ui.tr(ui.errorKey({ response: { status: 422, data: { detail: [{ msg: 'private' }] } } }))).toBe('Revise los campos y complete los datos necesarios.')
  })
})
