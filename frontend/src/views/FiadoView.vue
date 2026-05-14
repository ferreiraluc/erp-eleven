<template>
  <div class="fiado-root">
    <div class="fiado-header">
      <div class="fiado-title-row">
        <h1 class="fiado-title">📒 Caderno de Fiado</h1>
        <button class="fiado-btn-new" @click="openNewClient">+ Novo cliente</button>
      </div>
      <p class="fiado-subtitle">Controle de contas a receber de clientes atacadistas</p>

      <!-- Summary bar -->
      <div v-if="clients.length" class="fiado-summary">
        <div class="fiado-sum-card sum-total">
          <span class="sum-label">Total em aberto</span>
          <span class="sum-value">{{ fmtGs(totalSaldo) }}</span>
        </div>
        <div class="fiado-sum-card sum-clients">
          <span class="sum-label">Clientes ativos</span>
          <span class="sum-value">{{ clients.length }}</span>
        </div>
        <div class="fiado-sum-card sum-overdue">
          <span class="sum-label">Com saldo</span>
          <span class="sum-value">{{ clientsWithBalance }}</span>
        </div>
      </div>
    </div>

    <!-- Search -->
    <div class="fiado-search-row">
      <input v-model="search" type="text" placeholder="Buscar cliente…" class="fiado-search" />
    </div>

    <!-- Client cards -->
    <div class="fiado-list" v-if="filteredClients.length">
      <div
        v-for="client in filteredClients"
        :key="client.id"
        class="fiado-card"
        :class="{ 'card-zero': client.saldo_fiado_gs <= 0 }"
        @click="openClient(client)"
      >
        <div class="fiado-card-left">
          <div class="fiado-client-avatar">{{ client.nome[0].toUpperCase() }}</div>
          <div class="fiado-client-info">
            <div class="fiado-client-name">{{ client.nome }}</div>
            <div class="fiado-client-meta">
              <span v-if="client.doc">{{ client.doc }}</span>
              <span v-if="client.telefone">{{ client.telefone }}</span>
              <span class="fiado-tipo-badge">{{ client.tipo }}</span>
            </div>
          </div>
        </div>
        <div class="fiado-card-right">
          <div class="fiado-saldo" :class="client.saldo_fiado_gs > 0 ? 'saldo-debt' : 'saldo-zero'">
            {{ fmtGs(client.saldo_fiado_gs) }}
          </div>
          <div class="fiado-saldo-label">{{ client.saldo_fiado_gs > 0 ? 'deve' : 'em dia' }}</div>
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="fiado-empty">
      <p>{{ search ? 'Nenhum cliente encontrado' : 'Nenhum cliente cadastrado' }}</p>
      <button class="fiado-btn-new" @click="openNewClient">+ Adicionar primeiro cliente</button>
    </div>

    <!-- Client detail modal -->
    <div v-if="selectedClient" class="fiado-overlay" @click.self="selectedClient = null">
      <div class="fiado-detail-modal">
        <div class="fiado-detail-header">
          <div>
            <h2 class="fiado-detail-name">{{ selectedClient.nome }}</h2>
            <p v-if="selectedClient.doc" class="fiado-detail-meta">{{ selectedClient.doc }}</p>
            <p v-if="selectedClient.telefone" class="fiado-detail-meta">{{ selectedClient.telefone }}</p>
          </div>
          <button class="fiado-detail-close" @click="selectedClient = null">×</button>
        </div>

        <div class="fiado-detail-balance">
          <span class="fiado-balance-label">Saldo devedor</span>
          <span class="fiado-balance-value" :class="selectedClient.saldo_fiado_gs > 0 ? 'saldo-debt' : 'saldo-zero'">
            {{ fmtGs(selectedClient.saldo_fiado_gs) }}
          </span>
        </div>

        <!-- Payment input -->
        <div v-if="selectedClient.saldo_fiado_gs > 0" class="fiado-payment-form">
          <p class="fiado-payment-title">Registrar pagamento</p>
          <div class="fiado-payment-row">
            <div class="fiado-payment-input-wrap">
              <span class="fiado-payment-prefix">G$</span>
              <input
                v-model.number="paymentAmount"
                type="number" min="0" placeholder="0"
                class="fiado-payment-input"
              />
            </div>
            <input v-model="paymentNotes" type="text" placeholder="Observações (opcional)" class="fiado-payment-notes" />
            <button class="fiado-payment-btn" @click="recordPayment" :disabled="!paymentAmount || payingLoading">
              {{ payingLoading ? '…' : 'Confirmar' }}
            </button>
          </div>
          <div class="fiado-quick-amounts">
            <button
              v-for="amt in quickAmounts"
              :key="amt"
              class="fiado-quick-btn"
              @click="paymentAmount = amt"
            >{{ fmtGs(amt) }}</button>
            <button class="fiado-quick-btn fiado-quick-all" @click="paymentAmount = Math.ceil(selectedClient.saldo_fiado_gs)">
              Tudo ({{ fmtGs(selectedClient.saldo_fiado_gs) }})
            </button>
          </div>
        </div>

        <!-- Movement history -->
        <div class="fiado-movements">
          <p class="fiado-movements-title">Histórico</p>
          <div v-if="loadingHistory" class="fiado-history-loading">Carregando…</div>
          <div v-else-if="!movements.length" class="fiado-history-empty">Nenhum movimento</div>
          <div v-else class="fiado-movement-list">
            <div v-for="mv in movements" :key="mv.id" class="fiado-movement-row" :class="`mv-${mv.tipo}`">
              <div class="mv-icon">{{ mv.tipo === 'debit' ? '−' : '+' }}</div>
              <div class="mv-info">
                <span class="mv-tipo">{{ mv.tipo === 'debit' ? 'Compra' : 'Pagamento' }}</span>
                <span v-if="mv.notas" class="mv-notes">{{ mv.notas }}</span>
                <span class="mv-date">{{ formatDate(mv.created_at) }}</span>
              </div>
              <div class="mv-amounts">
                <span class="mv-valor" :class="mv.tipo === 'debit' ? 'mv-debt' : 'mv-credit'">
                  {{ mv.tipo === 'debit' ? '-' : '+' }}{{ fmtGs(mv.valor_gs) }}
                </span>
                <span class="mv-saldo">Saldo: {{ fmtGs(mv.saldo_gs) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- New client modal -->
    <div v-if="showNewClient" class="fiado-overlay" @click.self="showNewClient = false">
      <div class="fiado-new-modal">
        <div class="fiado-new-header">
          <h3>Novo cliente</h3>
          <button @click="showNewClient = false">×</button>
        </div>
        <div class="fiado-new-body">
          <div class="fiado-field">
            <label>Nome *</label>
            <input v-model="newClient.nome" type="text" class="fiado-input" placeholder="Nome do cliente" />
          </div>
          <div class="fiado-row">
            <div class="fiado-field">
              <label>Documento (CPF/RUC/CI)</label>
              <input v-model="newClient.doc" type="text" class="fiado-input" placeholder="Opcional" />
            </div>
            <div class="fiado-field">
              <label>Telefone</label>
              <input v-model="newClient.telefone" type="text" class="fiado-input" placeholder="Opcional" />
            </div>
          </div>
          <div class="fiado-row">
            <div class="fiado-field">
              <label>Tipo</label>
              <select v-model="newClient.tipo" class="fiado-input">
                <option value="atacadista">Atacadista</option>
                <option value="varejo">Varejo</option>
              </select>
            </div>
            <div class="fiado-field">
              <label>Limite de fiado (G$)</label>
              <input v-model.number="newClient.limite_fiado_gs" type="number" class="fiado-input" placeholder="0 = sem limite" />
            </div>
          </div>
          <div class="fiado-field">
            <label>Observações</label>
            <textarea v-model="newClient.notas" class="fiado-input fiado-textarea" placeholder="Opcional" rows="2"></textarea>
          </div>
          <div v-if="newClientError" class="fiado-error">{{ newClientError }}</div>
        </div>
        <div class="fiado-new-footer">
          <button class="fiado-btn-cancel" @click="showNewClient = false">Cancelar</button>
          <button class="fiado-btn-save" @click="saveNewClient" :disabled="!newClient.nome || savingClient">
            {{ savingClient ? 'Salvando…' : 'Cadastrar' }}
          </button>
        </div>
      </div>
    </div>

    <transition name="toast-fade">
      <div v-if="toast" class="fiado-toast" :class="`toast-${toast.type}`">{{ toast.msg }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { pdvAPI, type PdvClienteResponse, type PdvFiadoMovementResponse } from '@/services/api'

const clients = ref<PdvClienteResponse[]>([])
const loading = ref(false)
const search = ref('')
const selectedClient = ref<PdvClienteResponse | null>(null)
const movements = ref<PdvFiadoMovementResponse[]>([])
const loadingHistory = ref(false)
const paymentAmount = ref(0)
const paymentNotes = ref('')
const payingLoading = ref(false)
const showNewClient = ref(false)
const savingClient = ref(false)
const newClientError = ref('')

const newClient = ref({ nome: '', doc: '', telefone: '', tipo: 'atacadista', limite_fiado_gs: 0, notas: '' })

interface Toast { msg: string; type: 'success' | 'error' }
const toast = ref<Toast | null>(null)
let toastTimer: ReturnType<typeof setTimeout>

const totalSaldo = computed(() => clients.value.reduce((s, c) => s + c.saldo_fiado_gs, 0))
const clientsWithBalance = computed(() => clients.value.filter(c => c.saldo_fiado_gs > 0).length)
const filteredClients = computed(() => {
  if (!search.value) return clients.value
  const t = search.value.toLowerCase()
  return clients.value.filter(c =>
    c.nome.toLowerCase().includes(t) ||
    (c.doc || '').toLowerCase().includes(t) ||
    (c.telefone || '').includes(t)
  )
})
const quickAmounts = computed(() => {
  if (!selectedClient.value) return []
  const saldo = selectedClient.value.saldo_fiado_gs
  return [50000, 100000, 200000, 500000].filter(a => a < saldo)
})

function showToast(msg: string, type: Toast['type'] = 'success') {
  clearTimeout(toastTimer)
  toast.value = { msg, type }
  toastTimer = setTimeout(() => { toast.value = null }, 2500)
}

async function loadClients() {
  loading.value = true
  try {
    clients.value = await pdvAPI.getClients({ ativo: true })
  } finally {
    loading.value = false
  }
}

async function openClient(client: PdvClienteResponse) {
  selectedClient.value = client
  paymentAmount.value = 0
  paymentNotes.value = ''
  loadingHistory.value = true
  try {
    movements.value = await pdvAPI.getFiadoHistory(client.id)
  } finally {
    loadingHistory.value = false
  }
}

async function recordPayment() {
  if (!selectedClient.value || !paymentAmount.value) return
  payingLoading.value = true
  try {
    await pdvAPI.recordFiadoPayment(selectedClient.value.id, {
      valor_gs: paymentAmount.value,
      notas: paymentNotes.value || undefined,
    })
    showToast('Pagamento registrado!')
    await loadClients()
    // Refresh selected client
    const updated = clients.value.find(c => c.id === selectedClient.value!.id)
    if (updated) {
      selectedClient.value = updated
      movements.value = await pdvAPI.getFiadoHistory(updated.id)
    }
    paymentAmount.value = 0
    paymentNotes.value = ''
  } catch {
    showToast('Erro ao registrar pagamento', 'error')
  } finally {
    payingLoading.value = false
  }
}

function openNewClient() {
  newClient.value = { nome: '', doc: '', telefone: '', tipo: 'atacadista', limite_fiado_gs: 0, notas: '' }
  newClientError.value = ''
  showNewClient.value = true
}

async function saveNewClient() {
  if (!newClient.value.nome.trim()) return
  savingClient.value = true
  newClientError.value = ''
  try {
    await pdvAPI.createClient(newClient.value as any)
    await loadClients()
    showNewClient.value = false
    showToast('Cliente cadastrado!')
  } catch (e: any) {
    newClientError.value = e?.response?.data?.detail || 'Erro ao cadastrar'
  } finally {
    savingClient.value = false
  }
}

function fmtGs(v: number) {
  return 'G$ ' + Math.round(v).toLocaleString('es-PY')
}
function formatDate(s: string) {
  return new Date(s).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(loadClients)
</script>

<style scoped>
.fiado-root { padding: 1.25rem; max-width: 900px; margin: 0 auto; }

.fiado-header { margin-bottom: 1rem; }
.fiado-title-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 0.25rem; }
.fiado-title { margin: 0; font-size: 1.35rem; font-weight: 800; color: #111827; }
.fiado-subtitle { margin: 0 0 0.875rem; font-size: 0.8rem; color: #9ca3af; }

.fiado-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
.fiado-sum-card { background: white; border-radius: 0.75rem; padding: 0.875rem 1rem; display: flex; flex-direction: column; gap: 0.2rem; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.sum-label { font-size: 0.7rem; color: #9ca3af; font-weight: 600; text-transform: uppercase; }
.sum-value { font-size: 1.25rem; font-weight: 800; color: #111827; }
.sum-total .sum-value { color: #dc2626; }
.sum-clients .sum-value { color: #2563eb; }
.sum-overdue .sum-value { color: #d97706; }

.fiado-search-row { margin-bottom: 1rem; }
.fiado-search { width: 100%; box-sizing: border-box; border: 1.5px solid #e5e7eb; border-radius: 0.625rem; padding: 0.6rem 0.875rem; font-size: 0.9rem; outline: none; }
.fiado-search:focus { border-color: #f97316; }

.fiado-list { display: flex; flex-direction: column; gap: 0.5rem; }
.fiado-card {
  background: white; border-radius: 0.75rem; padding: 0.875rem 1rem;
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; transition: all 0.15s; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  border: 1.5px solid transparent;
}
.fiado-card:hover { border-color: #f97316; transform: translateY(-1px); }
.fiado-card.card-zero { opacity: 0.6; }
.fiado-card-left { display: flex; align-items: center; gap: 0.75rem; }
.fiado-client-avatar {
  width: 2.5rem; height: 2.5rem; border-radius: 50%;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: white; font-weight: 800; font-size: 1.1rem;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.fiado-client-name { font-weight: 700; color: #111827; font-size: 0.95rem; }
.fiado-client-meta { font-size: 0.72rem; color: #9ca3af; display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.1rem; }
.fiado-tipo-badge { background: #ede9fe; color: #5b21b6; padding: 0.1rem 0.375rem; border-radius: 0.3rem; font-size: 0.65rem; font-weight: 700; }
.fiado-saldo { font-size: 1.05rem; font-weight: 800; text-align: right; }
.fiado-saldo-label { font-size: 0.65rem; color: #9ca3af; text-align: right; }
.saldo-debt { color: #dc2626; }
.saldo-zero { color: #16a34a; }

.fiado-empty { text-align: center; padding: 3rem 1rem; color: #9ca3af; display: flex; flex-direction: column; align-items: center; gap: 1rem; }
.fiado-btn-new { padding: 0.5rem 1.25rem; background: #f97316; color: white; border: none; border-radius: 0.5rem; font-weight: 700; cursor: pointer; }

/* Detail Modal */
.fiado-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 1rem; box-sizing: border-box; }
.fiado-detail-modal { background: white; border-radius: 1rem; width: 100%; max-width: 560px; max-height: 92dvh; max-height: 92vh; overflow-y: auto; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.fiado-detail-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 1.25rem 1.25rem 0.75rem; border-bottom: 1px solid #f3f4f6; }
.fiado-detail-name { margin: 0; font-size: 1.1rem; font-weight: 800; color: #111827; }
.fiado-detail-meta { margin: 0.15rem 0 0; font-size: 0.78rem; color: #9ca3af; }
.fiado-detail-close { background: none; border: none; font-size: 1.5rem; color: #6b7280; cursor: pointer; }
.fiado-detail-balance { display: flex; justify-content: space-between; align-items: center; padding: 0.875rem 1.25rem; background: #fef2f2; }
.fiado-balance-label { font-size: 0.8rem; font-weight: 600; color: #374151; }
.fiado-balance-value { font-size: 1.5rem; font-weight: 900; }

.fiado-payment-form { padding: 0.875rem 1.25rem; border-bottom: 1px solid #f3f4f6; }
.fiado-payment-title { margin: 0 0 0.625rem; font-size: 0.8rem; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.04em; }
.fiado-payment-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; flex-wrap: wrap; }
.fiado-payment-input-wrap { display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; }
.fiado-payment-prefix { padding: 0 0.4rem; font-size: 0.75rem; color: #9ca3af; background: #f9fafb; border-right: 1px solid #e5e7eb; }
.fiado-payment-input { border: none; outline: none; padding: 0.45rem 0.5rem; font-size: 0.9rem; width: 120px; }
.fiado-payment-notes { flex: 1; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.45rem 0.6rem; font-size: 0.82rem; outline: none; }
.fiado-payment-btn { padding: 0.45rem 1rem; background: #16a34a; color: white; border: none; border-radius: 0.4rem; font-weight: 700; cursor: pointer; white-space: nowrap; }
.fiado-payment-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.fiado-quick-amounts { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.fiado-quick-btn { padding: 0.25rem 0.625rem; border: 1.5px solid #e5e7eb; border-radius: 0.3rem; background: white; font-size: 0.75rem; cursor: pointer; font-weight: 600; }
.fiado-quick-btn:hover { border-color: #16a34a; color: #16a34a; }
.fiado-quick-all { border-color: #16a34a; color: #16a34a; background: #f0fdf4; }

.fiado-movements { padding: 0.875rem 1.25rem; }
.fiado-movements-title { margin: 0 0 0.625rem; font-size: 0.8rem; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 0.04em; }
.fiado-history-loading, .fiado-history-empty { font-size: 0.82rem; color: #9ca3af; text-align: center; padding: 1rem 0; }
.fiado-movement-list { display: flex; flex-direction: column; gap: 0.35rem; }
.fiado-movement-row { display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem 0.625rem; border-radius: 0.5rem; background: #f9fafb; }
.mv-icon { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1rem; flex-shrink: 0; }
.mv-debit .mv-icon { background: #fee2e2; color: #dc2626; }
.mv-payment .mv-icon { background: #d1fae5; color: #16a34a; }
.mv-info { flex: 1; display: flex; flex-direction: column; }
.mv-tipo { font-size: 0.8rem; font-weight: 600; color: #374151; }
.mv-notes { font-size: 0.7rem; color: #9ca3af; }
.mv-date { font-size: 0.68rem; color: #d1d5db; }
.mv-amounts { display: flex; flex-direction: column; align-items: flex-end; }
.mv-valor { font-size: 0.85rem; font-weight: 700; }
.mv-debt { color: #dc2626; }
.mv-credit { color: #16a34a; }
.mv-saldo { font-size: 0.65rem; color: #9ca3af; }

/* New client modal */
.fiado-new-modal { background: white; border-radius: 1rem; width: 100%; max-width: 480px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.fiado-new-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; border-bottom: 1px solid #f3f4f6; }
.fiado-new-header h3 { margin: 0; font-size: 1rem; font-weight: 700; }
.fiado-new-header button { background: none; border: none; font-size: 1.4rem; color: #6b7280; cursor: pointer; }
.fiado-new-body { padding: 1rem 1.25rem; }
.fiado-field { display: flex; flex-direction: column; gap: 0.25rem; margin-bottom: 0.75rem; }
.fiado-field label { font-size: 0.75rem; font-weight: 600; color: #374151; }
.fiado-input { border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.45rem 0.6rem; font-size: 0.88rem; outline: none; }
.fiado-input:focus { border-color: #f97316; }
.fiado-textarea { resize: vertical; font-family: inherit; }
.fiado-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.fiado-error { color: #dc2626; font-size: 0.8rem; margin-top: 0.25rem; }
.fiado-new-footer { display: flex; gap: 0.75rem; padding: 0.875rem 1.25rem; border-top: 1px solid #f3f4f6; }
.fiado-btn-cancel { flex: 1; padding: 0.55rem; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; background: white; color: #6b7280; font-weight: 600; cursor: pointer; }
.fiado-btn-save { flex: 2; padding: 0.55rem; border: none; border-radius: 0.4rem; background: #f97316; color: white; font-weight: 700; cursor: pointer; }
.fiado-btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

.fiado-toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.6rem 1.25rem; border-radius: 2rem; font-size: 0.85rem; font-weight: 600; z-index: 9999; pointer-events: none; box-shadow: 0 4px 16px rgba(0,0,0,0.15); }
.toast-success { background: #111827; color: white; }
.toast-error   { background: #dc2626; color: white; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.25s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

@media (max-width: 640px) {
  .fiado-root { padding: 0.875rem; }
  .fiado-summary { grid-template-columns: 1fr 1fr; }
  .fiado-row { grid-template-columns: 1fr; }
}
</style>
