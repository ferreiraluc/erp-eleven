// Validate and prepare the named PDF before the download tap. The object URL
// is only a local download handle; it must never be sent as a message or link.
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
