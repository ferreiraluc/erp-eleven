import type { RouteLocationNormalized } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'
import { storedToken } from '@/services/sessionStorage'

export function createAuthGuard(getAuth: () => ReturnType<typeof useAuthStore>) {
  let navigationEpoch = 0
  return async (to: RouteLocationNormalized) => {
    const navigation = ++navigationEpoch, auth = getAuth(), ownerToken = storedToken()
    const verified = await auth.ensureSession()
    // Returning a redirect from an old guard can override newer Vue navigation.
    if (navigation !== navigationEpoch) return false
    if (storedToken() !== ownerToken && (storedToken() || auth.isLoading)) return false
    if (to.meta.requiresAuth && !verified) return '/login'
    if (!verified) return true
    if (auth.user?.must_change_password && to.path !== '/conta') return '/conta'
    if (to.meta.requiresGuest) return '/dashboard'
    if (to.meta.requiresOwner && !auth.isOwner) return '/dashboard'
    if (to.meta.requiresAdmin && !auth.isOwner) return '/dashboard'
    if (to.meta.requiresManager && !['ADMIN', 'GERENTE'].includes(auth.user?.role || '')) return '/dashboard'
    if (to.meta.requiresAllSales && auth.ownSales) return '/dashboard'
    return true
  }
}
