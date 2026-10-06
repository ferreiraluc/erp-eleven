<template>
  <label :class="['locale-control', { 'locale-control-compact': compact }]">
    <Globe v-if="!compact" aria-hidden="true" />
    <span v-if="!compact && !hideLabel">{{ $t('access.language') }}</span>
    <select
      :aria-label="$t('access.language')"
      :title="currentLanguage?.name"
      :value="locale"
      @change="setLocale(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="lang in availableLocales" :key="lang.code" :value="lang.code" :aria-label="lang.name">
        {{ lang.flag }} {{ compact ? lang.code.toUpperCase() : lang.name }}
      </option>
    </select>
  </label>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Globe } from 'lucide-vue-next'
import { availableLocales, setLocale } from '@/i18n'

defineProps<{ compact?: boolean; hideLabel?: boolean }>()
const { locale } = useI18n()
const currentLanguage = computed(() => availableLocales.find(lang => lang.code === locale.value))
</script>

<style scoped>
.locale-control { display: inline-flex; align-items: center; gap: .45rem; margin-left: auto; }
.locale-control svg { width: 15px; height: 15px; flex: 0 0 15px; }
.locale-control select { min-height: 36px; max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; padding: .4rem .5rem; background: #fff; color: #334155; font: inherit; cursor: pointer; }
.locale-control select:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.locale-control-compact { flex: 0 0 auto; margin-left: 0; }
.locale-control-compact select { height: 32px; min-height: 32px; width: 78px; padding: .25rem .35rem; background: #f9fafb; border-color: #d1d5db; color: #475569; font-size: .75rem; font-weight: 500; }
.locale-control-compact select:hover { background: #f3f4f6; border-color: #9ca3af; }
@media (max-width: 600px) {
  .locale-control:not(.locale-control-compact) select { min-height: 40px; }
}
@media (max-width: 360px) {
  .locale-control-compact select { width: 72px; }
}
</style>
