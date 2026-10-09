<template>
  <ModuleHeader :title="tr('Estoque')">
    <button v-if="isOwner" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="emit('open-deleted')">
      {{ tr('Histórico de excluídos') }}
    </button>
    <button type="button" class="erp-button erp-button--secondary erp-button--sm" :aria-expanded="diagnosticsOpen" aria-controls="inventory-diagnostics" @click="emit('toggle-diagnostics')">
      <ClipboardCheck aria-hidden="true" />{{ diagnosticsText('open') }}
    </button>
    <button type="button" class="label-examples erp-button erp-button--secondary erp-button--sm" @click="emit('open-labels')">
      <Lightbulb aria-hidden="true" />{{ tr('Exemplos de etiquetas') }}
    </button>
    <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="emit('open-import')">
      <Upload aria-hidden="true" />{{ tr('Importar') }}
    </button>
    <button type="button" class="erp-button erp-button--primary erp-button--sm" @click="emit('create')">
      <Plus aria-hidden="true" />{{ tr('Novo item') }}
    </button>
  </ModuleHeader>
</template>

<script setup lang="ts">
import { ClipboardCheck, Lightbulb, Plus, Upload } from 'lucide-vue-next'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { useInventoryI18n } from '@/components/inventory/i18n'
import { useI18n } from 'vue-i18n'
import { diagnosticsMessages } from '@/components/inventory/diagnosticsMessages'

defineProps<{ isOwner: boolean; diagnosticsOpen: boolean }>()
const emit = defineEmits<{
  create: []
  'open-deleted': []
  'toggle-diagnostics': []
  'open-labels': []
  'open-import': []
}>()
const { tr } = useInventoryI18n()
const { t: diagnosticsText } = useI18n({ useScope: 'local', messages: diagnosticsMessages })
</script>

<style scoped>
@media (max-width: 600px) {
  .label-examples { display: none; }
}
</style>
