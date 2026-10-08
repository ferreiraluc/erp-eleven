<template>
  <Teleport to="body">
    <div class="history-overlay erp-dialog-backdrop" @keydown.esc.stop.prevent="emit('close')" @keydown.tab="trapFocus">
      <section v-erp-dialog ref="dialog" class="history-dialog erp-dialog erp-dialog--lg" role="dialog" aria-modal="true" :aria-label="tr('Histórico do produto')" tabindex="-1">
        <header class="erp-dialog__header"><h2>{{ tr('Histórico do produto') }}</h2><button data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="tr('Fechar')" @click="emit('close')">✕</button></header>
        <main class="erp-dialog__body" ref="body">
          <section v-if="data" class="history-product">
            <h3>{{ data.product.name }}</h3><p>{{ [data.product.brand, data.product.size, data.product.color].filter(Boolean).join(' · ') }}</p>
            <code>{{ data.product.sku_internal }}</code><p v-if="data.product.barcode">{{ tr('Código de barras') }}: {{ data.product.barcode }}</p>
            <p v-if="data.product.deleted_at" class="history-warning">{{ tr('Excluído do catálogo em') }} {{ date(data.product.deleted_at) }} · {{ data.product.deleted_by || tr('Não registrado') }}. {{ tr('Saldos preservados como histórico; não fazem parte do estoque disponível.') }}</p>
            <p v-else-if="!data.product.is_active" class="history-warning">{{ tr('Produto inativo') }}</p>
            <dl class="history-meta"><div><dt>{{ tr('Criado em') }}</dt><dd>{{ date(data.product.created_at) }}</dd></div><div><dt>{{ tr('Cadastrado por') }}</dt><dd>{{ data.product.created_by || tr('Não registrado') }}</dd></div><div><dt>{{ tr('Última atualização') }}</dt><dd>{{ date(data.product.updated_at) }}</dd></div></dl>
            <dl class="history-stock"><div><dt>{{ tr('Total atual') }}</dt><dd>{{ quantity(data.product.current_stock) }}</dd></div><div><dt>{{ tr('Loja') }}</dt><dd>{{ quantity(data.product.stock_loja) }}</dd></div><div><dt>{{ tr('Depósito') }}</dt><dd>{{ quantity(data.product.stock_deposito) }}</dd></div></dl>
          </section>
          <nav class="history-tabs" :aria-label="tr('Histórico do produto')"><button v-for="tab in tabs" :key="tab.key" class="erp-control" :class="{ active: section === tab.key }" :aria-pressed="section === tab.key" @click="select(tab.key)">{{ tr(tab.label) }}<span v-if="data">{{ data.totals[tab.key] }}</span></button></nav>
          <p v-if="section === 'sales'" class="history-hint">{{ tr('Vendas concluídas e canceladas são preservadas. Uma venda pode conter várias linhas deste produto.') }}</p>
          <p v-if="data?.own_sales_only && section === 'sales'" class="history-hint">{{ tr('Você vê apenas suas próprias vendas.') }}</p>
          <p v-if="section === 'changes'" class="history-hint">{{ tr('Alterações registradas na auditoria. Dados anteriores à auditoria e valores não registrados não são reconstruídos.') }}</p>
          <p v-if="loading" role="status">{{ tr('Carregando histórico...') }}</p>
          <div v-else-if="error" class="history-warning" role="alert"><p>{{ tr('Não foi possível carregar o histórico do produto.') }}</p><button class="erp-button erp-button--secondary erp-button--sm" @click="load">{{ tr('Tentar novamente') }}</button></div>
          <template v-else-if="data">
            <p v-if="!data.rows.length" class="history-empty">{{ tr('Nenhum registro nesta seção.') }}</p>
            <ol v-else class="history-list">
              <li v-for="row in data.rows" :key="row.id">
                <div class="history-event-heading"><strong>{{ heading(row) }}</strong><time>{{ date(row.at) }}</time></div>
                <p>{{ tr('Registrado por') }}: {{ row.actor || tr('Não registrado') }}</p>
                <template v-if="row.kind === 'movements'">
                  <p>{{ tr(row.type === 'adjustment' ? 'Quantidade definida no local' : 'Quantidade') }}: <strong>{{ quantity(row.quantity) }}</strong></p>
                  <p>{{ tr('Saldo total') }}: {{ quantity(row.before) }} → <strong>{{ quantity(row.after) }}</strong></p>
                  <p>{{ tr('Local') }}: {{ location(row.location_from) }}<template v-if="row.location_to"> → {{ location(row.location_to) }}</template></p>
                  <p v-if="row.reason">{{ tr('Motivo') }}: {{ reason(row.reason) }}</p><p v-if="row.notes" class="history-notes">{{ row.notes }}</p>
                  <p v-if="row.restricted" class="history-hint">{{ tr('Movimentação operacional. Os detalhes desta venda seguem as permissões do vendedor.') }}</p>
                  <details v-else-if="row.reference_id"><summary>{{ tr('Vínculo de origem') }}</summary><p>{{ row.reference_type }}</p><code>{{ row.reference_id }}</code></details>
                </template>
                <template v-else-if="row.kind === 'sales'">
                  <p>{{ tr('Vendedor') }}: {{ row.seller || tr('Não registrado') }}</p><p>{{ tr('Cliente') }}: {{ row.customer || tr('Não registrado') }}</p>
                  <p class="history-hint">{{ tr(row.stock_applied ? 'Baixa de estoque marcada na venda' : 'Venda sem baixa ativa de estoque') }}</p>
                  <div v-for="line in row.lines" :key="line.id" class="history-sale-line">
                    <strong>{{ line.name }}</strong><p>{{ [line.size, line.color].filter(Boolean).join(' · ') }}</p>
                    <p>{{ quantity(line.quantity) }} × {{ money(line.unit_price_gs) }} · {{ location(line.location) }}</p>
                    <p>{{ tr('Total desta linha') }}: <strong>{{ money(line.total_gs) }}</strong></p>
                    <p v-if="Number(line.discount_gs)">{{ tr('Desconto desta linha') }}: {{ money(line.discount_gs) }}</p>
                    <p class="history-hint">{{ tr(line.link === 'item_id' ? 'Vínculo direto com este produto' : line.link === 'revision' ? 'Item de uma revisão anterior da venda; consulte o gestor de Vendas para os dados atuais.' : 'Referência histórica pelo SKU, sem vínculo direto') }}</p>
                    <p v-if="line.is_avulso" class="history-warning">{{ tr('Item avulso: não movimenta estoque.') }}</p>
                  </div>
                  <p>{{ tr('Total da venda inteira') }}: {{ money(row.sale_total_gs) }}</p>
                  <details><summary>{{ tr('Identificação da venda') }}</summary><code>{{ row.id }}</code><p>{{ tr('Última atualização') }}: {{ date(row.updated_at) }}</p></details>
                </template>
                <template v-else-if="row.kind === 'counts'">
                  <p>{{ row.name }} · {{ status(row.status) }}</p><p>{{ tr('Local') }}: {{ location(row.location) }}</p>
                  <p>{{ tr('Saldo na contagem') }}: {{ quantity(row.system_quantity) }} · {{ tr('Quantidade contada') }}: {{ quantity(row.counted_quantity) }}</p>
                  <p v-if="row.applied_at">{{ tr('Aplicado em') }}: {{ date(row.applied_at) }}</p>
                  <details><summary>{{ tr('Vínculo de origem') }}</summary><code>{{ row.session_id }}</code></details>
                </template>
                <template v-else-if="row.kind === 'changes'">
                  <p>{{ tr('Origem') }}: {{ row.source }}</p>
                  <ul><li v-for="(change, field) in row.fields" :key="field">{{ fieldLabel(field) }}<template v-if="!change.changed">: {{ value(change.before) }} → {{ value(change.after) }}</template><span v-else> · {{ tr('Campo alterado; valores não registrados') }}</span></li></ul>
                  <p v-if="!Object.keys(row.fields).length" class="history-hint">{{ tr('Sem detalhamento dos campos neste registro.') }}</p>
                </template>
              </li>
            </ol>
            <div v-if="data.total > data.page_size" class="history-pagination"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="page <= 1" @click="paginate(-1)">{{ tr('Anterior') }}</button><span>{{ page }} / {{ Math.ceil(data.total / data.page_size) }}</span><button class="erp-button erp-button--secondary erp-button--sm" :disabled="page * data.page_size >= data.total" @click="paginate(1)">{{ tr('Próxima') }}</button></div>
          </template>
        </main>
        <footer class="erp-dialog__footer"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="loading" @click="load">{{ tr('Atualizar') }}</button><button class="erp-button erp-button--primary erp-button--sm" @click="emit('close')">{{ tr('Fechar') }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { inventoryHistoryAPI, type HistorySection, type ProductHistory } from '@/services/inventoryHistory'
import { useInventoryI18n } from './i18n'
const props = withDefaults(defineProps<{ itemId: string; initialSection?: HistorySection }>(), { initialSection: 'movements' })
const emit = defineEmits<{ (e: 'close'): void }>()
const { tr, numberLocale } = useInventoryI18n()
const dialog = ref<HTMLElement>(), body = ref<HTMLElement>(), data = ref<ProductHistory | null>(null)
const section = ref<HistorySection>(props.initialSection), page = ref(1), loading = ref(true), error = ref(false)
let generation = 0, previousFocus: HTMLElement | null = null
const labels = { movements: 'Movimentações', sales: 'Vendas', counts: 'Contagens', changes: 'Alterações' }
const tabs = computed(() => (Object.keys(labels) as HistorySection[]).filter(key => key !== 'changes' || data.value?.can_view_changes).map(key => ({ key, label: labels[key] })))
const date = (v: string | null) => v ? new Date(v).toLocaleString(numberLocale(), { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' }) : tr('Não registrado')
const quantity = (v: string | number | null) => v === null ? tr('Não informado') : Number(v).toLocaleString(numberLocale())
const money = (v: string | null) => v === null ? tr('Não informado') : `G$ ${Number(v).toLocaleString(numberLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const location = (v: string | null) => tr(v === 'loja' ? 'Loja' : v === 'deposito' ? 'Depósito' : v || 'Não informado')
const value = (v: unknown) => v == null ? tr('Não registrado') : typeof v === 'boolean' ? tr(v ? 'Sim' : 'Não') : String(v)
const status = (v: string) => tr(({ completed: 'Concluída', partially_refunded: 'Devolução parcial', refunded: 'Estornada', cancelled: 'Cancelada', open: 'Aberta', counting: 'Em contagem', reviewing: 'Em revisão', applied: 'Aplicada' } as Record<string, string>)[v] || v)
const reason = (v: string) => tr(v === 'pdv_sale' ? 'Venda PDV' : v === 'pdv_cancel' ? 'Cancelamento de venda PDV' : v)
function heading(row: ProductHistory['rows'][number]) {
  if (row.kind === 'sales') return `${tr('Venda PDV')} · ${status(row.status)}`
  if (row.kind === 'counts') return tr('Contagem de inventário')
  if (row.kind === 'changes') return tr(({ create: 'Cadastro criado', update: 'Cadastro alterado', delete: 'Cadastro excluído', item_catalog_deleted: 'Excluído do catálogo com histórico preservado' } as Record<string, string>)[row.action] || row.action)
  return tr(({ entry: 'Entrada', exit: 'Saída', adjustment: 'Ajuste de estoque', transfer: 'Transferência' } as Record<string, string>)[row.type] || row.type)
}
const fields: Record<string, string> = { name: 'Nome', description: 'Descrição', brand: 'Marca', size: 'Tamanho', color: 'Cor', category: 'Categoria', unit: 'Unidade', location: 'Localização', barcode: 'Código de barras', sku_internal: 'SKU', supplier_id: 'Fornecedor', cost_price: 'Custo', sale_price: 'Preço de Venda', currency: 'Moeda', cost_currency: 'Moeda de custo', sale_currency: 'Moeda de venda', min_stock: 'Estoque Mínimo', max_stock: 'Estoque Máximo', current_stock: 'Total atual', stock_loja: 'Loja', stock_deposito: 'Depósito', group_key: 'Grade', is_active: 'Ativo' }
const fieldLabel = (field: string) => tr(fields[field] || field)
async function load() {
  const current = ++generation; loading.value = true; error.value = false
  try { const result = await inventoryHistoryAPI.get(props.itemId, section.value, page.value); if (current === generation) data.value = result }
  catch { if (current === generation) error.value = true }
  finally { if (current === generation) loading.value = false }
}
function select(tab: HistorySection) { section.value = tab; page.value = 1; load() }
function paginate(delta: number) { page.value += delta; load(); if (body.value) body.value.scrollTop = 0 }
function trapFocus(event: KeyboardEvent) {
  const nodes = Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), summary') || [])
  if (!nodes.length) return
  if (event.shiftKey && (document.activeElement === nodes[0] || document.activeElement === dialog.value)) { event.preventDefault(); nodes[nodes.length - 1].focus() }
  else if (!event.shiftKey && (document.activeElement === nodes[nodes.length - 1] || document.activeElement === dialog.value)) { event.preventDefault(); nodes[0].focus() }
}
onMounted(async () => { previousFocus = document.activeElement as HTMLElement; await nextTick(); dialog.value?.focus(); load() })
onUnmounted(() => { generation++; previousFocus?.focus() })
</script>

<style scoped>
.history-overlay{position:fixed;inset:0;z-index:12500;display:grid;place-items:center;padding:20px;background:#0f172a99;color:#334155}.history-dialog{background:white;width:min(820px,100%);max-height:94dvh;border-radius:16px;display:flex;flex-direction:column;box-shadow:0 20px 60px #0003;overflow:hidden}.history-dialog header,.history-dialog footer{padding:16px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-shrink:0}.history-dialog header{border-bottom:1px solid #e2e8f0}h2{font-size:18px;margin:0}h3{font-size:18px;margin:0 0 6px;color:#0f172a}main{padding:20px;overflow-y:auto;overscroll-behavior:contain;min-height:0}p{font-size:13px;line-height:1.5;margin:5px 0;overflow-wrap:anywhere}code{font-size:12px;overflow-wrap:anywhere}.history-meta,.history-stock{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}dt{font-size:12px;color:#64748b}dd{font-size:13px;margin:5px 0 0;overflow-wrap:anywhere}.history-stock>div{background:#f1f5f9;padding:12px;border-radius:10px}.history-stock dd{font-size:20px;font-weight:700}.history-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 12px}.history-tabs button{padding:8px 10px;border:1px solid #e2e8f0;background:white;border-radius:8px;font-size:13px;color:#475569;display:flex;gap:8px}.history-tabs .active{background:#eff6ff;border-color:#93c5fd;color:#1d4ed8}.history-tabs span{font-variant-numeric:tabular-nums}.history-hint{color:#64748b;font-size:12px}.history-warning{color:#92400e;background:#fffbeb;border-radius:8px;padding:10px}.history-empty{padding:24px;text-align:center;background:#f8fafc;border-radius:10px}.history-list{list-style:none;margin:16px 0;padding:0;display:grid;gap:12px}.history-list>li{border:1px solid #e2e8f0;border-radius:12px;padding:14px}.history-event-heading{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:10px;font-size:14px}.history-event-heading time{font-size:12px;color:#64748b}.history-sale-line{padding:10px;background:#f8fafc;border-radius:8px;margin:10px 0;font-size:13px}details{margin-top:10px;font-size:12px}summary{cursor:pointer;color:#2563eb;padding:5px 0}ul{padding-left:20px;font-size:13px}ul li{margin:6px 0;overflow-wrap:anywhere}.history-pagination{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:13px}.history-dialog footer{justify-content:flex-end;border-top:1px solid #e2e8f0}.history-notes{white-space:pre-wrap}
@media(max-width:600px){.history-overlay{padding:8px}.history-dialog{max-height:96dvh}.history-dialog header,.history-dialog footer,main{padding:14px}.history-meta{grid-template-columns:1fr}.history-stock{gap:6px}.history-stock>div{padding:10px 8px}.history-tabs button{font-size:12px;padding:8px}.history-list>li{padding:12px}.history-event-heading{flex-direction:column}}
</style>
