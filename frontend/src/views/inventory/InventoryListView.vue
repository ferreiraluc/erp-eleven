<template>
  <div class="inventory-view">
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <div class="header-top">
            <button @click="$router.back()" class="back-button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <h1 class="page-title">Estoque</h1>
          </div>
          <p class="page-subtitle">Gerencie os itens do inventário</p>
        </div>
        <div class="header-right">
          <button @click="showImport = true" class="btn btn-secondary">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Importar
          </button>
          <button @click="openCreate" class="btn btn-primary">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Novo item
          </button>
        </div>
      </div>
    </header>

    <!-- Search + Camera -->
    <div class="search-section">
      <div class="search-row">
        <div class="search-box">
          <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input v-model="searchQuery" type="text" placeholder="Buscar por nome, SKU, código..." class="search-input" />
        </div>
        <button @click="showScanner = true" class="camera-btn" title="Escanear código">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>

      <!-- Filter chips -->
      <div class="filter-chips">
        <button
          v-for="chip in statusChips"
          :key="chip.value"
          @click="setStatusFilter(chip.value)"
          :class="['chip', { active: activeStatus === chip.value }]"
        >
          {{ chip.label }}
          <span v-if="chip.count !== undefined" class="chip-count">{{ chip.count }}</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="inventoryStore.loading && inventoryStore.items.length === 0" class="loading-state">
      <div class="spinner"></div>
      <p>Carregando itens...</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="!inventoryStore.loading && inventoryStore.items.length === 0" class="empty-state">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
      <p>Nenhum item encontrado</p>
      <button @click="openCreate" class="btn btn-primary" style="margin-top:1rem;">Criar primeiro item</button>
    </div>

    <!-- Items list -->
    <div v-else class="items-list">
      <div
        v-for="item in inventoryStore.items"
        :key="item.id"
        class="item-card"
        :class="'alert-' + item.alert_level"
      >
        <div class="item-card-header">
          <img v-if="item.image_data" :src="item.image_data" alt="" class="item-thumb" />
          <div class="item-card-title">
            <div class="alert-badge" :class="'badge-' + item.alert_level">
              {{ alertLabel(item.alert_level) }}
            </div>
            <span class="item-name">{{ item.name }}</span>
          </div>
        </div>

        <div class="item-meta">
          <span>{{ item.sku_internal }}</span>
          <span v-if="item.category">· {{ item.category }}</span>
          <span v-if="item.size">· {{ item.size }}</span>
        </div>

        <div v-if="item.location" class="item-location">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          </svg>
          Local: {{ item.location }}
        </div>

        <div class="item-stock-row">
          <span class="stock-number" :class="'stock-' + item.alert_level">
            Estoque: {{ item.current_stock }}
          </span>
          <span class="stock-limits">mín:{{ item.min_stock }} máx:{{ item.max_stock }}</span>
        </div>

        <div class="item-actions">
          <button @click="handleQuickExit(item)" class="action-btn exit-btn" :disabled="item.current_stock <= 0">
            Consumir 1
          </button>
          <button @click="openMovement(item)" class="action-btn move-btn">Movimentar</button>
          <button @click="openEdit(item)" class="action-btn edit-btn">Editar</button>
        </div>
      </div>
    </div>

    <!-- Load more -->
    <div v-if="inventoryStore.pagination.page < inventoryStore.pagination.total_pages" class="load-more">
      <button @click="loadMore" :disabled="inventoryStore.loading" class="btn btn-secondary">
        {{ inventoryStore.loading ? 'Carregando...' : 'Carregar mais' }}
      </button>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>

    <!-- Modals -->
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />

    <ItemFormModal
      v-if="showItemForm"
      :item="editingItem"
      :suppliers="suppliers"
      @saved="onItemSaved"
      @close="showItemForm = false"
    />

    <MovementModal
      v-if="showMovementModal"
      :item="movementItem"
      @saved="onMovementSaved"
      @close="showMovementModal = false"
    />

    <ImportModal
      v-if="showImport"
      @imported="() => { inventoryStore.loadItems(1); inventoryStore.loadAlerts() }"
      @close="showImport = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useInventoryStore } from '@/stores/inventory'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import ItemFormModal from '@/components/inventory/ItemFormModal.vue'
import MovementModal from '@/components/inventory/MovementModal.vue'
import ImportModal from '@/components/inventory/ImportModal.vue'

const route = useRoute()
const inventoryStore = useInventoryStore()

const searchQuery = ref('')
const activeStatus = ref((route.query.status as string) || '')
const showScanner = ref(false)
const showItemForm = ref(false)
const showMovementModal = ref(false)
const showImport = ref(false)
const editingItem = ref<InventoryItem | null>(null)
const movementItem = ref<InventoryItem | null>(null)
const suppliers = ref<Array<{ id: string; name: string }>>([])
const toast = ref<{ message: string; type: string } | null>(null)

const statusChips = computed(() => [
  { value: '', label: 'Todos' },
  { value: 'low_stock', label: 'Baixo', count: inventoryStore.alerts?.low_stock_count },
  { value: 'out_of_stock', label: 'Sem estoque', count: inventoryStore.alerts?.out_of_stock_count },
  { value: 'inactive', label: 'Inativos' },
])

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    inventoryStore.filters.search = val
    inventoryStore.loadItems(1)
  }, 300)
})

function setStatusFilter(status: string) {
  activeStatus.value = status
  inventoryStore.filters.status = status
  inventoryStore.loadItems(1)
}

function loadMore() {
  const nextPage = inventoryStore.pagination.page + 1
  inventoryStore.loadItems(nextPage, true)
}

function openCreate() {
  editingItem.value = null
  showItemForm.value = true
}

function openEdit(item: InventoryItem) {
  editingItem.value = item
  showItemForm.value = true
}

function openMovement(item: InventoryItem) {
  movementItem.value = item
  showMovementModal.value = true
}

async function handleQuickExit(item: InventoryItem) {
  try {
    const result = await inventoryStore.quickExit(item.id)
    showToast(`Saída registrada. Estoque: ${result.new_stock}`, 'success')
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao registrar saída', 'error')
  }
}

async function onBarcodeDetected(code: string) {
  showScanner.value = false
  try {
    const items = await inventoryAPI.getByBarcode(code)
    if (items.length === 1) {
      openEdit(items[0])
    } else if (items.length > 1) {
      inventoryStore.filters.search = code
      searchQuery.value = code
      inventoryStore.loadItems(1)
    } else {
      showToast('Nenhum item encontrado para este código', 'warning')
    }
  } catch {
    showToast('Erro ao buscar código', 'error')
  }
}

function onItemSaved(item: InventoryItem) {
  showItemForm.value = false
  showToast(`Item "${item.name}" salvo com sucesso`, 'success')
  inventoryStore.loadItems(1)
}

function onMovementSaved() {
  showMovementModal.value = false
  showToast('Movimentação registrada', 'success')
  inventoryStore.loadItems(1)
}

function alertLabel(level: string | undefined) {
  const labels: Record<string, string> = {
    out: 'Sem estoque', low: 'Baixo', high: 'Excesso', ok: 'OK', inactive: 'Inativo'
  }
  return labels[level || 'ok'] || 'OK'
}

function showToast(message: string, type: string) {
  toast.value = { message, type }
  setTimeout(() => { toast.value = null }, 3000)
}

onMounted(async () => {
  if (route.query.status) {
    inventoryStore.filters.status = route.query.status as string
    activeStatus.value = route.query.status as string
  }
  await Promise.all([
    inventoryStore.loadItems(1),
    inventoryStore.loadAlerts(),
  ])
  try {
    const supplierList = await inventoryAPI.getSuppliers()
    suppliers.value = supplierList
  } catch {}
})
</script>

<style scoped>
.inventory-view { min-height: 100vh; background: #f9fafb; }
.page-header { background: white; border-bottom: 1px solid #e5e7eb; padding: 1rem; position: sticky; top: 0; z-index: 10; }
.header-content { display: flex; align-items: flex-start; justify-content: space-between; max-width: 800px; margin: 0 auto; }
.header-top { display: flex; align-items: center; gap: 0.75rem; }
.back-button { background: none; border: none; cursor: pointer; color: #6b7280; padding: 0.25rem; }
.page-title { font-size: 1.25rem; font-weight: 700; color: #111827; margin: 0; }
.page-subtitle { font-size: 0.8rem; color: #6b7280; margin: 0.25rem 0 0 2.25rem; }
.btn { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.875rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
.search-section { padding: 1rem; max-width: 800px; margin: 0 auto; }
.search-row { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; }
.search-box { flex: 1; position: relative; }
.search-icon { position: absolute; left: 0.75rem; top: 50%; transform: translateY(-50%); width: 1rem; height: 1rem; color: #9ca3af; }
.search-input { width: 100%; padding: 0.625rem 0.75rem 0.625rem 2.25rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.875rem; outline: none; box-sizing: border-box; }
.search-input:focus { border-color: #3b82f6; }
.camera-btn { padding: 0.625rem; background: white; border: 1px solid #d1d5db; border-radius: 8px; cursor: pointer; color: #374151; }
.filter-chips { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.chip { padding: 0.375rem 0.75rem; border-radius: 20px; background: #f3f4f6; border: 1px solid #e5e7eb; font-size: 0.8rem; cursor: pointer; color: #374151; display: flex; align-items: center; gap: 0.25rem; }
.chip.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.chip-count { background: #ef4444; color: white; border-radius: 10px; padding: 0 5px; font-size: 0.7rem; min-width: 16px; text-align: center; }
.loading-state { display: flex; flex-direction: column; align-items: center; padding: 3rem; color: #6b7280; gap: 1rem; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { display: flex; flex-direction: column; align-items: center; padding: 3rem 1rem; color: #6b7280; gap: 0.5rem; }
.items-list { padding: 0 1rem 1rem; max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: 0.75rem; }
.item-card { background: white; border-radius: 10px; padding: 1rem; border: 1px solid #e5e7eb; }
.item-card.alert-out { border-left: 4px solid #ef4444; }
.item-card.alert-low { border-left: 4px solid #f59e0b; }
.item-card.alert-high { border-left: 4px solid #8b5cf6; }
.item-card.alert-ok { border-left: 4px solid #10b981; }
.item-card.alert-inactive { border-left: 4px solid #9ca3af; opacity: 0.7; }
.item-card-header { display: flex; align-items: flex-start; gap: 0.75rem; margin-bottom: 0.375rem; }
.item-thumb { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e7eb; flex-shrink: 0; }
.item-card-title { display: flex; flex-direction: column; gap: 0.25rem; }
.alert-badge { font-size: 0.65rem; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 4px; white-space: nowrap; }
.badge-out { background: #fee2e2; color: #dc2626; }
.badge-low { background: #fef3c7; color: #d97706; }
.badge-high { background: #ede9fe; color: #7c3aed; }
.badge-ok { background: #d1fae5; color: #059669; }
.badge-inactive { background: #f3f4f6; color: #6b7280; }
.item-name { font-weight: 600; font-size: 0.95rem; color: #111827; }
.item-meta { font-size: 0.78rem; color: #6b7280; margin-bottom: 0.25rem; }
.item-location { font-size: 0.78rem; color: #6b7280; display: flex; align-items: center; gap: 0.25rem; margin-bottom: 0.5rem; }
.item-stock-row { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; }
.stock-number { font-size: 0.875rem; font-weight: 600; }
.stock-out { color: #dc2626; }
.stock-low { color: #d97706; }
.stock-high { color: #7c3aed; }
.stock-ok { color: #059669; }
.stock-inactive { color: #6b7280; }
.stock-limits { font-size: 0.75rem; color: #9ca3af; }
.item-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.action-btn { padding: 0.375rem 0.75rem; border-radius: 6px; font-size: 0.8rem; cursor: pointer; border: none; font-weight: 500; }
.exit-btn { background: #fee2e2; color: #dc2626; }
.exit-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.move-btn { background: #dbeafe; color: #1d4ed8; }
.edit-btn { background: #f3f4f6; color: #374151; }
.load-more { padding: 1rem; display: flex; justify-content: center; }
.toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.75rem 1.5rem; border-radius: 8px; font-size: 0.9rem; font-weight: 500; z-index: 9999; white-space: nowrap; }
.toast-success { background: #065f46; color: white; }
.toast-error { background: #7f1d1d; color: white; }
.toast-warning { background: #78350f; color: white; }
</style>
