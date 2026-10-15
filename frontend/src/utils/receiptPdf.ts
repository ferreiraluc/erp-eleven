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

// Local support details only: no receipt content, sale IDs, tokens or URLs.
export function receiptShareContext(event?: Event): string {
  const policy = (document as Document & { permissionsPolicy?: { allowsFeature(name: string): boolean }; featurePolicy?: { allowsFeature(name: string): boolean } })
  const permissions = policy.permissionsPolicy || policy.featurePolicy
  let allowed: boolean | string = 'unknown'
  try { allowed = permissions?.allowsFeature('web-share') ?? 'unknown' } catch { /* browser does not expose it */ }
  return [
    `secure=${window.isSecureContext}`, `trusted=${event?.isTrusted ?? 'unknown'}`,
    `activation=${navigator.userActivation?.isActive ?? 'unknown'}`,
    `policy=${allowed}`, `visibility=${document.visibilityState}`,
    navigator.userAgent,
  ].join('\n')
}
