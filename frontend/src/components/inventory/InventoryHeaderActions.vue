<template>
  <ModuleHeader :title="tr('Estoque')" class="inventory-header-actions">
    <InventoryActionsMenu :is-owner="isOwner" :diagnostics-open="diagnosticsOpen" :read-only="readOnly"
      @open-deleted="emit('open-deleted')" @toggle-diagnostics="emit('toggle-diagnostics')"
      @open-labels="emit('open-labels')" @open-import="emit('open-import')" @open-receiving="emit('open-receiving')" />
    <button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="readOnly" :title="readOnly ? tr('Acesso de consulta') : undefined" @click="!readOnly && emit('create')">
      <Plus aria-hidden="true" />{{ tr('Novo item') }}
    </button>
  </ModuleHeader>
</template>

<script setup lang="ts">
import { Plus } from 'lucide-vue-next'
import InventoryActionsMenu from './InventoryActionsMenu.vue'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { useInventoryI18n } from '@/components/inventory/i18n'

defineProps<{ isOwner: boolean; diagnosticsOpen: boolean; readOnly?: boolean }>()
const emit = defineEmits<{
  create: []
  'open-deleted': []
  'toggle-diagnostics': []
  'open-labels': []
  'open-import': []
  'open-receiving': []
}>()
const { tr } = useInventoryI18n()
</script>

<style scoped>
.inventory-header-actions{margin-bottom:0;padding-block:10px}
@media(max-width:600px){.inventory-header-actions{display:none}}
</style>
