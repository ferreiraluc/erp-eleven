import type { Router } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'

/** Revalidation may finish after logout or a different account starts signing in. */
export async function resumeVerifiedSession(auth: ReturnType<typeof useAuthStore>, router: Pick<Router, 'replace'>) {
  const ownerToken = auth.token
  if (document.hidden || !ownerToken) return
  const valid = await auth.ensureSession()
  if (auth.token !== ownerToken) {
    // A genuine expiry clears the token and still needs the login screen.
    // A new identity or a new pending login owns its own navigation instead.
    if (auth.token || auth.isLoading || auth.status !== 'guest') return
  }
  if (!valid) await router.replace('/login')
  else if (auth.user?.must_change_password) await router.replace('/conta')
}
