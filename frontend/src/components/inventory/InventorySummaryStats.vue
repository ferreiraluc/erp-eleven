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
      <span class="stat warning">
        <strong>{{ summary.low_stock_count }}</strong><span>{{ tr('baixo') }}</span>
      </span>
    </template>
    <template v-if="summary.out_of_stock_count > 0">
      <span class="separator" aria-hidden="true">·</span>
      <span class="stat danger">
        <strong>{{ summary.out_of_stock_count }}</strong><span>{{ tr('sem estoque') }}</span>
      </span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AlertSummary } from '@/services/api'
import { useInventoryI18n } from '@/components/inventory/i18n'

const props = defineProps<{ summary: AlertSummary; ungroupedOnly: boolean }>()
const emit = defineEmits<{ 'toggle-ungrouped': [] }>()
const { tr } = useInventoryI18n()
const ungroupedCount = computed(() => Math.max(0, props.summary.total_active_items - props.summary.grouped_items_count))
</script>

<style scoped>
.inventory-stats{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:5px 2px 4px;color:#64748b;font-size:.75rem}.stat{display:inline-flex;align-items:baseline;gap:3px}.stat strong{color:#374151}.separator{color:#cbd5e1}.stat-button{padding:3px 6px;border:0;border-radius:var(--radius-sm);background:transparent;color:#64748b;cursor:pointer;font:inherit}.stat-button:hover,.stat-button.active{background:#e2e8f0}.stat.warning strong,.stat.warning span{color:#b45309}.stat.danger strong,.stat.danger span{color:#b91c1c}
</style>
