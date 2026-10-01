<template>
  <section
    class="summary-card address-summary"
    aria-labelledby="address-summary-title"
    :aria-busy="loading"
  >
    <header class="summary-header">
      <div class="summary-heading">
        <span class="summary-icon"><MapPin :size="21" aria-hidden="true" /></span>
        <div>
          <h3 id="address-summary-title">
            <RouterLink to="/enderecos">Endereços e envios</RouterLink>
          </h3>
          <p>Agenda, impressão A4 e etiquetas</p>
        </div>
      </div>
      <RouterLink :to="{ path: '/enderecos', query: { action: 'print' } }" class="summary-primary"
        ><Plus :size="15" aria-hidden="true" />Gerar endereço</RouterLink
      >
    </header>

    <div class="summary-body">
      <div v-if="loading" class="summary-loading" role="status">
        <RefreshCw :size="20" class="spin" aria-hidden="true" />Consultando a operação…
      </div>
      <template v-else>
        <div v-if="overviewError" class="summary-error" role="alert">
          <span>Não foi possível carregar o resumo de endereços.</span
          ><button @click="load">Tentar novamente</button>
        </div>
        <template v-if="overview">
          <div class="address-metrics">
            <RouterLink to="/enderecos" class="summary-metric"
              ><span>Endereços salvos</span><strong>{{ number(overview.addresses) }}</strong
              ><small>Agenda de clientes <ArrowUpRight :size="12" aria-hidden="true" /></small
            ></RouterLink>
            <RouterLink
              :to="{ path: '/enderecos', query: { tab: 'history', status: 'pending' } }"
              class="summary-metric amber"
              ><span>Na fila</span><strong>{{ number(overview.statuses.pending || 0) }}</strong
              ><small>Aguardando impressão <ArrowUpRight :size="12" aria-hidden="true" /></small
            ></RouterLink>
            <RouterLink
              :to="{ path: '/enderecos', query: { tab: 'history', status: 'submitted' } }"
              class="summary-metric green"
              ><span>Enviados à impressora</span
              ><strong>{{ number(overview.statuses.submitted || 0) }}</strong
              ><small>Total registrado <ArrowUpRight :size="12" aria-hidden="true" /></small
            ></RouterLink>
          </div>
          <div class="printer-strip">
            <Printer :size="17" aria-hidden="true" />
            <div>
              <strong>{{ device?.name || 'Nenhuma impressora ativa' }}</strong
              ><span>{{
                device?.last_seen_at
                  ? `Último contato ${date(device.last_seen_at)}`
                  : 'Conecte o agente no computador da loja'
              }}</span>
            </div>
            <span class="summary-badge" :class="online ? 'green' : 'amber'"
              ><span class="status-dot" />{{ online ? 'Conectada' : 'Sem conexão recente' }}</span
            >
          </div>
        </template>

        <div class="summary-section-heading">
          <h4>Últimas solicitações</h4>
          <RouterLink :to="{ path: '/enderecos', query: { tab: 'history' } }"
            >Ver histórico <ArrowRight :size="13" aria-hidden="true"
          /></RouterLink>
        </div>
        <div v-if="historyError" class="summary-error" role="alert">
          <span>Histórico indisponível no momento.</span
          ><button @click="load">Tentar novamente</button>
        </div>
        <ul v-else-if="jobs.length" class="summary-list">
          <li v-for="job in jobs" :key="job.id">
            <RouterLink
              :to="{ path: '/enderecos', query: { tab: 'history', q: job.recipient } }"
              class="print-row"
              :aria-label="`Ver impressões de ${job.recipient || 'arquivo'}`"
            >
              <span class="row-icon"
                ><component
                  :is="job.source === 'superfrete' ? Truck : FileText"
                  :size="17"
                  aria-hidden="true"
              /></span>
              <span class="row-content"
                ><strong>{{ job.recipient || 'Arquivo PDF' }}</strong
                ><small
                  >{{ job.source === 'superfrete' ? 'Etiqueta' : 'Impressão' }} ·
                  {{ date(job.created_at) }}</small
                ></span
              >
              <span class="summary-badge" :class="statusClass(job.status)">{{
                states[job.status] || job.status
              }}</span>
            </RouterLink>
          </li>
        </ul>
        <div v-else class="summary-empty">
          <FileText :size="25" aria-hidden="true" /><strong>Nenhuma impressão registrada</strong
          ><span>Gere um endereço ou escolha um contato na agenda para começar.</span>
        </div>
      </template>
    </div>

    <footer class="summary-footer">
      <nav aria-label="Acessos rápidos de endereços">
        <RouterLink to="/enderecos"
          ><ContactRound :size="15" aria-hidden="true" />Agenda</RouterLink
        >
        <RouterLink :to="{ path: '/enderecos', query: { tab: 'history' } }"
          ><Printer :size="15" aria-hidden="true" />Impressões</RouterLink
        >
        <RouterLink :to="{ path: '/enderecos', query: { tab: 'freight' } }"
          ><Truck :size="15" aria-hidden="true" />SuperFrete</RouterLink
        >
      </nav>
      <button
        class="summary-refresh"
        :disabled="refreshing"
        @click="load"
        aria-label="Atualizar resumo de endereços"
        title="Atualizar resumo de endereços"
      >
        <RefreshCw :size="15" :class="{ spin: refreshing }" aria-hidden="true" />
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  ArrowRight,
  ArrowUpRight,
  ContactRound,
  FileText,
  MapPin,
  Plus,
  Printer,
  RefreshCw,
  Truck,
} from 'lucide-vue-next'
import api from '@/services/api'
import type { Job, Overview } from '@/components/addresses/types'

const overview = ref<Overview | null>(null)
const jobs = ref<Job[]>([])
const loading = ref(true),
  refreshing = ref(false),
  overviewError = ref(false),
  historyError = ref(false)
const now = ref(Date.now())
let clock: ReturnType<typeof setInterval> | undefined
const device = computed(
  () =>
    [...(overview.value?.devices || [])]
      .filter((d) => d.active)
      .sort(
        (a, b) => (Date.parse(b.last_seen_at || '') || 0) - (Date.parse(a.last_seen_at || '') || 0),
      )[0],
)
const online = computed(
  () => !!device.value?.last_seen_at && now.value - Date.parse(device.value.last_seen_at) < 90000,
)
const states: Record<string, string> = {
  pending: 'Na fila',
  claimed: 'Em processamento',
  submitted: 'Enviado à impressora',
  uncertain: 'Conferir no Windows',
  failed: 'Falha',
  expired: 'Expirado',
  cancelled: 'Cancelado',
}
const statusClass = (status: string) =>
  status === 'submitted'
    ? 'green'
    : ['failed', 'uncertain', 'expired'].includes(status)
      ? 'amber'
      : ''
const number = (value: number) => value.toLocaleString('pt-BR')
const date = (value: string) =>
  new Date(value).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

async function load() {
  if (refreshing.value) return
  refreshing.value = true
  const [summary, history] = await Promise.allSettled([
    api.get<Overview>('/api/address-manager/overview', { timeout: 15000 }),
    api.get<{ items: Job[] }>('/api/address-manager/history', {
      params: { limit: 3 },
      timeout: 15000,
    }),
  ])
  overviewError.value = summary.status === 'rejected'
  historyError.value = history.status === 'rejected'
  overview.value = summary.status === 'fulfilled' ? summary.value.data : null
  jobs.value = history.status === 'fulfilled' ? history.value.data.items : []
  now.value = Date.now()
  loading.value = false
  refreshing.value = false
}
onMounted(() => {
  load()
  clock = setInterval(() => {
    now.value = Date.now()
    if (!document.hidden) load()
  }, 30000)
})
onUnmounted(() => clearInterval(clock))
</script>

<style scoped src="./summary-card.css"></style>
<style scoped>
.address-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.printer-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #64748b;
  padding: 12px 0;
  border-bottom: 1px solid #edf1f5;
}
.printer-strip > svg {
  flex-shrink: 0;
}
.printer-strip > div {
  flex: 1;
  min-width: 0;
}
.printer-strip strong {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  overflow-wrap: anywhere;
}
.printer-strip div span {
  display: block;
  font-size: 10px;
  margin-top: 3px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.print-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 4px;
  text-decoration: none;
  border-radius: 8px;
  color: inherit;
}
.print-row:hover {
  background: #f8fafc;
}
.row-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 36px;
  background: #f1f5f9;
  color: #64748b;
  border-radius: 7px;
  flex-shrink: 0;
}
.row-content {
  flex: 1;
  min-width: 0;
}
.row-content strong {
  display: block;
  font-size: 12px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-content small {
  display: block;
  font-size: 10px;
  color: #64748b;
  margin-top: 3px;
}
@media (max-width: 480px) {
  .address-metrics {
    gap: 5px;
  }
  .address-metrics .summary-metric {
    padding: 12px 8px;
  }
  .address-metrics .summary-metric > span {
    font-size: 10px;
    min-height: 28px;
  }
  .address-metrics small {
    font-size: 9px;
  }
  .printer-strip {
    flex-wrap: wrap;
  }
  .printer-strip > .summary-badge {
    margin-left: 27px;
  }
  .print-row {
    flex-wrap: wrap;
    gap: 8px;
  }
  .print-row > .summary-badge {
    margin-left: 40px;
  }
  .row-content {
    min-width: calc(100% - 50px);
  }
}
</style>
