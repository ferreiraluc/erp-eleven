<template>
  <ModuleHeader :title="tr('Estoque')" class="inventory-header-actions">
    <InventoryActionsMenu :is-owner="isOwner" :diagnostics-open="diagnosticsOpen"
      @open-deleted="emit('open-deleted')" @toggle-diagnostics="emit('toggle-diagnostics')"
      @open-labels="emit('open-labels')" @open-import="emit('open-import')" />
    <button type="button" class="erp-button erp-button--primary erp-button--sm" @click="emit('create')">
      <Plus aria-hidden="true" />{{ tr('Novo item') }}
    </button>
  </ModuleHeader>
</template>

<script setup lang="ts">
import { Plus } from 'lucide-vue-next'
import InventoryActionsMenu from './InventoryActionsMenu.vue'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { useInventoryI18n } from '@/components/inventory/i18n'

defineProps<{ isOwner: boolean; diagnosticsOpen: boolean }>()
const emit = defineEmits<{
  create: []
  'open-deleted': []
  'toggle-diagnostics': []
  'open-labels': []
  'open-import': []
}>()
const { tr } = useInventoryI18n()
</script>

<style scoped>
.inventory-header-actions{margin-bottom:0;padding-block:10px}
@media(max-width:600px){.inventory-header-actions{display:none}}
</style>
