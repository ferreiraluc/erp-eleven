<template>
  <div id="app">
    <nav class="account-bar" :aria-label="$t('access.navigation')">
      <template v-if="auth.isAuthenticated">
        <RouterLink to="/dashboard" class="brand">ELEVEN</RouterLink>
        <span class="account-name">{{ auth.userName }}</span>
        <RouterLink to="/conta">{{ $t('access.account') }}</RouterLink>
        <template v-if="auth.isOwner">
          <RouterLink to="/usuarios">{{ $t('access.users') }}</RouterLink>
          <RouterLink to="/auditoria">{{ $t('access.audit') }}</RouterLink>
        </template>
        <button @click="logout">{{ $t('common.logout') }}</button>
      </template>
      <label class="locale-control"><span>{{ $t('access.language') }}</span><select :value="locale" @change="setLocale(($event.target as HTMLSelectElement).value)"><option v-for="lang in availableLocales" :key="lang.code" :value="lang.code">{{ lang.name }}</option></select></label>
    </nav>
    <div v-if="auth.status === 'checking'" class="session-state" role="status">{{ $t('access.checking') }}</div>
    <section v-else-if="auth.status === 'error' && route.meta.requiresAuth" class="session-state session-error" role="alert">
      <p>{{ $t('access.connectionError') }}</p>
      <div><button @click="retrySession">{{ $t('common.refresh') }}</button><button @click="logout">{{ $t('common.logout') }}</button></div>
    </section>
    <RouterView v-else-if="!route.meta.requiresAuth || auth.isAuthenticated" :key="auth.user?.id || 'guest'" />
    <NotificationToast />
  </div>
</template>
<script setup lang="ts">
import { RouterView, RouterLink, useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { availableLocales, setLocale } from '@/i18n'
import NotificationToast from '@/components/NotificationToast.vue'
const auth = useAuthStore(), router = useRouter(), route = useRoute()
const { locale } = useI18n()
async function retrySession() {
  const ownerToken = auth.token
  const valid = await auth.ensureSession(true)
  if (auth.isLoading || (auth.token !== ownerToken && auth.token)) return
  if (valid && auth.user?.must_change_password) await router.replace('/conta')
  else if (!valid && auth.status === 'guest') await router.replace('/login')
}
function logout() {
  const completion = auth.logout().catch(() => {})
  // The store expires locally before awaiting revocation. Do not navigate again
  // when its network response arrives and another account may already be active.
  if (auth.status === 'guest' && !auth.isLoading) void router.replace('/login')
  return completion
}
</script>
<style>
.session-error { align-content: center; gap: 1rem; padding: 1.5rem; text-align: center; }
.session-error p { max-width: 36rem; margin: 0; }
.session-error button { margin: 0 .4rem; padding: .55rem .9rem; border: 1px solid #cbd5e1; border-radius: 8px; background: white; color: #1d4ed8; cursor: pointer; }
.account-bar{display:flex;align-items:center;gap:16px;min-height:42px;padding:8px 24px;background:#fff;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;flex-wrap:wrap}.account-bar .brand{font-weight:800;letter-spacing:.14em;color:#2563eb}.account-bar a{color:#475569;text-decoration:none}.account-bar a.router-link-active:not(.brand){color:#2563eb}.account-bar button{border:0;background:transparent;color:#64748b;cursor:pointer;font:inherit}.account-name{margin-right:auto;font-weight:600}.locale-control{display:flex;align-items:center;gap:8px;margin-left:auto}.locale-control select{border:1px solid #e2e8f0;border-radius:7px;padding:5px;background:white;color:#334155}.session-state{min-height:70vh;display:grid;place-items:center;color:#64748b;font-size:16px}@media(max-width:600px){.account-bar{padding:8px 12px;gap:10px}.account-name{max-width:120px;overflow:hidden;white-space:nowrap}.locale-control span{display:none}}
</style>
