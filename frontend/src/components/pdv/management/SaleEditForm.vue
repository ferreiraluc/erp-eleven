<template>
  <div class="edit-sale">
    <div class="form-grid">
      <label>{{ tr('Vendedor') }}<select v-model="model.vendedor_id"><option v-for="s in sellers" :key="s.id" :value="s.id">{{ s.name }}</option></select></label>
      <label>{{ tr('Cliente') }}<input v-model="customerSearch" :placeholder="tr('Buscar cliente cadastrado')" @input="searchClients" /></label>
    </div>
    <div v-if="clients.length" class="search-results"><button v-for="client in clients" :key="client.id" type="button" class="erp-control" @click="chooseClient(client)">{{ client.nome }}<small>{{ client.doc || client.telefone || '' }}</small></button></div>
    <p>{{ tr('Cliente selecionado') }}: <strong>{{ model.cliente_nome || tr('Não informado') }}</strong> <button type="button" class="erp-button erp-button--ghost erp-button--sm" @click="model.cliente_id = undefined; model.cliente_nome = undefined">{{ tr('Remover vínculo') }}</button></p>
    <label v-if="!model.cliente_id">{{ tr('Nome do cliente sem cadastro') }}<input v-model="model.cliente_nome" maxlength="200" /></label>
    <h3>{{ tr('Itens da venda') }}</h3>
    <article v-for="(line,index) in model.items" :key="index" class="edit-line">
      <div class="line-heading"><strong>{{ line.item_name || tr('Selecione um produto') }}</strong><button type="button" class="erp-button erp-button--danger erp-button--sm" @click="removeItem(index)">{{ tr('Remover item') }}</button></div>
      <p class="hint">{{ [line.item_sku,line.item_size,line.item_color].filter(Boolean).join(' · ') }}</p>
      <div class="line-controls"><button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="productIndex = index; productSearch = ''; products = []">{{ tr('Selecionar produto') }}</button><label class="check"><input :checked="line.is_avulso" type="checkbox" @change="makeAvulso(index,($event.target as HTMLInputElement).checked)" />{{ tr('Item avulso') }}</label></div>
      <label v-if="line.is_avulso">{{ tr('Descrição do item') }}<input v-model="line.item_name" maxlength="300" /></label>
      <div class="form-grid quantities">
        <label>{{ tr('Quantidade') }}<input v-model.number="line.quantity" type="number" :step="line.is_avulso ? '.001' : '1'" min="0.001" /></label>
        <label>{{ tr('Preço unitário G$') }}<input v-model.number="line.unit_price_gs" type="number" step=".01" min="0" /></label>
        <label>{{ tr('Desconto do item G$') }}<input v-model.number="line.discount_gs" type="number" step=".01" min="0" /></label>
        <label>{{ tr('Local') }}<select v-model="line.location"><option value="loja">{{ tr('Loja') }}</option><option value="deposito">{{ tr('Depósito') }}</option></select></label>
      </div>
      <strong class="line-total">{{ gs(Number(line.quantity) * Number(line.unit_price_gs) - Number(line.discount_gs)) }}</strong>
    </article>
    <div v-if="productIndex !== null" class="product-search" role="region" :aria-label="tr('Selecionar produto')">
      <form @submit.prevent="searchProducts"><label>{{ tr('Buscar produto por nome, SKU ou código') }}<input v-model="productSearch" maxlength="150" /></label><button class="erp-button erp-button--secondary erp-button--sm" :disabled="searching">{{ tr('Buscar') }}</button><button type="button" class="erp-button erp-button--ghost erp-button--sm" @click="productIndex = null">{{ tr('Fechar') }}</button></form>
      <p v-if="searching" role="status">{{ tr('Buscando...') }}</p>
      <div class="search-results"><button v-for="p in products" :key="p.id" type="button" class="erp-control" @click="chooseProduct(p)"><strong>{{ p.name }}</strong><small>{{ p.sku_internal }} · {{ [p.size,p.color].filter(Boolean).join(' · ') }}</small></button></div>
    </div>
    <button type="button" class="erp-button erp-button--secondary" @click="addItem">+ {{ tr('Adicionar item') }}</button>
    <label class="discount">{{ tr('Desconto da venda G$') }}<input v-model.number="model.desconto_gs" type="number" step=".01" min="0" /></label>
    <h3>{{ tr('Pagamentos aplicados à venda') }}</h3><p class="hint">{{ tr('Informe os valores aplicados, sem incluir troco. A soma deve coincidir com o total corrigido.') }}</p>
    <article v-for="(p,index) in model.payments" :key="index" class="edit-line">
      <div class="form-grid quantities">
        <label>{{ tr('Pagamento') }}<select v-model="p.method"><option v-for="method in [...new Set([...paymentMethods,p.method])]" :key="method" :value="method">{{ paymentText(method) }}</option></select></label>
        <label>{{ tr('Moeda') }}<select v-model="p.currency"><option v-for="currency in ['GS','BRL','USD','EUR']" :key="currency">{{ currency }}</option></select></label>
        <label>{{ tr('Valor na moeda') }}<input v-model.number="p.amount_original" type="number" step=".01" min="0" @input="recalculate(p)" /></label>
        <label>{{ tr('Câmbio para G$') }}<input v-model.number="p.exchange_rate" type="number" step=".000001" min=".000001" @input="recalculate(p)" /></label>
      </div>
      <div class="line-heading"><strong>{{ gs(p.amount_gs) }}</strong><button type="button" class="erp-button erp-button--danger erp-button--sm" @click="model.payments.splice(index,1)">{{ tr('Remover pagamento') }}</button></div>
      <label>{{ tr('Referência do pagamento') }}<input v-model="p.reference" maxlength="200" /></label>
    </article>
    <button type="button" class="erp-button erp-button--secondary" @click="model.payments.push({method:'cash_gs',currency:'GS',amount_original:0,exchange_rate:1,amount_gs:0})">+ {{ tr('Adicionar pagamento') }}</button>
    <div class="totals"><p>{{ tr('Total corrigido') }} <strong>{{ gs(total) }}</strong></p><p>{{ tr('Pagamentos') }} <strong>{{ gs(paid) }}</strong></p><p :class="{ mismatch: Math.abs(total - paid) > .001 }">{{ tr('Diferença') }} <strong>{{ gs(total - paid) }}</strong></p></div>
    <label>{{ tr('Observações') }}<textarea v-model="model.notas" rows="3" maxlength="4000" /></label>
    <p v-if="error" role="alert" class="mismatch">{{ tr(error) }}</p>
  </div>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { inventoryAPI, pdvAPI, type InventoryItem, type PdvClienteResponse, type PdvSaleCreate, type PdvPaymentCreate } from '@/services/api'
import { saleError } from '@/services/pdvManagement'
import { tr, gs, paymentMethods, paymentText } from './i18n'
const model = defineModel<PdvSaleCreate>({ required: true })
defineProps<{ sellers: Array<{ id: string; name: string }> }>()
const productIndex = ref<number | null>(null), productSearch = ref(''), products = ref<InventoryItem[]>([]), searching = ref(false)
const customerSearch = ref(''), clients = ref<PdvClienteResponse[]>([]), error = ref('')
let productRequest = 0, clientRequest = 0
const total = computed(() => model.value.items.reduce((sum,l) => sum + Number(l.quantity) * Number(l.unit_price_gs) - Number(l.discount_gs), 0) - Number(model.value.desconto_gs))
const paid = computed(() => model.value.payments.reduce((sum,p) => sum + Number(p.amount_gs), 0))
function addItem() { model.value.items.push({item_name:'',quantity:1,unit_price_gs:0,discount_gs:0,is_avulso:false,location:'loja'}); productIndex.value = model.value.items.length - 1 }
function removeItem(index: number) { productRequest++; productIndex.value = null; products.value = []; searching.value = false; model.value.items.splice(index,1) }
function makeAvulso(index: number, value: boolean) { const line = model.value.items[index]; line.is_avulso = value; line.item_id = undefined; line.item_sku = undefined; if (!value) { line.item_name = ''; productIndex.value = index } }
function chooseProduct(product: InventoryItem) { if (productIndex.value === null) return; const line = model.value.items[productIndex.value]; if (line) Object.assign(line,{item_id:product.id,item_name:product.name,item_sku:product.sku_internal,item_size:product.size,item_color:product.color,item_category:product.category,is_avulso:false}); productIndex.value = null; products.value = [] }
async function searchProducts() { const current = ++productRequest; searching.value = true; error.value = ''
  try { const result = await inventoryAPI.getItems({search:productSearch.value,status:'active',page_size:20}); if (current === productRequest) products.value = result.items.filter(p=>p.is_active) }
  catch(e) { if (current === productRequest) error.value = saleError(e) } finally { if (current === productRequest) searching.value = false }
}
async function searchClients() { const current = ++clientRequest; if (customerSearch.value.trim().length < 2) { clients.value=[]; return }
  try { const result = await pdvAPI.getClients({search:customerSearch.value}); if (current === clientRequest) clients.value=result }
  catch(e) { if (current === clientRequest) error.value=saleError(e) }
}
function chooseClient(c: PdvClienteResponse) { model.value.cliente_id=c.id;model.value.cliente_nome=c.nome;clients.value=[];customerSearch.value='' }
function recalculate(p: PdvPaymentCreate) { p.amount_gs=Math.round(Number(p.amount_original)*Number(p.exchange_rate)*100)/100 }
onUnmounted(()=>{productRequest++;clientRequest++})
</script>
<style scoped>
.edit-sale{display:grid;gap:14px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.quantities{grid-template-columns:repeat(4,minmax(0,1fr))}label{display:grid;gap:6px;font-size:12px;font-weight:600}input,select,textarea{min-width:0;width:100%;box-sizing:border-box;padding:9px;border:1px solid #cbd5e1;border-radius:8px;background:white;font:inherit;font-size:14px;color:#334155}.check{display:flex;align-items:center;font-weight:400}.check input{width:auto}.edit-line{display:grid;gap:12px;border:1px solid #e2e8f0;border-radius:10px;padding:14px}.line-heading,.line-controls{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.line-heading strong{overflow-wrap:anywhere}.line-total{text-align:right}.hint{font-size:12px;color:#64748b;margin:0;line-height:1.5}.search-results{display:grid;gap:6px;max-height:220px;overflow:auto}.search-results button{display:grid;gap:5px;padding:10px;text-align:left;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;color:#1e293b}.search-results small{font-size:11px}.product-search{padding:14px;border:1px solid #93c5fd;border-radius:10px}.product-search form{display:flex;align-items:end;gap:8px;margin-bottom:10px}.product-search label{flex:1}.discount{max-width:250px}.totals{background:#f8fafc;padding:12px;border-radius:8px}.totals p{display:flex;justify-content:space-between;font-size:14px;gap:10px}.mismatch{color:#b91c1c}h3{font-size:16px;margin:8px 0}
@media(max-width:650px){.quantities{grid-template-columns:repeat(2,minmax(0,1fr))}.form-grid{gap:10px}input,select,textarea{font-size:16px}.edit-line{padding:10px}.product-search form{flex-wrap:wrap}.product-search label{flex-basis:100%}}
</style>
