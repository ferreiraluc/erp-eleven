<template>
  <section class="wa-panel" :aria-label="uiText('WhatsApp da equipe')">
    <div class="wa-heading">
      <div><h2>{{ uiText('WhatsApp da equipe') }}</h2><p>{{ uiText('O mesmo assistente do ERP, com acesso individual e grupos autorizados.') }}</p></div>
      <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="loading || saving" @click="load">{{ uiText('Atualizar') }}</button>
    </div>
    <p v-if="error" class="wa-error" role="alert">{{ error }}</p>
    <p v-if="refreshError" class="wa-error" role="status">{{ refreshError }}</p>
    <p v-if="notice" class="wa-notice" role="status">{{ notice }}</p>
    <p v-if="loading && !config" role="status">{{ uiText('Carregando conexão…') }}</p>
    <template v-if="config">
      <div class="wa-status" role="status"><strong>{{ connectionLabel }}</strong><span v-if="config.account_phone">{{ config.account_phone }}</span><small v-if="config.last_seen_at">{{ uiText('Último contato:') }} {{ date(config.last_seen_at) }}</small></div>
      <form @submit.prevent="save">
        <label class="wa-check"><input v-model="draft.enabled" type="checkbox" :disabled="saving" />{{ uiText('Habilitar WhatsApp da equipe') }}</label>
        <label class="wa-check"><input v-model="draft.allow_private" type="checkbox" :disabled="saving" />{{ uiText('Permitir conversas individuais com funcionários autorizados') }}</label>
        <label>{{ uiText('Nos grupos, responder a') }}
          <ErpSelect v-model="draft.group_mode" :disabled="saving" :aria-label="uiText('Quando responder nos grupos')">
            <option value="mention">{{ uiText('Menções, respostas ao bot ou /eleven') }}</option>
            <option value="all_authorized">{{ uiText('Todas as mensagens de funcionários autorizados') }}</option>
          </ErpSelect>
        </label>
        <fieldset :disabled="saving"><legend>{{ uiText('Grupos autorizados') }}</legend>
          <p class="wa-hint">{{ uiText('Adicione o bot ao grupo. A lista se atualiza automaticamente; marque o grupo e salve para liberar. Todos os membros poderão ler as respostas publicadas nele.') }}</p>
          <p v-if="config.error_code === 'group_sync_retry'" class="wa-hint" role="status">{{ uiText('O WhatsApp não retornou a lista de grupos. O agente tentará novamente automaticamente; os grupos já conhecidos continuam disponíveis.') }}</p>
          <label v-for="group in groups" :key="group.id" class="wa-check"><input v-model="draft.allowed_groups" :value="group.id" type="checkbox" />{{ group.name }}</label>
          <p v-if="!groups.length" class="wa-hint">{{ uiText('Nenhum grupo encontrado. Nenhum grupo está autorizado por padrão.') }}</p>
          <p class="wa-hint">{{ uiText('Para testar, envie /eleven ajuda de outro número autorizado. Mensagens do próprio número do bot são ignoradas.') }}</p>
        </fieldset>
        <label class="wa-check"><input v-model="draft.notify_tracking" type="checkbox" :disabled="saving" />{{ uiText('Avisar sobre novos rastreios nos grupos autorizados') }}</label>
        <button type="submit" class="erp-button erp-button--primary" :disabled="saving || loading">{{ saving ? uiText('Salvando…') : uiText('Salvar configuração') }}</button>
      </form>
      <div class="wa-link">
        <h3>{{ uiText('Vincular o número') }}</h3>
        <p>{{ uiText('Com o agente da nuvem configurado, abra WhatsApp → Aparelhos conectados → Conectar um aparelho e leia o QR Code abaixo.') }}</p>
        <button v-if="!pairingOpen" type="button" class="erp-button erp-button--secondary" @click="openPairing">{{ uiText('Mostrar QR Code') }}</button>
        <template v-else>
          <img v-if="qrImage" class="wa-qr" :src="qrImage" :alt="uiText('QR Code para vincular o WhatsApp da equipe')" />
          <p v-else role="status">{{ uiText('Aguardando QR Code do agente. Se o número já estiver conectado, não é necessário vinculá-lo novamente.') }}</p>
          <p class="wa-hint">{{ uiText('Este código é temporário e aparece somente para o administrador. Não compartilhe a imagem.') }}</p>
          <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="closePairing">{{ uiText('Ocultar QR Code') }}</button>
        </template>
      </div>
      <details class="wa-setup" @toggle="clearClosedSecret">
        <summary>{{ uiText('Configuração do agente na nuvem') }}</summary>
        <p>{{ uiText('A credencial conecta o agente ao ERP. Salve-a no ambiente protegido do serviço; ela não substitui o vínculo do WhatsApp por QR Code.') }}</p>
        <label v-if="config.credential_configured" class="wa-check"><input v-model="rotateConfirmed" type="checkbox" />{{ uiText('Quero substituir a credencial atual; o agente precisará receber a nova.') }}</label>
        <button type="button" class="erp-button erp-button--secondary" :disabled="saving || (config.credential_configured && !rotateConfirmed)" @click="credential">{{ config.credential_configured ? uiText('Substituir credencial') : uiText('Gerar credencial') }}</button>
        <label v-if="token">{{ uiText('Credencial exibida somente agora') }}<textarea :value="token" readonly spellcheck="false" autocomplete="off" :aria-label="uiText('Credencial do agente')" /></label>
      </details>
      <details class="wa-setup">
        <summary>{{ uiText('Refazer vínculo do WhatsApp') }}</summary>
        <p>{{ uiText('Use se o WhatsApp desconectou o aparelho ou se deseja trocar o número do bot. A sessão atual do agente será substituída, preservando as filas e o histórico do ERP.') }}</p>
        <label class="wa-check"><input v-model="resetConfirmed" type="checkbox" />{{ uiText('Quero vincular o número novamente por QR Code') }}</label>
        <button type="button" class="erp-button erp-button--secondary" :disabled="saving || !resetConfirmed" @click="resetSession">{{ uiText('Preparar novo vínculo') }}</button>
      </details>
      <p class="wa-hint">{{ uiText('Conexão independente pela sessão do WhatsApp Web. Pode exigir novo vínculo ou ser interrompida pelo WhatsApp. Use preferencialmente um número dedicado à equipe. Só os funcionários vinculados abaixo recebem acesso ao ERP.') }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { uiLocale, uiText } from '@/i18n/uiText'
import { createWhatsAppBridgeCredential, getWhatsAppBridge, getWhatsAppBridgePairing, resetWhatsAppBridgeSession, saveWhatsAppBridge, type WhatsAppBridgeConfig } from '@/services/whatsappBridge'

const config = ref<WhatsAppBridgeConfig | null>(null)
const draft = ref({ name: 'WhatsApp Eleven', enabled: false, allow_private: true, notify_tracking: false, group_mode: 'mention' as 'mention' | 'all_authorized', allowed_groups: [] as string[] })
const error = ref(''), refreshError = ref(''), notice = ref(''), token = ref('')
const statusTime = ref(Date.now())
const loading = ref(false), saving = ref(false), rotateConfirmed = ref(false), pairingOpen = ref(false), qrImage = ref('')
const resetConfirmed = ref(false)
let poll: ReturnType<typeof setTimeout> | undefined, expiry: ReturnType<typeof setTimeout> | undefined
let statusPoll: ReturnType<typeof setTimeout> | undefined, statusRefreshing = false, configRequest = 0
let generation = 0, disposed = false
const groups = computed(() => {
  const known = config.value?.discovered_groups || []
  return [...known, ...draft.value.allowed_groups.filter(id => !known.some(g => g.id === id)).map(id => ({ id, name: id }))]
})
const date = (value: string) => new Date(value).toLocaleString(uiLocale())
const connectionLabel = computed(() => {
  if (!config.value?.enabled) return uiText('Pausado')
  if (!config.value.last_seen_at || statusTime.value - Date.parse(config.value.last_seen_at) > 120_000) return uiText('Agente sem contato recente')
  return ({ connected: uiText('Conectado'), open: uiText('Conectado'), connecting: uiText('Conectando…'), qr: uiText('Aguardando vínculo'), pairing: uiText('Aguardando vínculo'), logged_out: uiText('Vincule o número novamente'), disconnected: uiText('Reconectando…') }[config.value.state] || uiText('Aguardando conexão'))
})
function explain(e: unknown) {
  const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : uiText('Não foi possível atualizar a conexão do WhatsApp.')
}
function configDraft(value: WhatsAppBridgeConfig) {
  return { name: value.name, enabled: value.enabled, allow_private: value.allow_private, notify_tracking: value.notify_tracking, group_mode: value.group_mode, allowed_groups: [...value.allowed_groups] }
}
function setConfig(value: WhatsAppBridgeConfig, preserveDraft = false) {
  const dirty = config.value && JSON.stringify(draft.value) !== JSON.stringify(configDraft(config.value))
  config.value = value
  statusTime.value = Date.now()
  if (!preserveDraft || !dirty) draft.value = configDraft(value)
}
async function load() {
  const request = ++configRequest
  loading.value = true; error.value = ''; refreshError.value = ''
  try { const value = await getWhatsAppBridge(); if (!disposed && request === configRequest) setConfig(value, true) }
  catch (e) { if (!disposed && request === configRequest) refreshError.value = explain(e) }
  finally { loading.value = false }
}
async function save() {
  configRequest++; saving.value = true; error.value = ''; notice.value = ''
  try { const value = await saveWhatsAppBridge(draft.value); if (!disposed) { setConfig(value); notice.value = uiText('Configuração salva.') } }
  catch (e) { if (!disposed) error.value = explain(e) }
  finally { saving.value = false }
}
async function credential() {
  configRequest++; saving.value = true; error.value = ''; token.value = ''
  try { const value = await createWhatsAppBridgeCredential(); if (!disposed) { token.value = value.token; rotateConfirmed.value = false; if (config.value) config.value.credential_configured = true } }
  catch (e) { if (!disposed) error.value = explain(e) }
  finally { saving.value = false }
}
function clearClosedSecret(event: Event) {
  if (!(event.target as HTMLDetailsElement).open) { token.value = ''; rotateConfirmed.value = false }
}
async function resetSession() {
  if (!resetConfirmed.value) return
  configRequest++; saving.value = true; error.value = ''; notice.value = ''; closePairing()
  try {
    await resetWhatsAppBridgeSession()
    if (!disposed) { resetConfirmed.value = false; notice.value = uiText('Novo vínculo solicitado. Aguarde o agente preparar o QR Code.'); openPairing() }
  } catch (e) { if (!disposed) error.value = explain(e) }
  finally { saving.value = false }
}
function closePairing() {
  generation++; pairingOpen.value = false; qrImage.value = ''
  clearTimeout(poll); clearTimeout(expiry)
}
function openPairing() {
  configRequest++; closePairing(); pairingOpen.value = true; error.value = ''
  const current = generation, started = Date.now()
  async function refresh() {
    if (disposed || current !== generation || !pairingOpen.value) return
    if (Date.now() - started >= 180_000) { closePairing(); return }
    const request = configRequest
    try {
      const [value, currentConfig] = await Promise.all([getWhatsAppBridgePairing(), getWhatsAppBridge()])
      if (disposed || current !== generation) return
      if (request !== configRequest) { poll = setTimeout(refresh, 5000); return }
      config.value = currentConfig
      if (currentConfig.state === 'connected' && currentConfig.last_seen_at && Date.now() - Date.parse(currentConfig.last_seen_at) < 120_000) {
        closePairing(); notice.value = uiText('WhatsApp conectado. Confira os funcionários e os grupos autorizados.'); return
      }
      clearTimeout(expiry)
      const remaining = value.expires_at ? Date.parse(value.expires_at) - Date.now() : 0
      qrImage.value = remaining > 0 && value.qr_image?.startsWith('data:image/png;base64,') ? value.qr_image : ''
      if (remaining > 0) expiry = setTimeout(() => { qrImage.value = '' }, Math.min(remaining, 60_000))
    } catch (e) { if (!disposed && current === generation && request === configRequest) { qrImage.value = ''; error.value = explain(e) } }
    if (!disposed && current === generation) poll = setTimeout(refresh, 5000)
  }
  void refresh()
}
async function refreshStatus() {
  clearTimeout(statusPoll)
  if (disposed) return
  statusTime.value = Date.now()
  if (!document.hidden && !loading.value && !saving.value && !pairingOpen.value && !statusRefreshing) {
    statusRefreshing = true
    const request = configRequest
    try {
      const value = await getWhatsAppBridge()
      if (!disposed && request === configRequest) { setConfig(value, true); refreshError.value = '' }
    } catch {
      if (!disposed && request === configRequest) refreshError.value = uiText('Não foi possível atualizar os grupos agora. A lista anterior foi mantida; tentaremos novamente.')
    } finally { statusRefreshing = false }
  }
  clearTimeout(statusPoll)
  if (!disposed && !document.hidden) statusPoll = setTimeout(refreshStatus, 10000)
}
function hidden() {
  if (document.hidden) { closePairing(); token.value = ''; clearTimeout(statusPoll) }
  else void refreshStatus()
}
onMounted(() => { void load(); statusPoll = setTimeout(refreshStatus, 10000); document.addEventListener('visibilitychange', hidden) })
onBeforeUnmount(() => { disposed = true; clearTimeout(statusPoll); closePairing(); token.value = ''; document.removeEventListener('visibilitychange', hidden) })
</script>

<style scoped>
.wa-panel { margin-top: 24px; padding: 20px; background: #fff; border: 1px solid #dde3eb; border-radius: 14px; color: #172033; }
.wa-heading { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
h2 { font-size: 20px; margin: 0; } h3 { font-size: 16px; margin: 0; }
p { line-height: 1.5; color: #556277; margin: 10px 0; } .wa-hint { font-size: 13px; }
.wa-status { display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 12px; border-radius: 10px; background: #f0f7ff; margin: 16px 0; }
.wa-status small { flex-basis: 100%; color: #556277; }
form { display: grid; gap: 16px; } label { display: grid; gap: 8px; font-size: 14px; }
.wa-check { display: flex; align-items: center; gap: 10px; min-height: 36px; } input[type=checkbox] { width: 18px; height: 18px; flex: none; }
fieldset { border: 1px solid #dde3eb; padding: 12px; border-radius: 10px; min-width: 0; } legend { font-size: 14px; font-weight: 600; }
form > button { justify-self: start; } .wa-link, .wa-setup { border-top: 1px solid #e7ecf2; padding-top: 16px; margin-top: 20px; }
summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
.wa-qr { display: block; width: min(280px, 100%); height: auto; margin: 16px 0; }
textarea { width: 100%; min-height: 70px; padding: 10px; border: 1px solid #b8c3d2; border-radius: 8px; word-break: break-all; margin-top: 8px; }
.wa-error, .wa-notice { border-radius: 8px; padding: 12px; } .wa-error { background: #fff0f0; color: #982a2a; } .wa-notice { background: #e8f7ee; color: #21673a; }
@media (max-width: 480px) { .wa-panel { padding: 16px; } }
</style>
