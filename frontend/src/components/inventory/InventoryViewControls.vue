<template>
  <div class="view-controls">
    <div class="view-options" role="group" :aria-label="tr('Visualização:')">
      <span class="view-label" aria-hidden="true">{{ tr('Visualização:') }}</span>
      <button v-for="option in options" :key="option.value" type="button" class="view-button erp-control"
        :class="{ active: mode === option.value }" :aria-label="tr(option.label)" :title="tr(option.label)" :aria-pressed="mode === option.value" @click="emit('mode', option.value)">
        <component :is="option.icon" aria-hidden="true" /><span class="view-name">{{ tr(option.label) }}</span>
      </button>
    </div>
    <div class="selection-results">
      <button type="button" class="view-button erp-control" :class="{ active: selectionMode }" :aria-pressed="selectionMode" @click="emit('toggle-selection')">
        {{ tr('Selecionar') }}
      </button>
      <span class="result-count search-result-count" role="status" aria-live="polite" aria-atomic="true">
        <span v-if="busy" class="spinner" aria-hidden="true" />
        {{ busy ? tr('Buscando...') : ready ? resultText : tr('Total não confirmado') }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Grid2X2, List, Rows3 } from 'lucide-vue-next'
import { useInventoryI18n } from '@/components/inventory/i18n'

export type InventoryViewMode = 'list' | 'compact' | 'grid'
defineProps<{ mode: InventoryViewMode; selectionMode: boolean; busy: boolean; ready: boolean; resultText: string }>()
const emit = defineEmits<{ mode: [value: InventoryViewMode]; 'toggle-selection': [] }>()
const { tr } = useInventoryI18n()
const options = [
  { value: 'list' as const, label: 'Lista', icon: List },
  { value: 'compact' as const, label: 'Compacto', icon: Rows3 },
  { value: 'grid' as const, label: 'Quadrados', icon: Grid2X2 },
]
</script>

<style scoped>
.view-controls,.view-options,.selection-results{display:flex;align-items:center;gap:6px;min-width:0}.view-controls{justify-content:space-between;flex-wrap:wrap}.view-options{flex-wrap:wrap}.view-label{margin-right:2px;color:#64748b;font-size:.75rem}.view-button{display:inline-flex;align-items:center;gap:5px;min-height:34px;padding:6px 10px;border:1px solid var(--color-border);border-radius:999px;background:#fff;color:#556277;cursor:pointer;font:inherit;font-size:.75rem;white-space:nowrap;transition:background-color var(--motion-fast),border-color var(--motion-fast),color var(--motion-fast)}.view-button:hover{border-color:#94a3b8;color:#334155}.view-button.active{border-color:var(--color-brand-600);background:var(--color-brand-100);color:var(--color-brand-700)}.view-button :deep(svg){width:16px;height:16px}.result-count{display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border-radius:999px;background:var(--color-brand-50);color:var(--color-brand-700);font-size:.75rem;font-weight:600}.spinner{width:12px;height:12px;flex:none;border:2px solid var(--color-brand-100);border-top-color:var(--color-brand-600);border-radius:50%;animation:inventory-spin .8s linear infinite}@keyframes inventory-spin{to{transform:rotate(360deg)}}@media(max-width:600px){.view-label{display:none}.view-button{min-height:30px;padding:5px 8px}.view-controls{gap:6px;flex-wrap:nowrap}.view-options{flex-wrap:nowrap;gap:4px}.view-name{display:none}.selection-results{flex:1;justify-content:flex-end;gap:5px}.result-count{padding:5px;font-size:.7rem;white-space:nowrap}}
</style>
