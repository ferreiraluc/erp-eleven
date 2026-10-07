<template>
  <div class="delete-overlay" @keydown.esc.stop.prevent="close" @keydown.tab="trapFocus">
    <section ref="dialog" class="delete-dialog" role="alertdialog" aria-modal="true" :aria-label="tr('Excluir produto definitivamente')" tabindex="-1">
      <header><h2>{{ tr('Excluir produto definitivamente') }}</h2></header>
      <main>
        <p v-if="loading" role="status">{{ tr('Conferindo vínculos do produto...') }}</p>
        <div v-else-if="error" role="alert"><p>{{ tr(error) }}</p><button class="erp-button erp-button--secondary" @click="load">{{ tr('Conferir novamente') }}</button></div>
        <template v-else-if="preview">
          <div class="product-identity"><strong>{{ preview.item.name }}</strong><span>{{ [preview.item.size, preview.item.color].filter(Boolean).join(' · ') }}</span><code>{{ preview.item.sku_internal }}</code></div>
          <template v-if="preview.allowed">
            <p>{{ tr('Esta ação apaga o produto, sua foto e as movimentações sem vínculo. Não é possível desfazer. As outras variações da grade permanecem.') }}</p>
            <dl>
              <div><dt>{{ tr('Estoque da loja') }}</dt><dd>{{ quantity(preview.item.stock_loja) }}</dd></div>
              <div><dt>{{ tr('Estoque do depósito') }}</dt><dd>{{ quantity(preview.item.stock_deposito) }}</dd></div>
              <div><dt>{{ tr('Movimentações a excluir') }}</dt><dd>{{ preview.movement_count }}</dd></div>
            </dl>
            <p class="audit-note">{{ tr('A exclusão ficará registrada na auditoria do Lucas.') }}</p>
            <label class="confirm-check"><input v-model="confirmed" type="checkbox" :disabled="busy" />{{ tr('Conferi este produto e quero excluí-lo definitivamente.') }}</label>
          </template>
          <template v-else>
            <p>{{ tr('Este produto tem vínculos operacionais e não pode ser excluído definitivamente.') }}</p>
            <ul><li v-for="blocker in preview.blockers" :key="blocker.code">{{ tr(blockerLabels[blocker.code]) }}: {{ blocker.count }}</li></ul>
          </template>
        </template>
      </main>
      <footer>
        <button class="erp-button erp-button--secondary" :disabled="busy" @click="close">{{ tr('Voltar') }}</button>
        <button v-if="preview?.allowed && !error" class="erp-button erp-button--danger" :disabled="!confirmed || busy || loading" @click="remove">{{ tr(busy ? 'Excluindo...' : 'Excluir definitivamente') }}</button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { inventoryDeletionAPI, type ItemDeletionPreview } from '@/services/inventoryDeletion'
import { useInventoryI18n } from './i18n'
const props = defineProps<{ itemId: string }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'deleted', id: string): void }>()
const { tr } = useInventoryI18n()
const preview = ref<ItemDeletionPreview | null>(null), dialog = ref<HTMLElement>()
const loading = ref(true), busy = ref(false), confirmed = ref(false), error = ref('')
let mounted = true
const blockerLabels = { sales: 'Vendas, inclusive canceladas', inventory_counts: 'Contagens de inventário', linked_movements: 'Movimentações vinculadas a outras operações' }
const quantity = (value: number | null) => value == null ? tr('Não informado') : value
function close() { if (!busy.value) emit('close') }
async function load() {
  loading.value = true; confirmed.value = false; preview.value = null; error.value = ''
  try { const result = await inventoryDeletionAPI.preview(props.itemId); if (mounted) preview.value = result }
  catch (cause: any) { if (mounted) error.value = typeof cause.response?.data?.detail === 'string' ? cause.response.data.detail : 'Não foi possível conferir os vínculos do produto.' }
  finally { if (mounted) { loading.value = false; await nextTick(); dialog.value?.focus() } }
}
async function remove() {
  if (busy.value || !confirmed.value || !preview.value?.allowed || !preview.value.plan_token) return
  busy.value = true
  try {
    const result = await inventoryDeletionAPI.remove(props.itemId, { sku: preview.value.item.sku_internal, plan_token: preview.value.plan_token, confirm: true })
    if (!result.deleted || result.id !== props.itemId) throw new Error('Deletion not confirmed')
    emit('deleted', result.id)
  } catch (cause: any) {
    confirmed.value = false; preview.value = null
    error.value = typeof cause.response?.data?.detail === 'string' ? cause.response.data.detail : 'Não foi possível confirmar a exclusão. Confira novamente antes de tentar outra vez.'
  } finally { busy.value = false }
}
function trapFocus(event: KeyboardEvent) {
  const nodes = Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled)') || [])
  if (!nodes.length) { event.preventDefault(); dialog.value?.focus(); return }
  const first = nodes[0], last = nodes[nodes.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.value)) { event.preventDefault(); first.focus() }
}
onMounted(load)
onUnmounted(() => { mounted = false })
</script>

<style scoped>
.delete-overlay { position: fixed; inset: 0; z-index: 1100; display: grid; place-items: center; padding: 1rem; background: #0f172a99; }
.delete-dialog { width: min(100%, 500px); max-height: calc(100dvh - 2rem); display: flex; flex-direction: column; background: white; border-radius: 16px; box-shadow: 0 20px 60px #0003; color: #374151; }
header, footer { padding: 1rem 1.25rem; flex-shrink: 0; }
header { border-bottom: 1px solid #e5e7eb; } h2 { margin: 0; font-size: 1.1rem; color: #111827; }
main { overflow-y: auto; padding: 1.25rem; font-size: .9rem; line-height: 1.5; } p { margin: .75rem 0; }
.product-identity { display: flex; flex-direction: column; overflow-wrap: anywhere; } .product-identity strong { color: #111827; font-size: 1rem; } code { font-size: .8rem; color: #6b7280; }
dl { padding: .75rem; background: #f8fafc; border-radius: 8px; } dl div { display: flex; justify-content: space-between; gap: 1rem; } dd { margin: 0; font-weight: 600; }
.audit-note { color: #6b7280; font-size: .8rem; } .confirm-check { display: flex; gap: .6rem; align-items: flex-start; } input { margin-top: .3rem; flex-shrink: 0; }
footer { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; border-top: 1px solid #e5e7eb; } footer button { white-space: normal; }
@media(max-width: 480px) { .delete-overlay { padding: .6rem; } .delete-dialog { max-height: calc(100dvh - 1.2rem); } main { padding: 1rem; } footer { padding: .85rem; } footer button { flex: 1; font-size: .8rem; } }
</style>
