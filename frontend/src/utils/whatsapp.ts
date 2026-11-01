export type PhoneCountry = 'BR' | 'PY'

/** International numbers take precedence; a local number needs an explicit country. */
export function normalizeWhatsappPhone(phone: string | null | undefined, country?: PhoneCountry | ''): string | null {
  const value = phone?.trim() || ''
  if (!/^\+?[\d\s().-]+$/.test(value)) return null

  let digits = value.replace(/\D/g, '')
  const international = value.startsWith('+') || digits.startsWith('00')
  if (digits.startsWith('00') && !value.startsWith('+')) digits = digits.slice(2)
  // Strip a Brazilian trunk zero only after an explicit international prefix.
  if (international && /^550[1-9]\d[2-9]\d{7,8}$/.test(digits)) digits = `55${digits.slice(3)}`
  // The national trunk zero is often retained after Paraguay's DDI in old entries.
  if (/^5950[1-9]\d{8}$/.test(digits)) digits = `595${digits.slice(4)}`
  const brazil = /^55[1-9]\d[2-9]\d{7,8}$/.test(digits)
  const paraguay = /^595[1-9]\d{8}$/.test(digits)
  if (!international && !brazil && !paraguay) {
    if (!country) return null
    if (digits.startsWith('0')) digits = digits.slice(1)
    if (country === 'BR' && /^[1-9]\d[2-9]\d{7,8}$/.test(digits)) digits = `55${digits}`
    else if (country === 'PY' && /^[1-9]\d{8}$/.test(digits)) digits = `595${digits}`
    else return null
  }
  if (!/^[1-9]\d{7,14}$/.test(digits) || /^(\d)\1+$/.test(digits)) return null
  if (digits.startsWith('55') && !/^55[1-9]\d[2-9]\d{7,8}$/.test(digits)) return null
  if (digits.startsWith('595') && !/^595[1-9]\d{8}$/.test(digits)) return null
  return `+${digits}`
}

export function whatsappPhoneCountry(phone: string | null | undefined): PhoneCountry | '' {
  const normalized = normalizeWhatsappPhone(phone)
  return normalized?.startsWith('+595') ? 'PY' : normalized?.startsWith('+55') ? 'BR' : ''
}

export function whatsappConversationUrl(phone: string | null | undefined, country?: PhoneCountry | ''): string | null {
  const normalized = normalizeWhatsappPhone(phone, country)
  return normalized ? `https://wa.me/${normalized.slice(1)}` : null
}
