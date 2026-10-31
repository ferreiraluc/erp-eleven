import { describe, expect, it } from 'vitest'
import { whatsappConversationUrl } from './whatsapp'

describe('WhatsApp conversation links', () => {
  it.each([
    ['+55 (11) 91234-5678', '5511912345678'],
    ['00 55 (11) 3456-7890', '551134567890'],
    ['5511912345678', '5511912345678'],
    ['55.11.3456.7890', '551134567890'],
    ['+595 981 234567', '595981234567'],
    ['00595981234567', '595981234567'],
    ['595981234567', '595981234567'],
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
    '+5511000000000', '+5500912345678', '+5511912345678900', '+5950981234567',
    '+55 11 91234-5678 ramal 2', '55+11912345678', '++5511912345678',
    'https://wa.me/5511912345678', '5511912345678?text=Olá', '5511912345678/123',
  ])('does not guess or create a link for %s', (phone) => {
    expect(whatsappConversationUrl(phone)).toBeNull()
  })
})
