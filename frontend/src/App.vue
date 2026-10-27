<template>
  <div id="app">
    <a class="skip-link" href="#main-content">{{ $t('access.skipToContent') }}</a>
    <AccountNavigation
      v-if="!route.matched.some(record => record.path === '/dashboard') || !auth.isAuthenticated"
      :class="{ 'operational-account-bar': route.meta.requiresAuth }"
    />
    <NotificationInvitation v-if="auth.isAuthenticated" />
    <div v-if="auth.status === 'checking'" class="session-state" role="status">{{ $t('access.checking') }}</div>
    <section v-else-if="auth.status === 'error' && route.meta.requiresAuth" class="session-state session-error" role="alert">
      <p>{{ $t('access.connectionError') }}</p>
      <div><button class="erp-button erp-button--secondary" @click="retrySession">{{ $t('common.refresh') }}</button><button class="erp-button erp-button--secondary" @click="logout">{{ $t('common.logout') }}</button></div>
    </section>
    <main v-else-if="!route.meta.requiresAuth || auth.isAuthenticated" id="main-content" tabindex="-1">
      <RouterView :key="auth.user?.id || 'guest'" />
    </main>
    <NotificationToast />
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import { useCurrencyStore } from '@/stores/currency'
import { RouterView, useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationToast from '@/components/NotificationToast.vue'
import AccountNavigation from '@/components/AccountNavigation.vue'
import { logoutToLogin } from '@/services/logoutNavigation'
import NotificationInvitation from '@/components/notifications/NotificationInvitation.vue'
import { useNotificationCenter } from '@/stores/notificationCenter'
import { safeNotificationPath } from '@/services/notifications'
const auth = useAuthStore(), router = useRouter(), route = useRoute()
const notificationCenter = useNotificationCenter()
function notificationMessage(event: MessageEvent) {
  if (!auth.isAuthenticated || event.data?.user_id !== auth.user?.id) return
  if (event.data.type === 'eleven-notification-refresh') void notificationCenter.load()
  if (event.data.type === 'eleven-notification-open') {
    const path = safeNotificationPath(event.data.action_path)
    if (path) void router.push(path)
  }
}
navigator.serviceWorker?.addEventListener('message', notificationMessage)
onBeforeUnmount(() => navigator.serviceWorker?.removeEventListener('message', notificationMessage))
const currency = useCurrencyStore()
watch(() => auth.isAuthenticated && auth.user?.id, id => { if (id) void currency.loadCurrentRates() }, { immediate: true })
async function retrySession() {
  const ownerToken = auth.token
  const valid = await auth.ensureSession(true)
  if (auth.isLoading || (auth.token !== ownerToken && auth.token)) return
  if (valid && auth.user?.must_change_password) await router.replace('/conta')
  else if (!valid && auth.status === 'guest') await router.replace('/login')
}
function logout() { return logoutToLogin(auth, router) }
</script>
<style>
@media (max-width: 768px) {
  #app > .operational-account-bar { display: none; }
}
.session-error { align-content: center; gap: 1rem; padding: 1.5rem; text-align: center; }
.session-error p { max-width: 36rem; margin: 0; }
.session-error button { margin: 0 .4rem; padding: .55rem .9rem; border: 1px solid #cbd5e1; border-radius: 8px; background: white; color: #1d4ed8; cursor: pointer; }
.session-state{min-height:70vh;display:grid;place-items:center;color:#64748b;font-size:16px}
.skip-link {
  position: fixed;
  z-index: 10000;
  top: var(--space-2);
  left: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-brand-700);
  color: #fff;
  font-weight: 700;
  text-decoration: none;
  transform: translateY(calc(-100% - var(--space-4)));
  transition: transform var(--motion-fast);
}
.skip-link:focus { transform: translateY(0); }
#main-content:focus { outline: none; }
</style>
