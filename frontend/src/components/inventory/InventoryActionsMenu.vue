<template>
    <details class="more-actions" @keydown.esc="($event.currentTarget as HTMLDetailsElement).open = false">
      <summary class="erp-button erp-button--secondary erp-button--sm" :class="{ 'actions-icon': compact }" :aria-label="tr('Mais ações')"><span v-if="!compact">{{ tr('Mais ações') }} <span aria-hidden="true">▾</span></span><span v-else aria-hidden="true">•••</span></summary>
      <div class="more-actions-menu" @click="($event.currentTarget as HTMLElement).closest('details')?.removeAttribute('open')">
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
      </div>
    </details>
</template>

<script setup lang="ts">
import { ClipboardCheck, Lightbulb, Upload } from 'lucide-vue-next'
import { useInventoryI18n } from '@/components/inventory/i18n'
import { useI18n } from 'vue-i18n'
import { diagnosticsMessages } from '@/components/inventory/diagnosticsMessages'

defineProps<{ isOwner: boolean; diagnosticsOpen: boolean; compact?: boolean }>()
const emit = defineEmits<{
  'open-deleted': []
  'toggle-diagnostics': []
  'open-labels': []
  'open-import': []
}>()
const { tr } = useInventoryI18n()
const { t: diagnosticsText } = useI18n({ useScope: 'local', messages: diagnosticsMessages })
</script>
<style scoped>
.more-actions{position:relative}.more-actions summary{list-style:none;cursor:pointer;border-radius:999px!important}.more-actions summary::-webkit-details-marker{display:none}
.more-actions-menu{position:absolute;right:0;top:calc(100% + 6px);z-index:60;display:flex;flex-direction:column;align-items:stretch;gap:4px;min-width:220px;padding:7px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;box-shadow:0 8px 24px #0f172a18}
.more-actions-menu :deep(button){justify-content:flex-start!important;min-height:34px!important;font-size:12px!important}
.actions-icon{width:32px!important;min-width:32px!important;height:32px!important;min-height:32px!important;padding:0!important;font-size:13px!important}
</style>
