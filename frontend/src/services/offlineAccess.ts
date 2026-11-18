/** An offline catalog is never a write-capable session. Old async UI handlers
 * must be stopped centrally too, even after their component is unmounted. */
let readOnlyToken: string | null = null
export function setOfflineReadOnly(token: string | null) { readOnlyToken = token }
export function isOfflineReadOnly(token: string | null) { return !!token && token === readOnlyToken }
if (typeof window !== 'undefined') {
  window.addEventListener('erp:session-cleared', () => setOfflineReadOnly(null))
}
