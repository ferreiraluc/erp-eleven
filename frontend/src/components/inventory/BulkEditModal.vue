<template>
  <div
    class="modal-overlay erp-dialog-backdrop"
    @click.self="!saving && !photoBusy && emit('close')"
  >
    <div v-erp-dialog class="modal-container erp-dialog erp-dialog--lg">
      <div class="modal-header erp-dialog__header">
        <h2>
          {{ tr('Editar Massivo') }} <span>({{ items.length }} {{ tr('itens)') }}</span>
        </h2>
        <button
          type="button"
          :disabled="saving || photoBusy"
          data-dialog-close
          :aria-label="tr('Fechar')"
          @click="emit('close')"
          class="erp-button erp-button--secondary erp-button--icon"
        >
          ×
        </button>
      </div>
      <div class="modal-body erp-dialog__body" :inert="saving || undefined">
        <p v-if="unknownStock" role="alert" class="stock-warning">
          {{
            tr(
              'Ajustes de saldo estão bloqueados nos itens não informados; a edição dos dados do produto continua disponível.',
            )
          }}
        </p>
        <BulkDetailsEditor
          v-model="detailsDraft"
          v-model:stock="stockDraft"
          v-model:photos="photoDraft"
          v-model:reason="stockReason"
          :items="baseline"
          :brands="distinctBrands"
          :categories="distinctCategories"
          :disabled="saving"
          @busy="photoBusy = $event"
        />
      </div>
      <p v-if="saveError" role="alert" class="save-error">{{ tr(saveError) }}</p>
      <div class="modal-footer erp-dialog__footer">
        <button
          type="button"
          @click="emit('close')"
          class="erp-button erp-button--secondary"
          :disabled="saving || photoBusy"
        >
          {{ tr('Cancelar') }}
        </button>
        <button
          type="button"
          @click="save"
          class="erp-button erp-button--primary"
          :aria-busy="saving"
          :disabled="saving || photoBusy || !hasChanges"
        >
          <span v-if="saving">{{ tr('Salvando...') }}</span
          ><span v-else>{{ tr('Salvar') }} {{ items.length }} {{ tr('itens') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { useInventoryI18n } from './i18n'
import BulkDetailsEditor from './BulkDetailsEditor.vue'
import { detailsError, type DetailDraft } from '@/services/inventoryBulkDetails'
import { photoAssignments, type PhotoDraft } from '@/services/inventoryBulkPhotos'
import { initialStockDraft, changedStock, validStockDraft } from '@/services/inventoryBulkStock'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import { hasKnownStock } from '@/services/inventoryStock'
const { tr } = useInventoryI18n()
const props = defineProps<{
  items: InventoryItem[]
  distinctBrands?: string[]
  distinctCategories?: string[]
}>()
const emit = defineEmits<{ close: []; saved: [] }>()
// A background refresh must never replace the values the operator reviewed.
const baseline = props.items.map((item) => ({ ...item }))
const detailsDraft = ref<DetailDraft>({}),
  photoDraft = ref<PhotoDraft>({})
const stockDraft = ref(initialStockDraft(baseline)),
  stockReason = ref('')
const saving = ref(false),
  photoBusy = ref(false),
  saveError = ref('')
const unknownStock = computed(() => baseline.some((item) => !hasKnownStock(item)))
const hasChanges = computed(
  () =>
    Object.keys(detailsDraft.value).length > 0 ||
    Object.keys(photoDraft.value).length > 0 ||
    changedStock(baseline, stockDraft.value).length > 0,
)
async function save() {
  if (!hasChanges.value || saving.value || photoBusy.value) return
  saveError.value =
    detailsError(detailsDraft.value, baseline) ||
    (!validStockDraft(baseline, stockDraft.value)
      ? 'Confira as quantidades: use inteiros a partir de zero, dentro do limite de estoque.'
      : '')
  if (saveError.value) return
  saving.value = true
  try {
    const perItems: NonNullable<Parameters<typeof inventoryAPI.batchEdit>[0]['sizes']> = []
    for (const item of baseline) {
      if (!detailsDraft.value[item.id] && !photoDraft.value[item.id]) continue
      const entry = {
        id: item.id,
        ...detailsDraft.value[item.id],
        ...(item.updated_at ? { expected_updated_at: item.updated_at } : {}),
      }
      perItems.push(entry as (typeof perItems)[number])
    }
    await inventoryAPI.batchEdit({
      item_ids: baseline.map((item) => item.id),
      details: true,
      image_groups: photoAssignments(
        photoDraft.value,
        baseline.map((item) => item.id),
      ),
      stock_adjustments: changedStock(baseline, stockDraft.value).map((item) => ({
        id: item.id,
        stock_loja: stockDraft.value[item.id].loja,
        stock_deposito: stockDraft.value[item.id].deposito,
        expected_loja: item.stock_loja!,
        expected_deposito: item.stock_deposito!,
        expected_total: item.current_stock!,
      })),
      stock_reason: stockReason.value.trim() || undefined,
      sizes: perItems.length ? perItems : undefined,
    })
    emit('saved')
  } catch (e: unknown) {
    const error = e as {
      response?: { data?: { detail?: string | Array<{ msg?: string }> } }
      message?: string
    }
    const detail = error.response?.data?.detail
    saveError.value =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || tr('Erro ao salvar')).join('\n')
          : error.message || 'Erro ao salvar'
  } finally {
    saving.value = false
  }
}
</script>
<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2500;
  padding: 1rem;
}
.modal-container {
  background: white;
  border-radius: 14px;
  width: 100%;
  max-width: 840px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.modal-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}
.modal-header h2 span {
  font-size: 14px;
  font-weight: 400;
  color: #64748b;
}
.modal-header button {
  font-size: 24px;
}
.modal-body {
  overflow-y: auto;
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
  padding: 14px 20px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
}
.stock-warning {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
}
.save-error {
  margin: 0;
  padding: 12px 20px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
  white-space: pre-line;
}
@media (max-width: 600px) {
  .modal-body {
    padding: 14px;
  }
  .modal-header,
  .modal-footer {
    padding: 12px 14px;
  }
}
</style>
