<template>
  <div class="clientes-view">
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <button @click="$router.back()" class="back-btn">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 class="page-title">Clientes</h1>
          </div>
        </div>
        <button @click="openCreate" class="btn btn-primary">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Novo cliente
        </button>
      </div>
    </header>

    <!-- Search -->
    <div class="search-section">
      <div class="search-box">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="search-icon">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input v-model="searchQuery" type="text" placeholder="Buscar por nome, telefone, CPF, e-mail..." class="search-input" />
      </div>
      <div class="filter-row">
        <button :class="['chip', { active: showInactive }]" @click="showInactive = !showInactive">
          {{ showInactive ? 'Todos' : 'Ativos' }}
        </button>
        <span class="total-count">{{ store.clientes.length }} cliente{{ store.clientes.length !== 1 ? 's' : '' }}</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="loading-state">
      <div class="spinner"></div>
      <p>Carregando...</p>
    </div>

    <!-- Empty -->
    <div v-else-if="!store.loading && store.clientes.length === 0" class="empty-state">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      <p>Nenhum cliente encontrado</p>
      <button @click="openCreate" class="btn btn-primary" style="margin-top:1rem">Cadastrar primeiro cliente</button>
    </div>

    <!-- List -->
    <div v-else class="clientes-list">
      <div
        v-for="c in store.clientes"
        :key="c.id"
        class="cliente-card"
        :class="{ inactive: !c.ativo }"
      >
        <div class="cliente-avatar">
          {{ c.nome.charAt(0).toUpperCase() }}
        </div>
        <div class="cliente-info">
          <div class="cliente-name-row">
            <span class="cliente-name">{{ c.nome }}</span>
            <span v-if="!c.ativo" class="badge-inactive">Inativo</span>
          </div>
          <div class="cliente-details">
            <span v-if="c.telefone" class="detail-item">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" /></svg>
              {{ c.telefone }}
            </span>
            <span v-if="c.email" class="detail-item">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
              {{ c.email }}
            </span>
            <span v-if="c.cpf" class="detail-item">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2" /></svg>
              {{ c.cpf }}
            </span>
            <span v-if="c.endereco" class="detail-item detail-endereco">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12" style="flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              {{ c.endereco.length > 60 ? c.endereco.slice(0, 60) + '…' : c.endereco }}
            </span>
          </div>
        </div>
        <div class="cliente-actions">
          <button @click="openEdit(c)" class="action-btn edit-btn" title="Editar">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
          </button>
          <button v-if="c.ativo" @click="confirmDelete(c)" class="action-btn delete-btn" title="Inativar">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Pagination sentinel -->
    <div v-if="hasMore" class="load-more-wrap">
      <button @click="loadMore" class="btn btn-secondary" :disabled="store.loading">Carregar mais</button>
    </div>

    <!-- Form Modal -->
    <ClienteFormModal
      :is-visible="showForm"
      :cliente="editingCliente"
      @close="showForm = false; editingCliente = null"
      @saved="onSaved"
    />

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast" :class="['toast', 'toast-' + toast.type]">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useClientesStore } from '@/stores/clientes'
import { type Cliente } from '@/services/api'
import ClienteFormModal from '@/components/clientes/ClienteFormModal.vue'

const store = useClientesStore()
const searchQuery = ref('')
const showInactive = ref(false)
const showForm = ref(false)
const editingCliente = ref<Cliente | null>(null)
const toast = ref<{ message: string; type: string } | null>(null)
const page = ref(0)
const hasMore = ref(false)
const PAGE_SIZE = 100

let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => reload(), 300)
})
watch(showInactive, () => reload())

function reload() {
  page.value = 0
  store.loadClientes(searchQuery.value || undefined)
}

function loadMore() {
  page.value++
  store.loadClientes(searchQuery.value || undefined)
}

function openCreate() {
  editingCliente.value = null
  showForm.value = true
}

function openEdit(c: Cliente) {
  editingCliente.value = c
  showForm.value = true
}

function onSaved(c: Cliente) {
  const idx = store.clientes.findIndex(x => x.id === c.id)
  if (idx !== -1) store.clientes[idx] = c
  else store.clientes.unshift(c)
  showToast(editingCliente.value ? 'Cliente atualizado.' : 'Cliente criado.', 'success')
}

async function confirmDelete(c: Cliente) {
  if (!confirm(`Inativar cliente "${c.nome}"?`)) return
  try {
    await store.deleteCliente(c.id)
    showToast('Cliente inativado.', 'success')
  } catch {
    showToast('Erro ao inativar cliente.', 'error')
  }
}

function showToast(message: string, type: string) {
  toast.value = { message, type }
  setTimeout(() => toast.value = null, 3000)
}

onMounted(() => reload())
</script>

<style scoped>
.clientes-view { min-height: 100vh; background: #f9fafb; }
.page-header { background: white; border-bottom: 1px solid #e5e7eb; padding: .75rem 1rem; position: sticky; top: 0; z-index: 10; }
.header-content { display: flex; align-items: center; justify-content: space-between; max-width: 1000px; margin: 0 auto; }
.header-left { display: flex; align-items: center; gap: .75rem; }
.back-btn { background: none; border: none; cursor: pointer; color: #6b7280; padding: .25rem; }
.page-title { font-size: 1.1rem; font-weight: 700; color: #111827; margin: 0; }
.btn { display: flex; align-items: center; gap: .4rem; padding: .45rem .9rem; border-radius: 8px; font-size: .875rem; cursor: pointer; border: none; font-weight: 600; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }

.search-section { padding: 1rem; max-width: 1000px; margin: 0 auto; }
.search-box { position: relative; margin-bottom: .6rem; }
.search-icon { position: absolute; left: .75rem; top: 50%; transform: translateY(-50%); color: #9ca3af; width: 1rem; height: 1rem; }
.search-input { width: 100%; padding: .6rem .75rem .6rem 2.25rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: .875rem; outline: none; box-sizing: border-box; }
.filter-row { display: flex; align-items: center; gap: .75rem; }
.chip { padding: .25rem .75rem; border-radius: 20px; font-size: .78rem; font-weight: 600; cursor: pointer; border: 1px solid #d1d5db; background: white; color: #6b7280; }
.chip.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.total-count { font-size: .78rem; color: #9ca3af; margin-left: auto; }

.loading-state, .empty-state { display: flex; flex-direction: column; align-items: center; gap: .75rem; padding: 3rem 1rem; color: #9ca3af; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.clientes-list { padding: 0 1rem 2rem; max-width: 1000px; margin: 0 auto; display: flex; flex-direction: column; gap: .5rem; }
.cliente-card { background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: .75rem 1rem; display: flex; align-items: center; gap: .85rem; transition: box-shadow .15s; }
.cliente-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.07); }
.cliente-card.inactive { opacity: .6; }
.cliente-avatar { width: 38px; height: 38px; border-radius: 50%; background: #dbeafe; color: #1d4ed8; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1rem; flex-shrink: 0; }
.cliente-info { flex: 1; min-width: 0; }
.cliente-name-row { display: flex; align-items: center; gap: .5rem; margin-bottom: .2rem; }
.cliente-name { font-weight: 600; font-size: .9rem; color: #111827; }
.badge-inactive { font-size: .68rem; background: #fee2e2; color: #dc2626; border-radius: 4px; padding: .1rem .35rem; font-weight: 600; }
.cliente-details { display: flex; flex-wrap: wrap; gap: .5rem .9rem; }
.detail-item { display: flex; align-items: center; gap: .25rem; font-size: .75rem; color: #6b7280; }
.cliente-actions { display: flex; gap: .35rem; flex-shrink: 0; }
.action-btn { padding: .3rem .4rem; border-radius: 6px; border: none; cursor: pointer; }
.edit-btn { background: #f3f4f6; color: #374151; }
.edit-btn:hover { background: #e5e7eb; }
.delete-btn { background: #fee2e2; color: #dc2626; }
.delete-btn:hover { background: #fecaca; }

.load-more-wrap { display: flex; justify-content: center; padding: 1rem; }

.toast { position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .7rem 1.2rem; border-radius: 8px; font-size: .85rem; font-weight: 600; z-index: 9999; box-shadow: 0 4px 12px rgba(0,0,0,.15); }
.toast-success { background: #10b981; color: white; }
.toast-error { background: #ef4444; color: white; }
.toast-enter-active, .toast-leave-active { transition: all .25s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 600px) {
  .page-header { padding: .4rem .75rem; }
  .page-title { font-size: 1rem; }
  .btn { padding: .35rem .65rem; font-size: .75rem; }
  .cliente-details { gap: .35rem .6rem; }
}
</style>
