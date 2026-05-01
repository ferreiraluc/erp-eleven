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
        <div class="item-row-main">
          <!-- Imagem (clicável) -->
          <div class="item-thumb-wrap" @click="item.image_data && (imageModalSrc = item.image_data)" :class="{ 'thumb-clickable': item.image_data }">
            <img v-if="item.image_data" :src="item.image_data" alt="" class="item-thumb" />
            <div v-else class="item-thumb-placeholder">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              </svg>
            </div>
          </div>

          <!-- Info -->
          <div class="item-info">
            <!-- Linha 1: Nome + Cor -->
            <div class="item-name-row">
              <span class="item-name">{{ item.name }}</span>
              <span v-if="item.color" class="item-color-tag">{{ item.color }}</span>
            </div>

            <!-- Linha 2: barcode · categoria · preço -->
            <div class="item-sub">
              <span v-if="item.barcode" class="item-barcode">{{ item.barcode }}</span>
              <template v-if="item.category">
                <span class="item-sub-sep" v-if="item.barcode"> · </span>
                <span>{{ item.category }}</span>
              </template>
              <template v-if="(item as any).sale_price">
                <span class="item-sub-sep"> · </span>
                <span class="item-price">R$ {{ Number((item as any).sale_price).toFixed(2).replace('.', ',') }}</span>
              </template>
            </div>

            <!-- Linha 3: estoque + local + badge + ações -->
            <div class="item-bottom-row">
              <div class="item-left-info">
                <span class="stock-number" :class="'stock-' + item.alert_level">
                  Est.&nbsp;{{ item.current_stock }}
                </span>
                <span v-if="item.size" class="item-size-inline">{{ item.size }}</span>
                <span v-if="item.location" class="item-location-inline">· {{ item.location }}</span>
                <span v-if="item.alert_level && item.alert_level !== 'ok'" class="alert-badge" :class="'badge-' + item.alert_level">
                  {{ alertLabel(item.alert_level) }}
                </span>
              </div>
              <div class="item-actions">
                <button @click="handleQuickExit(item)" class="action-btn exit-btn" :disabled="item.current_stock <= 0" title="Consumir 1">−1</button>
                <button @click="openMovement(item)" class="action-btn move-btn" title="Movimentar">Mov.</button>
                <button @click="openEdit(item)" class="action-btn edit-btn" title="Editar">Editar</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Image modal -->
    <div v-if="imageModalSrc" class="image-modal-overlay" @click="imageModalSrc = null">
      <img :src="imageModalSrc" alt="" class="image-modal-img" @click.stop />
      <button class="image-modal-close" @click="imageModalSrc = null">✕</button>
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
const imageModalSrc = ref<string | null>(null)

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
.header-content { display: flex; align-items: center; justify-content: space-between; max-width: 1400px; margin: 0 auto; padding: 0 1rem; }
.header-right { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
.header-top { display: flex; align-items: center; gap: 0.75rem; }
.back-button { background: none; border: none; cursor: pointer; color: #6b7280; padding: 0.25rem; }
.page-title { font-size: 1.25rem; font-weight: 700; color: #111827; margin: 0; }
.page-subtitle { font-size: 0.8rem; color: #6b7280; margin: 0.25rem 0 0 2.25rem; }
.btn { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.875rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
.search-section { padding: 1rem; max-width: 1400px; margin: 0 auto; }
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
/* ── Items list ─────────────────────────────────────────────────────────────── */
.items-list {
  padding: 0 1rem 1rem;
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.3rem;
}
@media (max-width: 500px) {
  .items-list { grid-template-columns: 1fr; }
}

.item-card {
  background: white;
  border-radius: 7px;
  padding: 0.45rem 0.6rem;
  border: 1px solid #e5e7eb;
}
.item-card.alert-out    { border-left: 3px solid #ef4444; }
.item-card.alert-low    { border-left: 3px solid #f59e0b; }
.item-card.alert-high   { border-left: 3px solid #8b5cf6; }
.item-card.alert-ok     { border-left: 3px solid #10b981; }
.item-card.alert-inactive { border-left: 3px solid #9ca3af; opacity: 0.7; }

/* Main row: thumb + info side by side */
.item-row-main { display: flex; align-items: center; gap: 0.5rem; }

/* Thumbnail */
.item-thumb-wrap {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 5px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
}
.item-thumb-wrap.thumb-clickable { cursor: zoom-in; }
.item-thumb-wrap.thumb-clickable:hover { border-color: #3b82f6; }
.item-thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
.item-thumb-placeholder { color: #d1d5db; }

/* Info column */
.item-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.15rem; }

/* Row 1: Name + Color */
.item-name-row { display: flex; align-items: baseline; gap: 0.4rem; min-width: 0; }
.item-name { font-weight: 600; font-size: 0.82rem; color: #111827; flex: 1; min-width: 0; word-break: break-word; }
.item-color-tag { font-size: 0.65rem; font-weight: 500; color: #6b7280; background: #f3f4f6; border-radius: 3px; padding: 0.1rem 0.35rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 70px; flex-shrink: 0; }

/* Row 2: barcode · category · price */
.item-sub { font-size: 0.68rem; color: #9ca3af; display: flex; align-items: center; flex-wrap: wrap; gap: 0; line-height: 1.3; }
.item-barcode { font-family: monospace; letter-spacing: 0.02em; }
.item-sub-sep { margin: 0 0.15rem; color: #d1d5db; }
.item-price { color: #059669; font-weight: 600; }

/* Row 3: stock + location + badge + actions */
.item-bottom-row { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; margin-top: 0.1rem; }
.item-left-info { display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }
.stock-number { font-size: 0.72rem; font-weight: 700; }
.stock-out      { color: #dc2626; }
.stock-low      { color: #d97706; }
.stock-high     { color: #7c3aed; }
.stock-ok       { color: #059669; }
.stock-inactive { color: #6b7280; }
.item-size-inline { font-size: 0.65rem; font-weight: 600; color: #374151; background: #f3f4f6; border-radius: 3px; padding: 0.05rem 0.3rem; }
.item-location-inline { font-size: 0.65rem; color: #9ca3af; }

/* Alert badge */
.alert-badge { font-size: 0.6rem; font-weight: 600; padding: 0.1rem 0.35rem; border-radius: 3px; white-space: nowrap; }
.badge-out      { background: #fee2e2; color: #dc2626; }
.badge-low      { background: #fef3c7; color: #d97706; }
.badge-high     { background: #ede9fe; color: #7c3aed; }
.badge-ok       { background: #d1fae5; color: #059669; }
.badge-inactive { background: #f3f4f6; color: #6b7280; }

/* Action buttons */
.item-actions { display: flex; gap: 0.3rem; flex-shrink: 0; }
.action-btn { padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; cursor: pointer; border: none; font-weight: 600; white-space: nowrap; }
.exit-btn  { background: #fee2e2; color: #dc2626; }
.exit-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.move-btn  { background: #dbeafe; color: #1d4ed8; }
.edit-btn  { background: #f3f4f6; color: #374151; }

/* ── Image modal ─────────────────────────────────────────────────────────────── */
.image-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
  cursor: zoom-out;
  padding: 1rem;
}
.image-modal-img {
  max-width: min(90vw, 600px);
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  cursor: default;
}
.image-modal-close {
  position: fixed;
  top: 1rem;
  right: 1rem;
  background: rgba(255,255,255,0.15);
  border: none;
  color: white;
  font-size: 1.25rem;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.image-modal-close:hover { background: rgba(255,255,255,0.3); }

/* ── Misc ────────────────────────────────────────────────────────────────────── */
.load-more { padding: 1rem; display: flex; justify-content: center; }
.toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.75rem 1.5rem; border-radius: 8px; font-size: 0.9rem; font-weight: 500; z-index: 9999; white-space: nowrap; }
.toast-success { background: #065f46; color: white; }
.toast-error   { background: #7f1d1d; color: white; }
.toast-warning { background: #78350f; color: white; }
</style>
