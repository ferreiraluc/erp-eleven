<template>
  <main class="assistant-page">
    <header>
      <div><RouterLink to="/dashboard">← Dashboard</RouterLink><h1>Assistente Eleven</h1>
        <p>WhatsApp individual e grupo Telegram, com memória operacional compartilhada.</p></div>
      <button :disabled="loading" @click="load">{{ loading ? 'Atualizando…' : 'Atualizar' }}</button>
    </header>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="notice" role="status" class="notice">{{ notice }}</p>
    <template v-if="status">
      <section class="status-grid" aria-label="Configuração dos canais">
        <article><span>Assistente</span><strong>{{ status.enabled ? 'Habilitado' : 'Pausado' }}</strong><small>Ativação pelo servidor</small></article>
        <article><span>DeepSeek</span><strong>{{ status.deepseek_configured ? 'Chave configurada' : 'Configuração pendente' }}</strong><small>{{ status.model }}</small></article>
        <article><span>WhatsApp · Twilio</span><strong>{{ !status.whatsapp_enabled ? 'Em standby' : status.twilio_configured ? 'Configurado' : 'Configuração pendente' }}</strong><small>Conversas individuais</small></article>
        <article><span>Telegram</span><strong>{{ !status.telegram_enabled ? 'Pausado' : status.telegram_configured ? 'Configurado' : 'Configuração pendente' }}</strong><small>{{ status.telegram_group_id || 'Grupo ainda não definido' }}</small></article>
      </section>
      <p class="hint">Configuração não comprova conexão. Verifique a fila após enviar uma mensagem de teste. Limite: {{ status.daily_messages_per_user }} mensagens por usuário em 24 horas.</p>

      <section class="card">
        <h2>Funcionários autorizados</h2>
        <p>Vincule o WhatsApp e o ID do Telegram ao mesmo usuário do ERP. Confirme a identidade do funcionário antes de liberar acesso.</p>
        <form @submit.prevent="saveIdentity">
          <label>Canal<select v-model="form.channel" aria-label="Canal"><option value="whatsapp">WhatsApp</option><option value="telegram">Telegram</option></select></label>
          <label>Identificador<input v-model.trim="form.external_id" required :placeholder="form.channel === 'whatsapp' ? 'whatsapp:+5511999999999' : 'ID numérico do usuário'" /></label>
          <label>Usuário ERP<select v-model="form.user_id" required aria-label="Usuário ERP"><option disabled value="">Selecione</option><option v-for="u in users" :key="u.id" :value="u.id">{{ u.nome }} · {{ u.role }}</option></select></label>
          <label class="check"><input v-model="form.active" type="checkbox" /> Acesso ativo</label>
          <label class="check"><input v-model="form.can_register" type="checkbox" /> Pode registrar ocorrências e preparar folgas (gestores)</label>
          <button :disabled="saving" type="submit">{{ saving ? 'Salvando…' : 'Salvar acesso' }}</button>
        </form>
        <div class="scroll"><table><thead><tr><th>Canal</th><th>Identificador</th><th>Funcionário</th><th>Acesso</th><th>Registros</th><th></th></tr></thead>
          <tbody><tr v-for="i in identities" :key="i.id"><td>{{ i.channel }}</td><td>{{ i.external_id }}</td><td>{{ userName(i.user_id) }}</td><td>{{ i.active ? 'Ativo' : 'Suspenso' }}</td><td>{{ i.can_register ? 'Permitido' : 'Consulta' }}</td><td><button @click="editIdentity(i)">Editar</button></td></tr>
          <tr v-if="!identities.length"><td colspan="6">Nenhum funcionário autorizado. O bot ignora remetentes desconhecidos.</td></tr></tbody></table></div>
      </section>

      <section class="card">
        <h2>Memória da equipe</h2>
        <p>O funcionário prepara um registro com <code>/registrar descrição</code> e compartilha com <code>/confirmar ID</code>. Conversas privadas não são copiadas para o grupo. Registros são relatos; não lançam vendas ou movimentam estoque.</p>
        <div class="notes"><article v-for="n in notes" :key="n.id" class="note">
          <div class="note-top"><strong>{{ n.kind }}</strong><span>{{ noteState(n.status) }}</span></div>
          <p>{{ n.content }}</p><small>{{ userName(n.user_id) }} · {{ date(n.created_at) }}</small>
          <code>{{ n.id }}</code>
        </article><p v-if="!notes.length">Nenhum registro ainda. Os últimos 100 aparecerão aqui.</p></div>
      </section>

      <section class="card">
        <h2>Cadastros de folgas pelo assistente</h2>
        <p>O bot mostra a prévia e exige confirmação do autor na mesma conversa. Apenas administradores e gerentes com permissão de registro podem cadastrar. Folgas cadastradas aguardam aprovação no calendário.</p>
        <div class="scroll"><table><thead><tr><th>Solicitado por</th><th>Vendedor</th><th>Dia</th><th>Tipo / período</th><th>Estado</th></tr></thead>
          <tbody><tr v-for="a in actions" :key="a.id"><td>{{ userName(a.user_id) }}</td><td>{{ a.vendedor }}</td><td>{{ a.data?.split('-').reverse().join('/') }}</td><td>{{ a.tipo }} / {{ a.periodo }}</td><td>{{ actionState(a.status) }}</td></tr>
          <tr v-if="!actions.length"><td colspan="5">Nenhuma solicitação de cadastro.</td></tr></tbody></table></div>
      </section>

      <section class="card">
        <h2>Processamento e envio</h2>
        <p>“Aceito pelo provedor” não significa lido ou entregue. Envio incerto exige conferência no canal para evitar duplicidade.</p>
        <div class="scroll"><table><thead><tr><th>Data</th><th>Canal</th><th>Etapa</th><th>Estado</th><th>Erro</th><th></th></tr></thead>
          <tbody><tr v-for="q in queue" :key="q.id"><td>{{ date(q.created_at) }}</td><td>{{ q.channel }}</td><td>{{ q.kind === 'message' ? 'Processar' : 'Enviar' }}</td><td>{{ queueState(q.status) }}</td><td>{{ q.error_code || '—' }}</td><td><button v-if="q.kind === 'message' && q.status === 'failed'" :disabled="saving" @click="retry(q.id)">Reprocessar</button></td></tr>
          <tr v-if="!queue.length"><td colspan="6">Nenhuma mensagem recebida ou envio agendado.</td></tr></tbody></table></div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import api from '@/services/api'

interface Identity { id: string; channel: 'whatsapp' | 'telegram'; external_id: string; user_id: string; active: boolean; can_register: boolean }
interface User { id: string; nome: string; role: string }
interface Note { id: string; kind: string; content: string; status: string; user_id: string; created_at: string }
interface Action { id: string; status: string; user_id: string; vendedor?: string; data?: string; tipo?: string; periodo?: string }
interface QueueItem { id: string; kind: string; channel: string; status: string; error_code?: string; created_at: string }
interface Status { enabled: boolean; telegram_enabled: boolean; whatsapp_enabled: boolean; model: string; deepseek_configured: boolean; twilio_configured: boolean; telegram_configured: boolean; telegram_group_id: string; daily_messages_per_user: number }
const status = ref<Status | null>(null)
const users = ref<User[]>([])
const identities = ref<Identity[]>([])
const notes = ref<Note[]>([])
const actions = ref<Action[]>([])
const queue = ref<QueueItem[]>([])
const loading = ref(false), saving = ref(false), error = ref(''), notice = ref('')
const form = ref<Omit<Identity, 'id'>>({ channel: 'whatsapp', external_id: '', user_id: '', active: true, can_register: false })
const userName = (id: string) => users.value.find(u => u.id === id)?.nome || id
const date = (value: string) => new Date(value).toLocaleString('pt-BR')
const noteState = (state: string) => ({ draft: 'Aguardando autor · expira em 24h', shared: 'Compartilhado', cancelled: 'Cancelado' }[state] || state)
const actionState = (state: string) => ({ draft: 'Aguardando confirmação · expira em 24h', executed: 'Cadastrada no ERP', cancelled: 'Cancelada' }[state] || state)
const queueState = (state: string) => ({ pending: 'Na fila', done: 'Processado', failed: 'Falha', sending: 'Enviando', accepted: 'Aceito pelo provedor', uncertain: 'Envio incerto', expired: 'Janela expirada', cancelled: 'Cancelado', rejected: 'Acesso revogado' }[state] || state)
function explainError(e: unknown) {
  const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : 'Não foi possível concluir. Verifique os campos e seu acesso de administrador.'
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const results = await Promise.all(['status', 'users', 'identities', 'notes', 'queue', 'actions'].map(path => api.get(`/api/assistant/${path}`)))
    status.value = results[0]!.data; users.value = results[1]!.data; identities.value = results[2]!.data
    notes.value = results[3]!.data; queue.value = results[4]!.data
    actions.value = results[5]!.data
  } catch (e) { error.value = explainError(e) }
  finally { loading.value = false }
}
function editIdentity(i: Identity) { form.value = { channel: i.channel, external_id: i.external_id, user_id: i.user_id, active: i.active, can_register: i.can_register }; notice.value = 'Edite os campos do acesso e clique em Salvar acesso.' }
async function saveIdentity() {
  saving.value = true; notice.value = ''; error.value = ''
  try { await api.post('/api/assistant/identities', form.value); await load(); notice.value = 'Acesso salvo.' }
  catch (e) { error.value = explainError(e) }
  finally { saving.value = false }
}
async function retry(id: string) {
  saving.value = true; error.value = ''; notice.value = ''
  try { await api.post(`/api/assistant/messages/${id}/retry`); await load(); notice.value = 'Mensagem recolocada na fila.' }
  catch (e) { error.value = explainError(e) }
  finally { saving.value = false }
}
onMounted(load)
</script>

<style scoped>
.assistant-page { max-width: 1200px; margin: auto; padding: 28px 20px 60px; color: #172033; }
header { display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 24px; }
h1 { font-size: 28px; font-weight: 750; margin: 12px 0 6px; } h2 { font-size: 20px; font-weight: 700; margin: 0 0 8px; }
p, small { color: #556277; } p { margin: 8px 0 16px; line-height: 1.6; } a { color: #2563eb; }
.status-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.status-grid article, .card { background: white; border: 1px solid #dde3eb; border-radius: 14px; padding: 20px; }
.status-grid span, .status-grid strong, .status-grid small { display: block; } .status-grid strong { margin: 8px 0; }
.status-grid span { font-size: 13px; color: #556277; } .card { margin-top: 24px; } .hint { font-size: 13px; }
form { display: flex; flex-wrap: wrap; gap: 14px; align-items: end; margin: 24px 0; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; } input, select { border: 1px solid #b8c3d2; border-radius: 7px; padding: 10px; color: #172033; background: white; }
.check { flex-direction: row; align-items: center; padding: 10px 0; } button { background: #edf3ff; color: #214faa; padding: 10px 14px; border-radius: 8px; cursor: pointer; font-weight: 600; border: 1px solid #cddafa; }
button:disabled { opacity: .55; cursor: wait; } .scroll { overflow-x: auto; } table { border-collapse: collapse; width: 100%; text-align: left; font-size: 13px; } td, th { padding: 12px 10px; border-bottom: 1px solid #e7ecf2; } th { color: #556277; }
.notes { display: grid; gap: 12px; grid-template-columns: repeat(2, 1fr); } .note { padding: 16px; border: 1px solid #e0e6ed; border-radius: 10px; min-width: 0; } .note-top { display: flex; justify-content: space-between; gap: 8px; } .note-top span { font-size: 12px; color: #556277; } .note p { white-space: pre-wrap; overflow-wrap: anywhere; } .note code { display: block; margin-top: 8px; font-size: 11px; overflow-wrap: anywhere; }
.error, .notice { border-radius: 8px; padding: 14px; } .error { background: #fff0f0; color: #982a2a; } .notice { background: #e8f7ee; color: #21673a; }
@media (max-width: 800px) { .status-grid { grid-template-columns: repeat(2, 1fr); } .notes { grid-template-columns: 1fr; } }
@media (max-width: 480px) { header { align-items: start; } h1 { font-size: 23px; } .assistant-page { padding: 20px 12px; } .status-grid { grid-template-columns: 1fr; } form label:not(.check) { width: 100%; } }
</style>
