import { Capacitor, type PluginListenerHandle } from '@capacitor/core'
import { App } from '@capacitor/app'
import type { Router } from 'vue-router'
import type { useAuthStore } from '@/stores/auth'
import { resumeVerifiedSession } from './sessionResume'

/** Native WebViews can resume without a browser focus/pageshow event. Reuse the
 * server-verified resume flow so daily expiry and revoked roles still apply. */
export async function initializeNativeLifecycle(auth: ReturnType<typeof useAuthStore>, router: Pick<Router, 'replace'>): Promise<() => Promise<void>> {
  if (!Capacitor.isNativePlatform()) return async () => undefined
  let removed = false
  let handle: PluginListenerHandle | undefined
  handle = await App.addListener('appStateChange', ({ isActive }) => {
    if (isActive && !removed) void resumeVerifiedSession(auth, router).then(() => {
      if (!removed) window.dispatchEvent(new Event('erp:native-app-active'))
    }).catch(() => undefined)
  })
  return async () => { removed = true; await handle?.remove() }
}
