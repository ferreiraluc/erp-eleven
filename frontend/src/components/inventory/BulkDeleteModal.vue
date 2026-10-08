<template>
  <div class="erp-dialog-backdrop bulk-delete-overlay" @keydown.esc.stop.prevent="close">
    <section v-erp-dialog class="erp-dialog erp-dialog--md bulk-delete" role="alertdialog" :aria-label="tr('Excluir itens selecionados')">
      <header class="erp-dialog__header"><h2>{{ tr('Excluir itens selecionados') }}</h2></header>
      <main class="erp-dialog__body">
        <p>{{ tr('Confira cada produto e o tipo de exclusão. Esta ação não pode ser desfeita.') }}</p>
        <p class="notice">{{ tr('Sem vínculos: apaga produto, foto e movimentações sem vínculo. Com histórico: retira do catálogo e mantém vendas e movimentações, sem estornar valores.') }}</p>
        <p v-if="loading" role="status">{{ tr('Conferindo os itens selecionados...') }}</p>
        <ul class="deletion-list">
          <li v-for="row in rows" :key="row.id" :class="{ removed: row.deleted }">
            <div class="identity"><strong>{{ row.preview?.item.name || row.name }}</strong><span v-if="row.preview">{{ [row.preview.item.size, row.preview.item.color].filter(Boolean).join(' · ') }}</span><code v-if="row.preview">{{ row.preview.item.sku_internal }}</code></div>
            <strong class="outcome" :class="{ preserved: row.preview && !row.preview.allowed }">{{ tr(row.deleted ? 'Excluído' : mode(row) === 'permanent' ? 'Excluir definitivamente' : mode(row) === 'history' ? 'Excluir e manter histórico' : 'Indisponível') }}</strong>
            <div v-if="row.preview && !row.deleted" class="details">
              <span>{{ tr('Loja:') }} {{ quantity(row.preview.item.stock_loja) }} · {{ tr('Depósito:') }} {{ quantity(row.preview.item.stock_deposito) }}</span>
              <span>{{ tr('Movimentações: {count}', { count: row.preview.movement_count }) }}</span>
              <span v-for="blocker in row.preview.blockers" :key="blocker.code">{{ tr(blockerLabels[blocker.code]) }}: {{ blocker.count }}</span>
            </div>
            <p v-if="row.error" class="error" role="alert">{{ tr(row.error) }}</p>
          </li>
        </ul>
        <p v-if="deletedCount" role="status">{{ tr('Itens excluídos: {count}', { count: deletedCount }) }}</p>
        <p v-if="busy" role="status">{{ tr('Processando item {current} de {total}...', { current: progress, total: total }) }}</p>
        <p v-if="needsReview" class="error" role="alert">{{ tr('A operação foi interrompida. Os itens concluídos não serão repetidos. Confira os pendentes antes de continuar.') }}</p>
        <label v-if="!loading && actionable.length && !needsReview" class="confirmation"><input v-model="confirmed" type="checkbox" :disabled="busy" />{{ tr('Conferi os produtos e autorizo as exclusões indicadas acima.') }}</label>
      </main>
      <footer class="erp-dialog__footer">
        <button class="erp-button erp-button--secondary" :disabled="busy" @click="close">{{ tr(deletedCount ? 'Concluir' : 'Voltar') }}</button>
        <button v-if="!loading && !busy && rows.some(row => !row.deleted && row.error)" class="erp-button erp-button--secondary" @click="load">{{ tr('Conferir pendentes novamente') }}</button>
        <button v-if="actionable.length && !needsReview" class="erp-button erp-button--danger" :disabled="!confirmed || loading || busy" @click="remove">{{ tr(busy ? 'Excluindo...' : 'Excluir {count} itens', { count: actionable.length }) }}</button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { inventoryDeletionAPI, type ItemDeletionPreview } from '@/services/inventoryDeletion'
import { useInventoryI18n } from './i18n'
const props = defineProps<{ items: Array<{ id: string; name: string }> }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'deleted', id: string): void; (e: 'settled'): void }>()
const { tr } = useInventoryI18n()
type Row = { id: string; name: string; preview?: ItemDeletionPreview; deleted: boolean; error: string }
const rows = ref<Row[]>([...new Map(props.items.map(item => [item.id, item])).values()].map(item => ({ id: item.id, name: item.name, deleted: false, error: '' })))
const loading = ref(true), busy = ref(false), confirmed = ref(false), needsReview = ref(false)
const progress = ref(0), total = ref(0)
const blockerLabels = { sales: 'Vendas, inclusive canceladas', inventory_counts: 'Contagens de inventário', linked_movements: 'Movimentações vinculadas a outras operações' }
let mounted = true
function mode(row: Row) { return row.preview?.allowed && row.preview.plan_token ? 'permanent' : !row.preview?.allowed && row.preview?.preserve_history_token ? 'history' : null }
const actionable = computed(() => rows.value.filter(row => !row.deleted && !row.error && mode(row)))
const deletedCount = computed(() => rows.value.filter(row => row.deleted).length)
const quantity = (value: number | null) => value == null ? tr('Não informado') : value
function errorMessage(cause: any, fallback: string) { return typeof cause?.response?.data?.detail === 'string' ? cause.response.data.detail : fallback }
function close() { if (!busy.value) emit('close') }
async function load() {
  if (busy.value) return
  loading.value = true; confirmed.value = false; needsReview.value = false
  const pending = rows.value.filter(row => !row.deleted)
  pending.forEach(row => { row.preview = undefined; row.error = '' })
  let index = 0
  // Bounded preview reads; each mutation remains an independently confirmed transaction.
  await Promise.all(Array.from({ length: Math.min(4, pending.length) }, async () => {
    while (mounted && index < pending.length) {
      const row = pending[index++]!
      try {
        const preview = await inventoryDeletionAPI.preview(row.id)
        if (!mounted) return
        if (preview.item.id !== row.id) throw new Error('Preview identity mismatch')
        row.preview = preview
        if (!mode(row)) row.error = 'Não foi possível conferir os vínculos do produto.'
      } catch (cause) { if (mounted) row.error = errorMessage(cause, 'Não foi possível conferir os vínculos do produto.') }
    }
  }))
  if (mounted) loading.value = false
}
async function remove() {
  if (busy.value || loading.value || !confirmed.value || needsReview.value || !actionable.value.length) return
  const pending = [...actionable.value]
  busy.value = true; total.value = pending.length; progress.value = 0
  try {
    for (const row of pending) {
      if (!mounted) break
      progress.value++
      const preview = row.preview!
      const preserve = mode(row) === 'history'
      try {
        const result = await (preserve ? inventoryDeletionAPI.preserveHistory : inventoryDeletionAPI.remove)(row.id, {
          sku: preview.item.sku_internal, plan_token: (preserve ? preview.preserve_history_token : preview.plan_token)!, confirm: true,
        })
        if (!result.deleted || result.id !== row.id) throw new Error('Deletion not confirmed')
        row.deleted = true
        if (mounted) emit('deleted', row.id)
      } catch (cause) {
        row.error = errorMessage(cause, 'Não foi possível confirmar a exclusão. Confira novamente antes de tentar outra vez.')
        needsReview.value = true
        break // Never automatically retry an uncertain destructive request or continue past a failure.
      }
    }
  } finally {
    busy.value = false; confirmed.value = false
    if (mounted) emit('settled')
  }
}
onMounted(load)
onUnmounted(() => { mounted = false })
</script>

<style scoped>
.bulk-delete-overlay { position:fixed; inset:0; z-index:1100; display:grid; place-items:center; background:#0f172a99; padding:1rem; }
.bulk-delete { width:min(100%,680px); background:white; color:#334155; border-radius:16px; max-height:calc(100dvh - 2rem); display:flex; flex-direction:column; }
header, footer { padding:1rem 1.25rem; flex-shrink:0; } h2 { font-size:1.1rem; margin:0; }
main { overflow-y:auto; padding:0 1.25rem 1rem; font-size:.875rem; } p { line-height:1.5; }
.notice { color:#64748b; font-size:.8rem; } .deletion-list { list-style:none; padding:0; margin:1rem 0; display:grid; gap:.6rem; }
li { border:1px solid #e2e8f0; border-radius:10px; padding:.75rem; display:flex; flex-wrap:wrap; gap:.4rem .75rem; align-items:start; }
.identity { display:flex; flex-direction:column; flex:1; min-width:0; overflow-wrap:anywhere; } .identity span, code { font-size:.75rem; color:#64748b; }
.outcome { font-size:.75rem; color:#b91c1c; } .preserved { color:#92400e; } .removed .outcome { color:#047857; }
.details { width:100%; display:flex; flex-wrap:wrap; gap:.3rem .75rem; font-size:.75rem; color:#64748b; }
.error { color:#b91c1c; margin:.3rem 0; width:100%; } .confirmation { display:flex; gap:.6rem; align-items:flex-start; } input { margin-top:.2rem; }
footer { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:.5rem; border-top:1px solid #e2e8f0; } footer button { white-space:normal; }
@media(max-width:500px) { .bulk-delete-overlay { padding:.6rem; } main { padding:0 1rem 1rem; } footer { padding:.75rem; } footer button { flex:1; font-size:.8rem; } }
</style>
