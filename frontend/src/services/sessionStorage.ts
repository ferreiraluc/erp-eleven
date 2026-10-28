export function storedToken(): string | null {
  return sessionStorage.getItem('auth_token') || localStorage.getItem('auth_token')
}

export function saveToken(token: string, remember = true) {
  clearSession()
  ;(remember ? localStorage : sessionStorage).setItem('auth_token', token)
}

export function clearSession() {
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
  const storage = sessionStorage.getItem('auth_token') === token ? sessionStorage : localStorage
  storage.setItem('auth_session_expiry', JSON.stringify({ token, expiresAt: Math.min(previous, expiresAt) }))
}

export function tokenIsCurrent(token: string): boolean {
  const expiresAt = sessionExpiry(token)
  return expiresAt !== null && expiresAt > Date.now()
}
