<template>
  <div class="inventory-stats" :aria-label="tr('Resumo do estoque')">
    <span class="stat"><strong>{{ summary.total_active_items }}</strong><span>{{ tr('itens') }}</span></span>
    <span class="separator" aria-hidden="true">·</span>
    <span class="stat"><strong>{{ summary.group_count }}</strong><span>{{ tr('grades') }}</span></span>
    <span class="separator" aria-hidden="true">·</span>
    <button type="button" class="stat stat-button erp-control" :class="{ active: ungroupedOnly }" :aria-pressed="ungroupedOnly" :aria-label="tr('Filtrar itens sem grade')" @click="emit('toggle-ungrouped')">
      <strong>{{ ungroupedCount }}</strong><span>{{ tr('sem grade') }}</span>
    </button>
    <template v-if="summary.low_stock_count > 0">
      <span class="separator" aria-hidden="true">·</span>
      <button type="button" class="stat stat-button warning erp-control" :class="{ active: status === 'low_stock' }" :aria-pressed="status === 'low_stock'" :aria-label="tr('Filtrar estoque baixo')" @click="emit('status', status === 'low_stock' ? '' : 'low_stock')">
        <strong>{{ summary.low_stock_count }}</strong><span>{{ tr('baixo') }}</span>
      </button>
    </template>
    <template v-if="summary.out_of_stock_count > 0">
      <span class="separator" aria-hidden="true">·</span>
      <button type="button" class="stat stat-button danger erp-control" :class="{ active: status === 'out_of_stock' }" :aria-pressed="status === 'out_of_stock'" :aria-label="tr('Filtrar sem estoque')" @click="emit('status', status === 'out_of_stock' ? '' : 'out_of_stock')">
        <strong>{{ summary.out_of_stock_count }}</strong><span>{{ tr('sem estoque') }}</span>
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AlertSummary } from '@/services/api'
import { useInventoryI18n } from '@/components/inventory/i18n'

const props = defineProps<{ summary: AlertSummary; status: string; ungroupedOnly: boolean }>()
const emit = defineEmits<{ status: [value: string]; 'toggle-ungrouped': [] }>()
const { tr } = useInventoryI18n()
const ungroupedCount = computed(() => Math.max(0, props.summary.total_active_items - props.summary.grouped_items_count))
</script>

<style scoped>
.inventory-stats{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:5px 2px 4px;color:#64748b;font-size:.75rem}.stat{display:inline-flex;align-items:baseline;gap:3px}.stat strong{color:#374151}.separator{color:#cbd5e1}.stat-button{padding:3px 6px;border:0;border-radius:var(--radius-sm);background:transparent;color:#64748b;cursor:pointer;font:inherit}.stat-button:hover,.stat-button.active{background:#e2e8f0}.stat-button.warning strong,.stat-button.warning span{color:#b45309}.stat-button.warning:hover,.stat-button.warning.active{background:#fef3c7}.stat-button.danger strong,.stat-button.danger span{color:#b91c1c}.stat-button.danger:hover,.stat-button.danger.active{background:#fee2e2}
</style>
