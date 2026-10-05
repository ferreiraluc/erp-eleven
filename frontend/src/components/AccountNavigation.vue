<template>
  <nav :class="['account-navigation', embedded ? 'account-navigation-embedded' : 'account-bar']" :aria-label="$t('access.navigation')">
    <template v-if="auth.isAuthenticated">
      <template v-if="!embedded">
        <RouterLink to="/dashboard" class="brand">ELEVEN</RouterLink>
        <span class="account-name">{{ auth.userName }}</span>
      </template>
      <div class="account-links">
        <RouterLink to="/conta"><UserRound aria-hidden="true" />{{ $t('access.account') }}</RouterLink>
        <template v-if="auth.isOwner">
          <RouterLink to="/usuarios"><UsersRound aria-hidden="true" />{{ $t('access.users') }}</RouterLink>
          <RouterLink to="/auditoria"><ShieldCheck aria-hidden="true" />{{ $t('access.audit') }}</RouterLink>
        </template>
        <button type="button" @click="logoutToLogin(auth, router)"><LogOut aria-hidden="true" />{{ $t('common.logout') }}</button>
      </div>
    </template>
    <label class="locale-control">
      <Globe aria-hidden="true" />
      <span v-if="!embedded">{{ $t('access.language') }}</span>
      <select :aria-label="$t('access.language')" :value="locale" @change="setLocale(($event.target as HTMLSelectElement).value)">
        <option v-for="lang in availableLocales" :key="lang.code" :value="lang.code">{{ lang.name }}</option>
      </select>
    </label>
  </nav>
</template>

<script setup lang="ts">
import { RouterLink, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Globe, LogOut, ShieldCheck, UserRound, UsersRound } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { availableLocales, setLocale } from '@/i18n'
import { logoutToLogin } from '@/services/logoutNavigation'

defineProps<{ embedded?: boolean }>()
const auth = useAuthStore(), router = useRouter()
const { locale } = useI18n()
</script>

<style scoped>
.account-navigation { display: flex; align-items: center; flex-wrap: wrap; gap: .75rem; color: #64748b; font-size: .75rem; }
.account-bar { min-height: 42px; padding: .5rem 1.5rem; background: #fff; border-bottom: 1px solid #e2e8f0; }
.brand { font-weight: 800; letter-spacing: .14em; color: #2563eb; text-decoration: none; }
.account-name { margin-right: auto; font-weight: 600; overflow-wrap: anywhere; }
.account-links { display: flex; align-items: center; flex-wrap: wrap; gap: .25rem; }
.account-links a, .account-links button { display: inline-flex; align-items: center; justify-content: center; gap: .4rem; min-height: 36px; padding: .45rem .6rem; border: 1px solid transparent; border-radius: 8px; background: transparent; color: #475569; cursor: pointer; font: inherit; font-weight: 500; text-decoration: none; white-space: nowrap; }
.account-links a:hover, .account-links button:hover { color: #1d4ed8; background: #eff6ff; }
.account-links a.router-link-active { color: #1d4ed8; background: #eff6ff; border-color: #dbeafe; }
.account-links a:focus-visible, .account-links button:focus-visible, select:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.account-navigation svg { width: 15px; height: 15px; flex: 0 0 15px; }
.locale-control { display: inline-flex; align-items: center; gap: .45rem; margin-left: auto; }
.locale-control select { min-height: 36px; max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; padding: .4rem .5rem; background: #fff; color: #334155; font: inherit; cursor: pointer; }
.account-navigation-embedded { justify-content: flex-end; gap: .5rem; }
.account-navigation-embedded .locale-control { margin-left: 0; }
@media (max-width: 600px) {
  .account-bar { padding: .5rem .75rem; gap: .5rem; }
  .account-links a, .account-links button { min-height: 40px; padding: .5rem; }
  .account-navigation-embedded { width: 100%; justify-content: space-between; }
  .account-navigation-embedded .account-links { gap: .15rem; }
  .locale-control select { min-height: 40px; }
}
</style>
