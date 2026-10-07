<template>
  <ProductHistoryModal v-if="selected" :item-id="selected" @close="selected = ''" />
  <Teleport to="body"><div v-show="!selected" class="deleted-history-overlay" @keydown.esc.stop="emit('close')">
    <section ref="dialog" role="dialog" aria-modal="true" :aria-label="tr('Histórico de excluídos')" tabindex="-1" @keydown.tab="trapFocus">
      <header><h2>{{ tr('Histórico de excluídos') }}</h2><button class="erp-button erp-button--ghost erp-button--icon" :aria-label="tr('Fechar')" @click="emit('close')">✕</button></header>
      <main>
        <p>{{ tr('Produtos retirados do catálogo com registros preservados. Abra um produto para consultar seu histórico.') }}</p>
        <form @submit.prevent="page = 1; load()"><input v-model="search" :placeholder="tr('Buscar por nome ou SKU')" :aria-label="tr('Buscar por nome ou SKU')" maxlength="150" /><button class="erp-button erp-button--secondary erp-button--sm">{{ tr('Buscar') }}</button></form>
        <p v-if="loading" role="status">{{ tr('Carregando histórico...') }}</p>
        <div v-else-if="error" role="alert"><p>{{ tr('Não foi possível carregar o histórico do produto.') }}</p><button class="erp-button erp-button--secondary erp-button--sm" @click="load">{{ tr('Tentar novamente') }}</button></div>
        <template v-else-if="data"><p v-if="!data.items.length">{{ tr('Nenhum registro nesta seção.') }}</p>
          <ul><li v-for="item in data.items" :key="item.id"><button class="erp-control" @click="selected = item.id"><strong>{{ item.name }}</strong><code>{{ item.sku }}</code><span>{{ tr('Ver histórico e vínculos') }} →</span></button></li></ul>
          <footer v-if="data.total > data.page_size"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="page === 1" @click="page--; load()">{{ tr('Anterior') }}</button><span>{{ page }} / {{ Math.ceil(data.total / data.page_size) }}</span><button class="erp-button erp-button--secondary erp-button--sm" :disabled="page * data.page_size >= data.total" @click="page++; load()">{{ tr('Próxima') }}</button></footer>
        </template>
      </main>
    </section>
  </div></Teleport>
</template>
<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import ProductHistoryModal from './ProductHistoryModal.vue'
import { inventoryHistoryAPI } from '@/services/inventoryHistory'
import { useInventoryI18n } from './i18n'
const emit = defineEmits<{ (e: 'close'): void }>()
const { tr } = useInventoryI18n()
const dialog = ref<HTMLElement>(), search = ref(''), page = ref(1), selected = ref(''), loading = ref(true), error = ref(false)
const data = ref<Awaited<ReturnType<typeof inventoryHistoryAPI.deleted>> | null>(null)
let sequence = 0, prior: HTMLElement | null = null
async function load() { const current = ++sequence; loading.value = true; error.value = false
  try { const result = await inventoryHistoryAPI.deleted(search.value, page.value); if (current === sequence) data.value = result }
  catch { if (current === sequence) error.value = true } finally { if (current === sequence) loading.value = false }
}
function trapFocus(event: KeyboardEvent) {
  const nodes = Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input') || [])
  if (event.shiftKey && (document.activeElement === nodes[0] || document.activeElement === dialog.value)) { event.preventDefault(); nodes.at(-1)?.focus() }
  else if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0]?.focus() }
}
watch(selected, async value => { if (!value) { await nextTick(); dialog.value?.focus() } })
onMounted(async () => { prior = document.activeElement as HTMLElement; await nextTick(); dialog.value?.focus(); load() })
onUnmounted(() => { sequence++; prior?.focus() })
</script>
<style scoped>
.deleted-history-overlay{position:fixed;inset:0;z-index:12000;padding:16px;display:grid;place-items:center;background:#0f172a99;color:#334155}section{width:min(640px,100%);max-height:94dvh;display:flex;flex-direction:column;border-radius:14px;background:white}header,main{padding:16px}header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e2e8f0}h2{margin:0;font-size:18px}main{overflow:auto}p{font-size:13px;line-height:1.5}form{display:flex;gap:8px;margin:16px 0}input{min-width:0;flex:1;border:1px solid #cbd5e1;border-radius:8px;padding:8px;font-size:16px}ul{list-style:none;padding:0;display:grid;gap:10px}li button{display:flex;flex-direction:column;gap:6px;text-align:left;white-space:normal;width:100%;border:1px solid #e2e8f0;border-radius:10px;padding:12px;background:#f8fafc;color:#334155;overflow-wrap:anywhere}code,li span{font-size:12px}li span{color:#2563eb}footer{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:13px}
</style>
