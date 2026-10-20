<template>
  <section class="mac-setup" :aria-label="uiText('3nStar no iMac')">
    <h3>{{ uiText('3nStar no iMac') }}</h3>
    <p>{{ uiText('Bobina 80 mm · Ethernet · início automático após login no macOS.') }}</p>
    <p v-if="loading" role="status">{{ uiText('Carregando…') }}</p>
    <template v-else>
      <p v-if="!mac?.auto_receipts">{{ uiText('A impressora atual continua atendendo até você conferir o teste e ativar a 3nStar.') }}</p>
      <button v-if="!mac" type="button" class="erp-button erp-button--secondary" :disabled="busy || !!error" @click="prepare">{{ uiText('Preparar 3nStar no Mac') }}</button>
      <template v-else>
        <strong>{{ uiText(mac.auto_receipts ? '3nStar ativa para as próximas vendas' : '3nStar em preparação') }}</strong>
        <p>{{ uiText('Último contato:') }} {{ mac.last_seen_at ? new Date(mac.last_seen_at).toLocaleString() : uiText('Ainda não conectado') }}</p>
        <div v-if="token" class="mac-secret">
          <strong>{{ uiText('Credencial exclusiva do Mac') }}</strong>
          <p>{{ uiText('Cole no Instalar.command do iMac. Não use a credencial da Zebra ou da Samsung.') }}</p>
          <input :value="token" readonly :aria-label="uiText('Credencial exclusiva do Mac')" @focus="($event.target as HTMLInputElement).select()" />
          <button type="button" class="erp-button erp-button--secondary" @click="copy">{{ uiText(copied ? 'Copiado' : 'Copiar credencial') }}</button>
          <label class="mac-check"><input v-model="savedToken" type="checkbox" />{{ uiText('Guardei a credencial no instalador') }}</label>
        </div>
        <a :href="packageUrl" class="erp-button erp-button--secondary" target="_blank" rel="noopener">{{ uiText('Baixar agente macOS') }} · {{ version }}</a>
        <p>{{ uiText('Extraia o ZIP e abra Instalar.command no iMac. Depois pode fechar o Terminal.') }}</p>
        <button v-if="!token" type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy" @click="rotateConfirm=!rotateConfirm">{{ uiText('Substituir credencial perdida') }}</button>
        <div v-if="rotateConfirm">
          <p>{{ uiText('A credencial antiga do Mac deixará de funcionar. Atualize o instalador do iMac.') }}</p>
          <button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="rotate">{{ uiText('Confirmar nova credencial') }}</button>
        </div>
        <p>{{ uiText('O teste imprime um comprovante de conferência, sem criar venda. Confira o papel antes de pedir outro teste.') }}</p>
        <div class="mac-actions">
          <button type="button" class="erp-button erp-button--secondary" :disabled="busy || !mac.last_seen_at || testPending" @click="test">{{ uiText('Imprimir teste na 3nStar') }}</button>
          <button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="refresh">{{ uiText('Atualizar estado') }}</button>
        </div>
        <p v-if="mac.last_test" role="status">{{ uiText('Teste:') }} {{ testLabel }} <span v-if="mac.last_test.diagnostic_message">{{ mac.last_test.diagnostic_message }}</span></p>
        <template v-if="!mac.auto_receipts">
          <label class="mac-check"><input v-model="verified" type="checkbox" :disabled="mac.last_test?.status !== 'submitted'" />{{ uiText('Conferi o papel: conteúdo completo, legível e corte correto.') }}</label>
          <button type="button" class="erp-button erp-button--primary" :disabled="busy || !verified || mac.last_test?.status !== 'submitted'" @click="activate">{{ uiText('Ativar 3nStar para as próximas vendas') }}</button>
        </template>
        <details v-else-if="windows">
          <summary>{{ uiText('Retornar à impressora Windows') }}</summary>
          <p>{{ uiText('Conclua os tickets pendentes e mantenha o agente Windows aberto antes de trocar.') }}</p>
          <button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="rollback">{{ uiText('Confirmar retorno ao Windows') }}</button>
        </details>
        <button v-if="mac.auto_receipts" type="button" class="erp-button erp-button--ghost" :disabled="busy" @click="pause">{{ uiText('Desativar impressão automática de novas vendas') }}</button>
        <small v-if="mac.auto_receipts">{{ uiText('Os trabalhos já confirmados continuam na fila.') }}</small>
      </template>
    </template>
    <p v-if="error" role="alert">{{ error }}</p>
    <button v-if="error" type="button" class="erp-button erp-button--ghost" :disabled="busy" @click="refresh">{{ uiText('Atualizar estado') }}</button>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { pdvReceipts, type ReceiptPrinter } from '@/services/pdvReceipts'
import { saleError } from '@/services/pdvManagement'
import { uiText } from '@/i18n/uiText'
const emit = defineEmits<{(e:'activated'):void}>()
const devices=ref<ReceiptPrinter[]>([]), packageUrl=ref(''), version=ref(''), token=ref(''), copied=ref(false)
const loading=ref(true), busy=ref(false), error=ref(''), savedToken=ref(false), verified=ref(false), rotateConfirm=ref(false)
const testKey=ref<string|null>(null)
const mac=computed(()=>devices.value.find(d=>d.driver==='escpos_tcp'))
const windows=computed(()=>devices.value.find(d=>d.driver!=='escpos_tcp'))
const testPending=computed(()=>['pending','claimed'].includes(mac.value?.last_test?.status ?? ''))
const testLabel=computed(()=>uiText(({pending:'Na fila',claimed:'Processando',submitted:'Enviado à impressora',uncertain:'Envio incerto',failed:'Falhou'} as Record<string,string>)[mac.value?.last_test?.status ?? ''] ?? 'Aguardando'))
async function load() {
  const result=await pdvReceipts.destinations()
  const prior=mac.value?.last_test?.id
  devices.value=result.devices; packageUrl.value=result.mac_package_url; version.value=result.mac_agent_version
  if(prior !== mac.value?.last_test?.id) verified.value=false
}
async function action(fn:()=>Promise<void>) {
  if(busy.value)return
  busy.value=true; error.value=''
  try { await fn() } catch(e) { error.value=saleError(e) } finally { busy.value=false; loading.value=false }
}
async function refresh() { await action(load) }
onMounted(refresh)
async function prepare() { await action(async()=>{
  const result=await pdvReceipts.prepareMac()
  if(result.token){token.value=result.token;savedToken.value=false}
  // Keep the credential visible even if the follow-up read fails.
  devices.value=[...devices.value.filter(d=>d.id!==result.device.id),result.device]
  await load()
}) }
async function rotate() { await action(async()=>{
  if(!mac.value)return
  token.value=(await pdvReceipts.credential(mac.value.id)).token
  savedToken.value=false;copied.value=false;rotateConfirm.value=false
}) }
async function copy() { try {await navigator.clipboard.writeText(token.value);copied.value=true} catch {error.value=uiText('Selecione e copie a credencial manualmente.')} }
async function test() { await action(async()=>{
  if(!mac.value || testPending.value)return
  testKey.value ??= crypto.randomUUID()
  const result=await pdvReceipts.testPrinter(mac.value.id,testKey.value)
  mac.value.last_test=result.job; verified.value=false; testKey.value=null
}) }
async function activate() { await action(async()=>{
  if(!mac.value || !verified.value || mac.value.last_test?.status!=='submitted')return
  await pdvReceipts.activatePrinter(mac.value.id,mac.value.last_test.id)
  await load(); emit('activated')
}) }
async function rollback() { await action(async()=>{
  if(!windows.value)return
  await pdvReceipts.activatePrinter(windows.value.id)
  await load();emit('activated')
}) }
async function pause() { await action(async()=>{
  if(!mac.value)return
  await pdvReceipts.pausePrinter(mac.value.id);await load();emit('activated')
}) }
function canClose() {
  if(busy.value)return false
  if(token.value && !savedToken.value){error.value=uiText('Guarde a credencial e marque a confirmação antes de fechar.');return false}
  return true
}
defineExpose({canClose})
</script>
<style scoped>
.mac-setup{display:grid;gap:.75rem;padding:1rem;background:#f0f7ff;border:1px solid #cbdff5;border-radius:1rem}
.mac-setup h3,.mac-setup p{margin:0}.mac-setup p,.mac-check{font-size:.875rem;line-height:1.45}
.mac-actions{display:flex;flex-wrap:wrap;gap:.5rem}.mac-check{display:flex;align-items:flex-start;gap:.5rem}
.mac-check input{flex:none;margin-top:.2rem}.mac-secret{display:grid;gap:.65rem}
.mac-secret input[readonly]{width:100%;min-width:0;box-sizing:border-box;font-size:16px;padding:.55rem;border:1px solid #cbd5e1;border-radius:.5rem}
.mac-setup a{text-align:center}.mac-setup details>*{margin-top:.65rem}.mac-setup [role=alert]{color:#b91c1c}
</style>
