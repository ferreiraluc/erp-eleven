import { isNativeSession, nativeSessionVault } from './nativeSessionVault'

export function storedToken(): string | null {
  if (isNativeSession()) return nativeSessionVault().token
  return sessionStorage.getItem('auth_token') || localStorage.getItem('auth_token')
}

export function saveToken(token: string, remember = true) {
  if (isNativeSession()) {
    clearBrowserSession()
    nativeSessionVault().save(token, remember)
    window.dispatchEvent(new Event('erp:session-cleared'))
    return
  }
  clearSession()
  ;(remember ? localStorage : sessionStorage).setItem('auth_token', token)
}

export function clearSession() {
  if (isNativeSession()) nativeSessionVault().clear()
  clearBrowserSession()
  if (isNativeSession()) window.dispatchEvent(new Event('erp:session-cleared'))
}

function clearBrowserSession() {
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem('auth_token')
    storage.removeItem('auth_session_expiry')
    storage.removeItem('user_data')
    storage.removeItem('erp_last_route')
  }
}

function jwtExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]!.replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' && Number.isFinite(payload.exp) && payload.sid
      ? payload.exp * 1000 : null
  } catch { return null }
}

/** The server may shorten a legacy JWT without replacing its signed token. */
export function sessionExpiry(token: string): number | null {
  const signed = jwtExpiry(token)
  if (signed === null) return null
  if (isNativeSession()) {
    const vault = nativeSessionVault()
    return vault.token === token && vault.expiresAt !== null ? Math.min(signed, vault.expiresAt) : signed
  }
  for (const storage of [sessionStorage, localStorage]) {
    try {
      const deadline = JSON.parse(storage.getItem('auth_session_expiry') || 'null')
      if (deadline?.token === token && typeof deadline.expiresAt === 'number' && Number.isFinite(deadline.expiresAt)) {
        return Math.min(signed, deadline.expiresAt)
      }
    } catch { /* A malformed local hint never replaces the signed JWT deadline. */ }
  }
  return signed
}

export function saveSessionExpiry(token: string, deadline?: string) {
  if (storedToken() !== token || !deadline) return
  const expiresAt = Date.parse(deadline), previous = sessionExpiry(token)
  if (!Number.isFinite(expiresAt) || previous === null) return
  if (isNativeSession()) { nativeSessionVault().shorten(token, Math.min(previous, expiresAt)); return }
  const storage = sessionStorage.getItem('auth_token') === token ? sessionStorage : localStorage
  storage.setItem('auth_session_expiry', JSON.stringify({ token, expiresAt: Math.min(previous, expiresAt) }))
}

export function tokenIsCurrent(token: string): boolean {
  const expiresAt = sessionExpiry(token)
  return expiresAt !== null && expiresAt > Date.now()
}

/** Run before installing the router: an unhydrated app must not appear logged out
 * and then restore another identity after a delayed secure-storage read. */
export async function initializeNativeSession(): Promise<void> {
  if (!isNativeSession()) return
  clearBrowserSession()
  const vault = nativeSessionVault()
  await vault.initialize()
  if (vault.token && !tokenIsCurrent(vault.token)) { vault.clear(); await vault.flush() }
}

export function flushSessionStorage(): Promise<void> {
  return isNativeSession() ? nativeSessionVault().flush() : Promise.resolve()
}

export function sessionIsRemembered(token: string): boolean {
  return isNativeSession() ? nativeSessionVault().token === token && nativeSessionVault().isRemembered : localStorage.getItem('auth_token') === token
}

/** Explicit recovery for a corrupt/invalidated native entry. Removes only this
 * login; notification-installation identity and other app data are preserved. */
export async function resetNativeSession(): Promise<void> {
  if (!isNativeSession()) return
  clearSession()
  await flushSessionStorage()
  await initializeNativeSession()
}
