<template>
  <Teleport to="body">
    <div class="gallery-backdrop erp-dialog-backdrop" @click.self="emit('close')">
      <section v-erp-dialog class="erp-dialog gallery-dialog" role="dialog" aria-modal="true" :aria-label="item.name">
        <header class="erp-dialog__header"><h2>{{ item.name }}</h2><button data-dialog-close type="button" class="erp-button erp-button--secondary erp-button--icon" :aria-label="tr('Fechar')" @click="emit('close')">×</button></header>
        <div class="erp-dialog__body"><ProductGallery :cover="item.image_data || ''" :additional="additional" expanded :loading="loading" :load-error="error" @retry="load" /></div>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import ProductGallery from './ProductGallery.vue'
import { useInventoryI18n } from './i18n'
const props = defineProps<{ item: InventoryItem }>()
const emit = defineEmits<{ (e: 'close'): void }>()
const { tr } = useInventoryI18n()
const additional = ref<string[]>([]), loading = ref(false), error = ref(false)
let disposed = false
onUnmounted(() => { disposed = true })
async function load() {
  loading.value = true; error.value = false
  try { const data = await inventoryAPI.getItemPhotos(props.item.id); if (!disposed) additional.value = data.additional_images }
  catch { if (!disposed) error.value = true }
  finally { if (!disposed) loading.value = false }
}
onMounted(load)
</script>
<style scoped>
.gallery-backdrop { position:fixed; inset:0; z-index:2000; display:flex; align-items:center; justify-content:center; }
.gallery-dialog { width:min(680px,calc(100vw - 24px)); }
.gallery-dialog h2 { min-width:0; overflow-wrap:anywhere; font-size:17px; }
</style>
