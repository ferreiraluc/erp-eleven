<template>
  <Teleport to="body"><div class="erp-dialog-backdrop" @click.self="close"><section v-erp-dialog class="erp-dialog erp-dialog--md archive-dialog" aria-labelledby="archive-orders-title">
    <header class="erp-dialog__header"><h2 id="archive-orders-title">{{ uiText('Arquivar pedidos anteriores') }}</h2><button data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="uiText('Fechar')" :disabled="busy || uncertain" @click="close">×</button></header>
    <div class="erp-dialog__body">
      <p>{{ uiText('Comece uma lista nova mantendo clientes, pagamentos, vendas e rastreios no histórico. Nenhum registro será excluído.') }}</p>
      <p v-if="loading" role="status">{{ uiText('Conferindo pedidos…') }}</p>
      <template v-if="preview">
        <div class="archive-count"><strong>{{ preview.eligible_count }}</strong><span>{{ uiText('pedidos a arquivar') }}</span></div>
        <p v-if="!preview.allowed" class="archive-warning" role="alert">{{ uiText('Existem pedidos com peças reservadas ou em condicional. Conclua essas pendências antes de arquivar a lista.') }}</p>
        <ul v-if="!preview.allowed"><li v-for="item in preview.blockers" :key="item.id">{{ item.numero_pedido }} · {{ item.cliente_nome }} · {{ reservationStatusLabel(item.commerce_status) }}</li></ul>
        <details v-if="preview.sample.length"><summary>{{ uiText('Conferir pedidos que serão arquivados') }}</summary><ul><li v-for="item in preview.sample" :key="item.id">{{ item.numero_pedido }} · {{ item.cliente_nome }}</li></ul></details>
        <label v-if="preview.allowed && preview.eligible_count > 0" class="archive-confirm"><input v-model="confirmed" type="checkbox" :disabled="busy || uncertain" />{{ uiText('Conferi os pedidos. Quero arquivar esta lista e preservar o histórico.') }}</label>
      </template>
      <p v-if="error" class="archive-warning" role="alert">{{ error }}</p>
      <p v-if="uncertain" role="alert">{{ uiText('Resposta não confirmada. Repetir recupera a mesma solicitação sem duplicar a operação.') }}</p>
      <button v-if="!preview && !loading && !uncertain" class="erp-button erp-button--secondary" @click="load">{{ uiText('Tentar novamente') }}</button>
    </div>
    <footer class="erp-dialog__footer"><button class="erp-button erp-button--secondary" :disabled="busy || uncertain" @click="close">{{ uiText('Cancelar') }}</button><button class="erp-button erp-button--primary" :disabled="busy || (!uncertain && (!preview?.allowed || !preview.eligible_count || !confirmed))" @click="archive">{{ uiText(busy ? 'Processando…' : uncertain ? 'Repetir confirmação' : 'Arquivar lista') }}</button></footer>
  </section></div></Teleport>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { useAuthStore } from '@/stores/auth'
import { uiText } from '@/i18n/uiText'
import { orderArchive, type ArchivePreview, type ArchiveCommand } from '@/services/orderArchive'
import { reservationError, reservationStatusLabel } from '@/services/orderReservations'
const emit = defineEmits<{ close: []; archived: [] }>()
const auth = useAuthStore(), preview = ref<ArchivePreview | null>(null), loading = ref(false), busy = ref(false), confirmed = ref(false), uncertain = ref(false), error = ref('')
const storageKey = `eleven.order-archive.${auth.user?.id || ''}`
let pending: ArchiveCommand | null = null, disposed = false
function stash() { try { if (pending) sessionStorage.setItem(storageKey, JSON.stringify(pending)); else sessionStorage.removeItem(storageKey) } catch { /* in-memory retry remains available */ } }
function close() { if (!busy.value && !uncertain.value) emit('close') }
async function load() { if (!auth.isOwner) return; loading.value = true; error.value = ''; try { const value = await orderArchive.preview(); if (!disposed) preview.value = value } catch (caught) { if (!disposed) error.value = reservationError(caught) } finally { if (!disposed) loading.value = false } }
async function archive() {
  if (!auth.isOwner || busy.value || (!pending && (!preview.value?.allowed || !preview.value.eligible_count || !confirmed.value))) return
  pending ||= { request_id: crypto.randomUUID(), confirm: true, plan_token: preview.value!.plan_token, expected_count: preview.value!.total }
  stash(); busy.value = true; error.value = ''
  try { await orderArchive.confirm(pending); pending = null; stash(); uncertain.value = false; if (!disposed) emit('archived') }
  catch (caught) { const status = (caught as { response?: { status?: number } })?.response?.status; uncertain.value = !status || status >= 500; if (!uncertain.value) { pending = null; stash(); confirmed.value = false; preview.value = null } if (!disposed) error.value = reservationError(caught) }
  finally { busy.value = false }
}
onMounted(() => { try { const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null'); if (saved?.request_id && saved.plan_token && saved.confirm === true && Number.isInteger(saved.expected_count)) { pending = saved; uncertain.value = true } } catch { /* no usable saved request */ } if (!uncertain.value) void load() })
onBeforeUnmount(() => { disposed = true })
</script>
<style scoped>
.erp-dialog-backdrop{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:1000}.archive-dialog{max-width:560px}.archive-dialog h2{font-size:1.1rem}.archive-dialog p,.archive-dialog li,.archive-dialog summary{font-size:.84rem;line-height:1.6}.archive-count{display:flex;gap:12px;align-items:center;background:#eff6ff;color:#1e3a5f;border-radius:12px;padding:16px;margin:16px 0}.archive-count strong{font-size:1.5rem}.archive-count span{font-size:.85rem}.archive-confirm{display:flex;gap:10px;align-items:flex-start;font-size:.85rem;line-height:1.6;margin-top:20px}.archive-confirm input{margin-top:5px;accent-color:#2563eb}.archive-warning{color:#9a3412;background:#fff7ed;padding:12px;border-radius:10px}.archive-dialog ul{max-height:200px;overflow:auto;padding-left:20px}.archive-dialog summary{cursor:pointer;color:#2563eb}
</style>
