import { describe, expect, it } from 'vitest'
import { normalizeWhatsappPhone, whatsappConversationUrl, whatsappPhoneCountry, type PhoneCountry } from './whatsapp'

describe('WhatsApp conversation links', () => {
  it.each([
    ['+55 (11) 91234-5678', '5511912345678'],
    ['+55 (011) 91234-5678', '5511912345678'],
    ['0055 (011) 3456-7890', '551134567890'],
    ['00 55 (11) 3456-7890', '551134567890'],
    ['5511912345678', '5511912345678'],
    ['55.11.3456.7890', '551134567890'],
    ['+595 981 234567', '595981234567'],
    ['00595981234567', '595981234567'],
    ['595981234567', '595981234567'],
    ['+595 (0981) 234567', '595981234567'],
    ['+1 (202) 555-0123', '12025550123'],
    ['0044 20 7946 0018', '442079460018'],
    ['+39 06 1234 5678', '390612345678'],
    ['+54 9 11 2345 6789', '5491123456789'],
  ])('preserves the international number %s without prefilled text', (phone, number) => {
    const url = new URL(whatsappConversationUrl(phone)!)
    expect(url.origin).toBe('https://wa.me')
    expect(url.pathname).toBe(`/${number}`)
    expect(url.search).toBe('')
    expect(url.hash).toBe('')
  })

  it.each([
    undefined, null, '', '   ', '(11) 91234-5678', '(55) 91234-5678',
    '0981 234567', '981234567', '2025550123', '442079460018',
    '+', '+1234', '+111111111111', '+0012025550123', '00005511912345678',
    '+5511000000000', '+5500912345678', '+5511912345678900',
    '+55 (0011) 91234-5678',
    '+55 11 91234-5678 ramal 2', '55+11912345678', '++5511912345678',
    'https://wa.me/5511912345678', '5511912345678?text=Olá', '5511912345678/123',
  ])('does not guess or create a link for %s', (phone) => {
    expect(whatsappConversationUrl(phone)).toBeNull()
  })

  it.each([
    ['(11) 91234-5678', 'BR', '+5511912345678'],
    ['(55) 91234-5678', 'BR', '+5555912345678'],
    ['011 3456-7890', 'BR', '+551134567890'],
    ['0981 234567', 'PY', '+595981234567'],
    ['981234567', 'PY', '+595981234567'],
    ['+55 (11) 91234-5678', 'PY', '+5511912345678'],
    ['+595 (0981) 234567', 'BR', '+595981234567'],
  ])('normalizes %s only with the selected phone country %s', (phone, country, expected) => {
    expect(normalizeWhatsappPhone(phone, country as PhoneCountry)).toBe(expected)
    expect(whatsappConversationUrl(phone, country as PhoneCountry)).toBe(`https://wa.me/${expected.slice(1)}`)
    expect(whatsappPhoneCountry(expected)).toBe(expected.startsWith('+595') ? 'PY' : 'BR')
  })

  it.each([
    ['0981234567', 'BR'], ['11912345678', 'PY'], ['912345678', 'BR'],
    ['+55 11 00000000', 'PY'], ['5511912345678?text=oi', 'BR'],
  ])('does not reinterpret invalid or incomplete %s as %s', (phone, country) => {
    expect(normalizeWhatsappPhone(phone, country as PhoneCountry)).toBeNull()
  })
})
