/** Build a conversation link without guessing the country of a local number. */
export function whatsappConversationUrl(phone: string | null | undefined): string | null {
  const value = phone?.trim() || ''
  if (!/^\+?[\d\s().-]+$/.test(value)) return null

  let digits = value.replace(/\D/g, '')
  const explicitInternational = value.startsWith('+') || digits.startsWith('00')
  if (digits.startsWith('00') && !value.startsWith('+')) digits = digits.slice(2)
  if (!/^[1-9]\d{7,14}$/.test(digits) || /^(\d)\1+$/.test(digits)) return null

  // The directory also stores Brazilian and Paraguayan numbers as digits with DDI.
  // Do not infer the phone's country from documents, an address, or the UI language.
  const brazil = /^55[1-9]\d[2-9]\d{7,8}$/.test(digits)
  const paraguay = /^595[1-9]\d{8}$/.test(digits)
  if (digits.startsWith('55') && !brazil) return null
  if (digits.startsWith('595') && !paraguay) return null
  if (!explicitInternational && !brazil && !paraguay) return null

  return `https://wa.me/${digits}`
}
