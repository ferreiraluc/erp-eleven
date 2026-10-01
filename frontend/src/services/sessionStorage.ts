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
    storage.removeItem('user_data')
    storage.removeItem('erp_last_route')
  }
}

export function tokenIsCurrent(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]!.replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now() && !!payload.sid
  } catch { return false }
}
