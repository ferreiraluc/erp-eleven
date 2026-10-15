// Materialize the response as bytes, rather than forwarding a network-backed Blob
// to the OS share service. Keep this work outside the user's share/download tap.
export function receiptPdfFile(buffer: ArrayBuffer, code: string): File {
  const bytes = new Uint8Array(buffer)
  const header = String.fromCharCode(...bytes.subarray(0, 5))
  const trailer = String.fromCharCode(...bytes.subarray(Math.max(0, bytes.length - 1024)))
  if (!bytes.length || header !== '%PDF-' || !trailer.includes('%%EOF')) {
    throw new Error('INVALID_RECEIPT_PDF')
  }
  const identity = code.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64) || 'venta'
  return new File([buffer], `eleven-ticket-${identity}.pdf`, { type: 'application/pdf', lastModified: Date.now() })
}

// An unknown policy name can return false. Distinguish that from an actual
// prohibition, especially on browsers with only partial Permissions Policy support.
type SharePolicy = { allowsFeature(name: string): boolean; features?(): string[] }
export function receiptSharePolicy(): { allowed: boolean | 'unknown'; supported: boolean | 'unknown' } {
  const doc = document as Document & { permissionsPolicy?: SharePolicy; featurePolicy?: SharePolicy }
  const policy = doc.permissionsPolicy || doc.featurePolicy
  try {
    if (!policy) return { allowed: 'unknown', supported: 'unknown' }
    const supported = policy.features ? policy.features().includes('web-share') : 'unknown'
    return { allowed: supported === false ? 'unknown' : policy.allowsFeature('web-share'), supported }
  } catch { return { allowed: 'unknown', supported: 'unknown' } }
}

// Local support details only: no receipt content, sale IDs, tokens or URLs.
export function receiptShareContext(event?: Event): string {
  const policy = receiptSharePolicy()
  return [
    `secure=${window.isSecureContext}`, `trusted=${event?.isTrusted ?? 'unknown'}`,
    `activation=${navigator.userActivation?.isActive ?? 'unknown'}`,
    `policy=${policy.allowed}`, `policySupported=${policy.supported}`,
    `topLevel=${window.top === window.self}`, `visibility=${document.visibilityState}`,
    navigator.userAgent,
  ].join('\n')
}
