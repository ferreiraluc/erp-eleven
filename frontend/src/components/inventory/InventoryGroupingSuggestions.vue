<template>
  <aside class="suggestions" :aria-label="tr('Similares detectados:')">
    <strong>{{ tr('Similares detectados:') }}</strong>
    <button v-for="suggestion in suggestions.slice(0, 4)" :key="suggestion.name" type="button" class="suggestion erp-control"
      :aria-label="tr('{count} itens com nome similar', { count: suggestion.items.length })" @click="emit('select', suggestion)">
      {{ suggestion.name }} <span aria-hidden="true">({{ suggestion.items.length }})</span>
    </button>
  </aside>
</template>

<script setup lang="ts">
import type { SuggestionResponse } from '@/services/api'
import { useInventoryI18n } from '@/components/inventory/i18n'

defineProps<{ suggestions: SuggestionResponse[] }>()
const emit = defineEmits<{ select: [suggestion: SuggestionResponse] }>()
const { tr } = useInventoryI18n()
</script>

<style scoped>
.suggestions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:6px;padding:7px 9px;border:1px solid #fcd34d;border-radius:var(--radius-sm);background:#fffbeb}.suggestions>strong{color:#92400e;font-size:.72rem;white-space:nowrap}.suggestion{padding:4px 9px;border:1px solid #fbbf24;border-radius:999px;background:#fef3c7;color:#92400e;cursor:pointer;font:inherit;font-size:.72rem;white-space:nowrap;transition:background-color var(--motion-fast)}.suggestion:hover{background:#fde68a}
</style>
