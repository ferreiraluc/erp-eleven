<template>
  <div class="locale-control" :class="{ 'locale-control-compact': compact }">
    <Globe v-if="!compact" aria-hidden="true" />
    <span v-if="!compact && !hideLabel">{{ $t('access.language') }}</span>
    <ErpDropdown
      :model-value="locale"
      :options="options"
      :compact="compact"
      :align="align"
      :label="$t('access.language')"
      :title="currentLanguage.name"
      @update:model-value="setLocale"
    />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Globe } from 'lucide-vue-next'
import { availableLocales, setLocale } from '@/i18n'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
const props = defineProps<{ compact?: boolean; hideLabel?: boolean; align?: 'start' | 'end' }>()
const { locale } = useI18n()
const currentLanguage = computed(
  () => availableLocales.find((lang) => lang.code === locale.value) ?? availableLocales[2]!,
)
const options = computed(() =>
  availableLocales.map((lang) => ({
    value: lang.code,
    label: lang.code.toUpperCase(),
    description: lang.name,
    icon: lang.flag,
    triggerLabel: props.compact ? lang.code.toUpperCase() : lang.name,
  })),
)
</script>
<style scoped>
.locale-control {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin-left: auto;
  min-width: 0;
}
.locale-control > svg {
  width: 15px;
  height: 15px;
  flex: 0 0 15px;
}
.locale-control > .erp-dropdown {
  width: auto;
  min-width: 130px;
}
.locale-control-compact {
  flex: 0 0 auto;
  margin-left: 0;
}
.locale-control-compact > .erp-dropdown {
  width: 78px;
  min-width: 0;
}
@media (max-width: 360px) {
  .locale-control-compact > .erp-dropdown {
    width: 72px;
  }
}
</style>
