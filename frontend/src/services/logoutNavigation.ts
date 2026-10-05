import type { Router } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'

export function logoutToLogin(auth: ReturnType<typeof useAuthStore>, router: Pick<Router, 'replace'>) {
  const completion = auth.logout().catch(() => {})
  // Local expiry happens before revocation. Its late network result must never
  // navigate away from a different account that has since signed in.
  if (auth.status === 'guest' && !auth.isLoading) void router.replace('/login')
  return completion
}
