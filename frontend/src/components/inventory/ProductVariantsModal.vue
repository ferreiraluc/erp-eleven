<template>
  <ItemFormModal
    v-if="context"
    :key="revision"
    :grade-context="context"
    @close="emit('close')"
    @reload-grade="load"
    @variants-created="emit('saved', $event)"
  />
  <div v-else class="erp-dialog-backdrop">
    <section
      v-erp-dialog
      class="erp-dialog erp-dialog--compact"
      role="dialog"
      aria-modal="true"
      :aria-label="tr('Adicionar grade')"
    >
      <header class="erp-dialog__header">
        <h2>{{ tr('Adicionar grade') }}</h2>
        <button
          data-dialog-close
          type="button"
          class="erp-button erp-button--secondary erp-button--icon"
          @click="emit('close')"
         :aria-label="tr('Fechar')">
          ×
        </button>
      </header>
      <div class="erp-dialog__body">
        <p role="status">{{ tr(loading ? 'Carregando...' : error) }}</p>
      </div>
      <footer class="erp-dialog__footer">
        <button v-if="!loading" type="button" class="erp-button erp-button--primary" @click="load">
          {{ tr('Tentar novamente') }}</button
        ><button type="button" class="erp-button erp-button--secondary" @click="emit('close')">
          {{ tr('Cancelar') }}
        </button>
      </footer>
    </section>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import ItemFormModal from './ItemFormModal.vue'
import { vErpDialog } from '@/directives/erpDialog'
import {
  inventoryVariantsAPI,
  type VariantContext,
  type VariantResult,
} from '@/services/inventoryVariants'
import { useInventoryI18n } from './i18n'
const props = defineProps<{ itemId: string; mode: 'duplicate' | 'grade' }>()
const emit = defineEmits<{ close: []; saved: [result: VariantResult] }>()
const { tr } = useInventoryI18n()
const context = ref<VariantContext>(),
  loading = ref(false),
  error = ref(''),
  revision = ref(0)
let disposed = false
async function load() {
  if (loading.value) return
  loading.value = true
  context.value = undefined
  try {
    const value = await inventoryVariantsAPI.context(props.itemId, true)
    if (!disposed) {
      context.value = value
      revision.value++
    }
  } catch {
    error.value = 'Não foi possível carregar o produto. Tente novamente.'
  } finally {
    loading.value = false
  }
}
onMounted(load)
onBeforeUnmount(() => {
  disposed = true
})
</script>

<style scoped>
.erp-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
