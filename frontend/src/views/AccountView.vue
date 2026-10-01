<template>
  <main class="access-page account-page">
    <header class="access-head"><div><h1>{{ $t('access.account') }}</h1><p>{{ auth.userName }} · {{ auth.user?.email }}</p></div><RouterLink v-if="!auth.user?.must_change_password" class="button" to="/dashboard">{{ $t('access.back') }}</RouterLink></header>
    <p v-if="auth.user?.must_change_password" class="notice">{{ $t('access.firstPassword') }}</p>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <section class="access-card"><h2>{{ $t('access.changePassword') }}</h2><p>{{ $t('access.passwordHelp') }}</p>
      <form @submit.prevent="submit"><div class="password-fields">
        <label>{{ $t('access.currentPassword') }}<input v-model="current" type="password" autocomplete="current-password" required /></label>
        <label>{{ $t('access.newPassword') }}<input v-model="password" type="password" autocomplete="new-password" minlength="6" maxlength="72" required /></label>
        <label>{{ $t('access.confirmPassword') }}<input v-model="confirm" type="password" autocomplete="new-password" minlength="6" maxlength="72" required /></label>
      </div><div class="actions"><button class="primary" :disabled="saving">{{ saving ? $t('common.loading') : $t('access.savePassword') }}</button></div></form>
    </section>
    <p class="muted">{{ $t('access.activityNotice') }}</p>
  </main>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore(), router = useRouter(), { t } = useI18n()
const current = ref(''), password = ref(''), confirm = ref(''), error = ref(''), saving = ref(false)
async function submit() {
  error.value = ''
  if (password.value !== confirm.value) { error.value = t('access.passwordMismatch'); return }
  saving.value = true
  try { await auth.changePassword(current.value,password.value); await router.replace('/dashboard') }
  catch(e) { error.value = axios.isAxiosError(e) && e.response?.status === 400 ? t('access.passwordRejected') : t('access.connectionError') }
  finally { saving.value = false; current.value=''; password.value=''; confirm.value='' }
}
</script>
<style scoped src="@/components/access/access.css"></style>
<style scoped>.account-page{max-width:720px}.password-fields{display:grid;gap:20px}</style>
