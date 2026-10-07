<template>
  <header class="erp-module-header">
    <div class="erp-module-header__heading">
      <button
        v-if="showBack"
        type="button"
        class="erp-button erp-button--ghost erp-button--icon"
        :aria-label="uiText('Voltar ao dashboard')"
        :title="uiText('Voltar ao dashboard')"
        @click="$router.replace('/dashboard')"
      >
        <ArrowLeft :size="18" aria-hidden="true" />
      </button>
      <div class="erp-module-header__text">
        <h1>{{ title }}</h1>
        <div v-if="$slots.meta" class="erp-module-header__meta"><slot name="meta" /></div>
      </div>
    </div>
    <div v-if="$slots.default" class="erp-module-header__actions"><slot /></div>
  </header>
</template>

<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'
import { uiText } from '@/i18n/uiText'

withDefaults(defineProps<{ title: string; showBack?: boolean }>(), { showBack: true })
</script>

<style scoped>
.erp-module-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 20px;
  flex-shrink: 0;
  padding: 16px 24px;
  margin: 0 0 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  color: #111827;
}
.erp-module-header__heading {
  display: flex;
  align-items: center;
  flex: 1 1 auto;
  gap: 12px;
  min-width: 0;
  max-width: 100%;
}
.erp-module-header__text { min-width: 0; }
.erp-module-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -.02em;
  overflow-wrap: break-word;
}
.erp-module-header__meta {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.erp-module-header__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  max-width: 100%;
  margin-left: auto;
}
/* Header density is shared; each page retains action visibility and permissions. */
:is(#app, body) .erp-module-header :deep(.erp-button) {
  min-height: 34px;
  padding: 7px 10px;
  font-size: 12px;
  line-height: 18px;
  gap: 6px;
  width: auto;
  flex: 0 1 auto;
  margin: 0;
}
:is(#app, body) .erp-module-header :deep(.erp-button--icon) {
  width: 34px;
  min-width: 34px;
  height: 34px;
  padding: 7px;
  flex-shrink: 0;
}
@media (max-width: 600px) {
  .erp-module-header { padding: 12px; gap: 10px 12px; margin-bottom: 12px; }
  .erp-module-header__heading { flex-basis: min-content; gap: 8px; }
  .erp-module-header h1 { font-size: 16px; }
  .erp-module-header__actions { gap: 6px; }
  :is(#app, body) .erp-module-header :deep(.erp-button) {
    min-height: 32px;
    padding: 6px 8px;
    font-size: 12px;
    line-height: 18px;
    gap: 5px;
  }
  :is(#app, body) .erp-module-header :deep(.erp-button--icon) {
    width: 32px;
    min-width: 32px;
    height: 32px;
    padding: 6px;
  }
}
</style>
