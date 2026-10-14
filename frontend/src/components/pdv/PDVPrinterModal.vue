<template>
  <Teleport to="body">
    <div class="erp-dialog-backdrop printer-backdrop" @click.self="close">
      <form v-erp-dialog class="erp-dialog erp-dialog--sm printer-dialog" :aria-label="uiText('Impressora de tickets')" @submit.prevent="save">
        <header class="erp-dialog__header"><h2>{{ uiText('Impressora de tickets') }}</h2><button type="button" data-dialog-close class="erp-button erp-button--ghost" @click="close">×</button></header>
        <div class="erp-dialog__body printer-fields">
          <p>{{ uiText('Tickets do PDV em uma fila própria. A impressora de endereços A4 continua separada.') }}</p>
          <p v-if="loading" role="status">{{ uiText('Carregando…') }}</p>
          <template v-else>
            <label>{{ uiText('Nome') }}<input v-model.trim="form.name" required maxlength="100" /></label>
            <div class="printer-size">
              <label>{{ uiText('Largura (mm)') }}<input v-model.number="form.paper_width_mm" type="number" min="50" max="104" required /></label>
              <label>{{ uiText('Altura (mm)') }}<input v-model.number="form.paper_height_mm" type="number" min="50" max="400" required /></label>
            </div>
            <small>{{ uiText('Use o mesmo tamanho no driver Zebra. Etiquetas 6 × 8 cm: 60 × 80 mm. Vendas longas usam várias etiquetas.') }}</small>
            <label class="printer-check"><input v-model="form.auto_receipts" type="checkbox" />{{ uiText('Imprimir ao confirmar a venda, inclusive pelo celular') }}</label>
            <p v-if="device">{{ uiText('Último contato:') }} {{ device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : uiText('Ainda não conectado') }}</p>
            <div v-if="token" class="printer-secret">
              <strong>{{ uiText('Credencial exclusiva da Zebra') }}</strong>
              <p>{{ uiText('Copie agora para o instalador Eleven Tickets. Ela só é exibida nesta criação; não use a credencial da Samsung.') }}</p>
              <input :value="token" readonly aria-label="Credencial exclusiva da Zebra" @focus="($event.target as HTMLInputElement).select()" />
              <button type="button" class="erp-button erp-button--secondary" @click="copyToken">{{ uiText(copied ? 'Copiado' : 'Copiar credencial') }}</button>
              <label class="printer-check"><input v-model="savedToken" type="checkbox" />{{ uiText('Guardei a credencial no instalador') }}</label>
            </div>
            <button v-if="device" type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="download">{{ uiText('Baixar agente Windows para tickets') }}</button>
            <button v-if="device && !token" type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy" @click="rotateConfirm=!rotateConfirm">{{ uiText('Substituir credencial perdida') }}</button>
            <div v-if="rotateConfirm">
              <p>{{ uiText('A credencial anterior deixará de funcionar. Será necessário informar a nova no instalador Windows.') }}</p>
              <button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="rotate">{{ uiText('Confirmar nova credencial') }}</button>
            </div>
            <p>{{ uiText('Instale sem substituir o Eleven Impressao. Abra Eleven Tickets e mantenha o computador ligado. O agente para macOS será preparado na migração.') }}</p>
          </template>
          <p v-if="error" role="alert">{{ error }}</p><p v-if="saved" role="status">{{ uiText('Configuração salva.') }}</p>
        </div>
        <footer class="erp-dialog__footer"><button type="button" class="erp-button erp-button--secondary" @click="close">{{ uiText('Fechar') }}</button><button class="erp-button erp-button--primary" :disabled="busy || loading">{{ uiText('Salvar') }}</button></footer>
      </form>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { vErpDialog } from '@/directives/erpDialog'
import { uiText } from '@/i18n/uiText'
import { pdvReceipts, type ReceiptPrinter } from '@/services/pdvReceipts'
import { saleError } from '@/services/pdvManagement'
const emit = defineEmits<{ (e:'close'):void }>()
const device = ref<ReceiptPrinter | null>(null), token = ref(''), loading = ref(true), busy = ref(false), error = ref(''), saved = ref(false), copied = ref(false), savedToken = ref(false)
const form = reactive({ name:'Zebra ZD220', paper_width_mm:60, paper_height_mm:80, auto_receipts:false })
const rotateConfirm=ref(false)
onMounted(async () => { try { device.value = (await pdvReceipts.printer()).device; if(device.value) Object.assign(form, device.value) } catch(e) { error.value=saleError(e) } finally { loading.value=false } })
async function save() {
  if(busy.value) return
  busy.value=true; error.value=''; saved.value=false
  try { const result=await pdvReceipts.configure({name:form.name, paper_width_mm:form.paper_width_mm, paper_height_mm:form.paper_height_mm, auto_receipts:form.auto_receipts}); device.value=result.device; if(result.token) token.value=result.token; saved.value=true }
  catch(e) { error.value=saleError(e) } finally { busy.value=false }
}
async function copyToken() { try { await navigator.clipboard.writeText(token.value); copied.value=true } catch { error.value=uiText('Selecione e copie a credencial manualmente.') } }
async function rotate() { if(busy.value)return; busy.value=true;error.value='';try{token.value=(await pdvReceipts.credential()).token;copied.value=false;savedToken.value=false;rotateConfirm.value=false}catch(e){error.value=saleError(e)}finally{busy.value=false} }
async function download() {
  busy.value=true; error.value=''
  try { const blob=await pdvReceipts.package(); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='Eleven-Tickets-Windows.zip'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),10000) }
  catch(e) { error.value=saleError(e) } finally { busy.value=false }
}
function close() { if(busy.value) return; if(token.value && !savedToken.value) { error.value=uiText('Guarde a credencial e marque a confirmação antes de fechar.'); return } emit('close') }
</script>
<style scoped>
.printer-backdrop{position:fixed;inset:0;z-index:2100;display:flex;align-items:center;justify-content:center}
.printer-dialog{background:white}.printer-fields{display:grid;gap:.85rem}.printer-fields p{margin:0;font-size:.875rem}.printer-fields label{display:grid;gap:.3rem;font-size:.875rem}.printer-fields input:not([type=checkbox]){width:100%;min-width:0;padding:.55rem;border:1px solid #cbd5e1;border-radius:.5rem;font-size:16px;box-sizing:border-box}.printer-size{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}.printer-fields .printer-check{display:flex;align-items:center;gap:.5rem}.printer-secret{display:grid;gap:.65rem;padding:.75rem;background:#eff6ff;border-radius:.75rem}
</style>
