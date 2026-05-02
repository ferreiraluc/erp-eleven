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

      <!-- Filter chips (status + marca + categoria + ver grupos) -->
      <div class="filter-chips" ref="filterChipsRef">
        <!-- Status -->
        <button
          v-for="chip in statusChips"
          :key="chip.value"
          @click="setStatusFilter(chip.value)"
          :class="['chip', { active: activeStatus === chip.value }]"
        >
          {{ chip.label }}
          <span v-if="chip.count !== undefined" class="chip-count">{{ chip.count }}</span>
        </button>

        <!-- Marca dropdown chip -->
        <div class="chip-dd-wrap" v-if="distinctBrands.length > 0">
          <button @click="toggleFilter('brand')" :class="['chip', { active: !!filterBrand }]">
            {{ filterBrand || 'Marca' }} <span class="chip-caret">▾</span>
          </button>
          <div v-if="openFilter === 'brand'" class="chip-dropdown">
            <button @click="setFilter('brand', '')" :class="['chip-dd-opt', { active: !filterBrand }]">Todas as marcas</button>
            <button v-for="b in distinctBrands" :key="b" @click="setFilter('brand', b)" :class="['chip-dd-opt', { active: filterBrand === b }]">{{ b }}</button>
          </div>
        </div>

        <!-- Categoria dropdown chip -->
        <div class="chip-dd-wrap" v-if="distinctCategories.length > 0">
          <button @click="toggleFilter('category')" :class="['chip', { active: !!filterCategory }]">
            {{ filterCategory ? formatCategory(filterCategory) : 'Categoria' }} <span class="chip-caret">▾</span>
          </button>
          <div v-if="openFilter === 'category'" class="chip-dropdown">
            <button @click="setFilter('category', '')" :class="['chip-dd-opt', { active: !filterCategory }]">Todas as categorias</button>
            <button v-for="c in distinctCategories" :key="c" @click="setFilter('category', c)" :class="['chip-dd-opt', { active: filterCategory === c }]">{{ formatCategory(c) }}</button>
          </div>
        </div>

        <!-- Ver grupos (só aparece se existem grupos) -->
        <button v-if="hasGroups" @click="toggleGroupMode" :class="['chip', { active: groupMode }]">
          {{ groupMode ? 'Ver grupos ✓' : 'Ver grupos' }}
        </button>
      </div>

      <!-- Sugestões de agrupamento (visível no modo seleção) -->
      <div v-if="selectionMode && suggestedGroups.length > 0" class="suggestions-bar">
        <span class="sug-label">Similares detectados:</span>
        <button
          v-for="sg in suggestedGroups.slice(0, 4)"
          :key="sg.name"
          @click="selectSuggestedGroup(sg)"
          class="sug-chip"
          :title="`${sg.items.length} itens com nome similar`"
        >
          {{ sg.name }} ({{ sg.items.length }})
        </button>
      </div>

      <!-- View mode switcher -->
      <div class="view-switcher">
        <span class="view-label">Visualização:</span>
        <button :class="['view-btn', { active: viewMode === 'list' }]" @click="setView('list')" title="Lista">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          Lista
        </button>
        <button :class="['view-btn', { active: viewMode === 'compact' }]" @click="setView('compact')" title="Compacto">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h7M4 12h7M4 19h7M14 5h6M14 12h6M14 19h6" />
          </svg>
          Compacto
        </button>
        <button :class="['view-btn', { active: viewMode === 'grid' }]" @click="setView('grid')" title="Grade">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          Grade
        </button>
        <span class="view-sep">|</span>
        <button :class="['view-btn', { active: selectionMode }]" @click="toggleSelectionMode" title="Selecionar para agrupar">
          Agrupar
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
    <div v-else class="items-container" :class="`view-${viewMode}`">
      <template v-for="entry in flatList" :key="entry.type === 'group' ? 'g-' + entry.group.group_key : entry.item.id">

        <!-- ── CARD DE GRUPO ── -->
        <div v-if="entry.type === 'group'" class="group-card" :class="'alert-' + groupAlertLevel(entry.group.items)">
          <div class="group-header">
            <div class="group-title-area">
              <span class="group-name">{{ entry.group.group_key }}</span>
              <span class="group-total-stock">Total: {{ entry.group.total_stock }}</span>
            </div>
            <div class="group-btns">
              <button @click="toggleExpand(entry.group.group_key)" class="action-btn expand-btn">
                {{ expandedGroups.includes(entry.group.group_key) ? '▲ Recolher' : '▼ Expandir' }}
              </button>
              <button @click="handleUngroup(entry.group.group_key)" class="action-btn ungroup-btn">Desagrupar</button>
            </div>
          </div>
          <div class="size-chips">
            <span
              v-for="v in entry.group.items"
              :key="v.id"
              class="size-chip"
              :class="'chip-alert-' + v.alert_level"
              @click="openEdit(v)"
              :title="v.name + ' · ' + v.sku_internal"
            >
              {{ v.size || v.name }} &nbsp;{{ v.current_stock }}
            </span>
          </div>
        </div>

        <!-- ── CARD INDIVIDUAL ── -->
        <div
          v-else
          class="item-card"
          :class="['alert-' + entry.item.alert_level, { 'sub-item': groupMode && entry.item.group_key, 'card-selected': selectedIds.includes(entry.item.id) }]"
          @click="selectionMode && toggleSelection(entry.item.id)"
        >
          <!-- Checkbox de seleção -->
          <div v-if="selectionMode" class="card-check" @click.stop="toggleSelection(entry.item.id)">
            <span :class="['check-box', { checked: selectedIds.includes(entry.item.id) }]">
              <svg v-if="selectedIds.includes(entry.item.id)" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="12" height="12"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
            </span>
          </div>
          <!-- Imagem topo (grid view) -->
          <div class="item-grid-image" @click.stop="entry.item.image_data && (imageModalSrc = entry.item.image_data)" :class="{ 'thumb-clickable': entry.item.image_data }">
            <img v-if="entry.item.image_data" :src="entry.item.image_data" alt="" class="item-grid-img" />
            <div v-else class="item-grid-placeholder">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="28" height="28"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
            </div>
          </div>

          <div class="item-row-main">
            <!-- Thumb -->
            <div class="item-thumb-wrap" @click="entry.item.image_data && (imageModalSrc = entry.item.image_data)" :class="{ 'thumb-clickable': entry.item.image_data }">
              <img v-if="entry.item.image_data" :src="entry.item.image_data" alt="" class="item-thumb" />
              <div v-else class="item-thumb-placeholder"><svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg></div>
            </div>

            <div class="item-info">
              <div class="item-name-row">
                <span class="item-name">{{ entry.item.name }}</span>
                <span v-if="entry.item.color" class="item-color-tag">{{ entry.item.color }}</span>
              </div>
              <div class="item-sub">
                <span v-if="entry.item.brand" class="item-brand">{{ entry.item.brand }}</span>
                <template v-if="entry.item.category">
                  <span class="item-sub-sep" v-if="entry.item.brand"> · </span>
                  <span>{{ formatCategory(entry.item.category) }}</span>
                </template>
                <template v-if="entry.item.sale_price">
                  <span class="item-sub-sep"> · </span>
                  <span class="item-price">{{ currencySymbol(entry.item.sale_currency || entry.item.currency) }} {{ Number(entry.item.sale_price).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) }}</span>
                </template>
              </div>
              <div class="item-bottom-row">
                <div class="item-left-info">
                  <span class="stock-number" :class="'stock-' + entry.item.alert_level">Estoque:&nbsp;{{ entry.item.current_stock }}</span>
                  <span v-if="entry.item.size" class="item-size-inline">{{ entry.item.size }}</span>
                  <span v-if="entry.item.location" class="item-location-inline">· {{ entry.item.location }}</span>
                  <span v-if="entry.item.alert_level && entry.item.alert_level !== 'ok'" class="alert-badge" :class="'badge-' + entry.item.alert_level">{{ alertLabel(entry.item.alert_level) }}</span>
                </div>
                <div class="item-actions">
                  <button @click="handleQuickExit(entry.item)" class="action-btn exit-btn" :disabled="entry.item.current_stock <= 0">Diminuir</button>
                  <button @click="openMovement(entry.item)" class="action-btn move-btn">Movimentar</button>
                  <button @click="openEdit(entry.item)" class="action-btn edit-btn">Editar</button>
                </div>
              </div>
            </div>
          </div>
        </div>

      </template>
    </div>

    <!-- Sentinel para infinite scroll -->
    <div ref="scrollSentinel" class="scroll-sentinel">
      <div v-if="inventoryStore.loading && inventoryStore.items.length > 0" class="loading-more">
        <div class="spinner-sm"></div>
      </div>
    </div>

    <!-- Image modal -->
    <div v-if="imageModalSrc" class="image-modal-overlay" @click="imageModalSrc = null">
      <img :src="imageModalSrc" alt="" class="image-modal-img" @click.stop />
      <button class="image-modal-close" @click="imageModalSrc = null">✕</button>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="'toast-' + toast.type">{{ toast.message }}</div>

    <!-- Modals -->
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />

    <ItemFormModal
      v-if="showItemForm"
      :item="editingItem"
      :suppliers="suppliers"
      :existing-group-keys="existingGroupKeys"
      :existing-brands="existingBrands"
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

    <!-- Barra flutuante de seleção -->
    <transition name="sel-bar">
      <div v-if="selectionMode && selectedIds.length > 0" class="selection-bar">
        <span class="sel-count">{{ selectedIds.length }} item{{ selectedIds.length !== 1 ? 's' : '' }} selecionado{{ selectedIds.length !== 1 ? 's' : '' }}</span>
        <div class="sel-actions">
          <button @click="showGroupModal = true" class="sel-btn sel-btn-primary">
            Agrupar
          </button>
          <button @click="selectedIds = []" class="sel-btn">Limpar</button>
        </div>
      </div>
    </transition>

    <!-- Modal de nome do grupo -->
    <div v-if="showGroupModal" class="gmodal-overlay" @click.self="showGroupModal = false">
      <div class="gmodal">
        <h3 class="gmodal-title">Definir nome do grupo</h3>
        <p class="gmodal-sub">{{ selectedIds.length }} itens serão agrupados. Defina um código ou nome de modelo:</p>
        <input
          v-model="groupNameInput"
          type="text"
          class="gmodal-input"
          placeholder="Ex: DKR003, FLC009 LUTT/NAPA..."
          list="gname-list"
          ref="groupNameInputRef"
          @keydown.enter="confirmGroup"
        />
        <datalist id="gname-list">
          <option v-for="gk in existingGroupKeys" :key="gk" :value="gk" />
        </datalist>
        <p class="gmodal-hint">Sugestão baseada nos nomes: <strong>{{ groupNameSuggestion }}</strong></p>
        <div class="gmodal-footer">
          <button @click="showGroupModal = false" class="sel-btn">Cancelar</button>
          <button @click="confirmGroup" class="sel-btn sel-btn-primary" :disabled="!groupNameInput.trim() || grouping">
            {{ grouping ? 'Agrupando...' : 'Agrupar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
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
const distinctBrands = ref<string[]>([])
const distinctCategories = ref<string[]>([])
const filterBrand = ref('')
const filterCategory = ref('')
const openFilter = ref<string | null>(null)
const filterChipsRef = ref<HTMLElement | null>(null)

const hasGroups = computed(() => inventoryStore.items.some(i => i.group_key))
const imageModalSrc = ref<string | null>(null)
const viewMode = ref<'list' | 'compact' | 'grid'>(
  (localStorage.getItem('inv_view') as any) || 'compact'
)
const groupMode = ref(localStorage.getItem('inv_group_mode') === 'true')
const expandedGroups = ref<string[]>([])
const selectionMode = ref(false)
const selectedIds = ref<string[]>([])
const showGroupModal = ref(false)
const groupNameInput = ref('')
const groupNameInputRef = ref<HTMLInputElement | null>(null)
const grouping = ref(false)
const scrollSentinel = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null

function setView(mode: 'list' | 'compact' | 'grid') {
  viewMode.value = mode
  localStorage.setItem('inv_view', mode)
}

function toggleGroupMode() {
  groupMode.value = !groupMode.value
  localStorage.setItem('inv_group_mode', String(groupMode.value))
}

function toggleExpand(groupKey: string) {
  const idx = expandedGroups.value.indexOf(groupKey)
  if (idx === -1) expandedGroups.value.push(groupKey)
  else expandedGroups.value.splice(idx, 1)
}

function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value
  if (!selectionMode.value) {
    selectedIds.value = []
    showGroupModal.value = false
  }
}

function toggleSelection(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

const groupNameSuggestion = computed(() => {
  if (selectedIds.value.length < 2) return ''
  const selected = inventoryStore.items.filter(i => selectedIds.value.includes(i.id))
  if (!selected.length) return ''
  const names = selected.map(i => i.name)
  let prefix = names[0]
  for (const name of names.slice(1)) {
    let i = 0
    while (i < prefix.length && i < name.length && prefix[i] === name[i]) i++
    prefix = prefix.slice(0, i)
  }
  return prefix.trim().replace(/[-_\s]+$/, '')
})

watch(showGroupModal, (val) => {
  if (val) {
    groupNameInput.value = groupNameSuggestion.value
    nextTick(() => groupNameInputRef.value?.focus())
  }
})

async function confirmGroup() {
  const name = groupNameInput.value.trim()
  if (!name || grouping.value) return
  grouping.value = true
  try {
    await inventoryAPI.groupItems(selectedIds.value, name)
    showToast(`${selectedIds.value.length} itens agrupados como "${name}"`, 'success')
    showGroupModal.value = false
    selectionMode.value = false
    selectedIds.value = []
    groupNameInput.value = ''
    groupMode.value = true
    localStorage.setItem('inv_group_mode', 'true')
    await inventoryStore.loadItems(1)
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao agrupar', 'error')
  } finally {
    grouping.value = false
  }
}

function currencySymbol(c: string): string {
  const map: Record<string, string> = { PYG: 'G$', BRL: 'R$', USD: 'U$', EUR: '€' }
  return map[c] || c
}

function formatCategory(cat: string): string {
  return cat ? cat.replace('>', ' › ') : ''
}

interface GroupEntry {
  _isGroup: true
  group_key: string
  items: InventoryItem[]
  total_stock: number
}

type FlatEntry = { type: 'group'; group: GroupEntry } | { type: 'item'; item: InventoryItem }

const flatList = computed<FlatEntry[]>(() => {
  if (!groupMode.value) {
    return inventoryStore.items.map(item => ({ type: 'item' as const, item }))
  }
  const groups = new Map<string, InventoryItem[]>()
  const ungrouped: InventoryItem[] = []
  for (const item of inventoryStore.items) {
    if (item.group_key) {
      const arr = groups.get(item.group_key) ?? []
      arr.push(item)
      groups.set(item.group_key, arr)
    } else {
      ungrouped.push(item)
    }
  }
  const result: FlatEntry[] = []
  for (const [key, items] of groups) {
    const g: GroupEntry = {
      _isGroup: true,
      group_key: key,
      items,
      total_stock: items.reduce((s, i) => s + i.current_stock, 0),
    }
    result.push({ type: 'group', group: g })
    if (expandedGroups.value.includes(key)) {
      for (const item of items) result.push({ type: 'item', item })
    }
  }
  for (const item of ungrouped) result.push({ type: 'item', item })
  return result
})

function groupAlertLevel(items: InventoryItem[]): string {
  if (items.some(i => i.alert_level === 'out')) return 'out'
  if (items.some(i => i.alert_level === 'low')) return 'low'
  if (items.some(i => i.alert_level === 'high')) return 'high'
  return 'ok'
}

const existingGroupKeys = computed<string[]>(() => {
  const s = new Set<string>()
  for (const item of inventoryStore.items) {
    if (item.group_key) s.add(item.group_key)
  }
  return Array.from(s).sort()
})

const existingBrands = computed<string[]>(() => {
  const s = new Set<string>()
  for (const item of inventoryStore.items) {
    if (item.brand) s.add(item.brand)
  }
  return Array.from(s).sort()
})

async function handleUngroup(groupKey: string) {
  try {
    await inventoryAPI.ungroup(groupKey)
    showToast(`Grupo "${groupKey}" desagrupado`, 'success')
    await inventoryStore.loadItems(1)
  } catch (e: any) {
    showToast(e.response?.data?.detail || 'Erro ao desagrupar', 'error')
  }
}

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

function toggleFilter(key: string) {
  openFilter.value = openFilter.value === key ? null : key
}

function setFilter(key: 'brand' | 'category', value: string) {
  if (key === 'brand') filterBrand.value = value
  else filterCategory.value = value
  openFilter.value = null
  inventoryStore.filters.brand = filterBrand.value
  inventoryStore.filters.category = filterCategory.value
  inventoryStore.loadItems(1)
}

function applyAdvancedFilter() {
  inventoryStore.filters.brand = filterBrand.value
  inventoryStore.filters.category = filterCategory.value
  inventoryStore.loadItems(1)
}

function clearAdvancedFilters() {
  filterBrand.value = ''
  filterCategory.value = ''
  inventoryStore.filters.brand = ''
  inventoryStore.filters.category = ''
  inventoryStore.loadItems(1)
}

// Sugestões de grupos por nome similar (prefixo comum ≥ 4 chars)
interface SuggestedGroup { name: string; items: InventoryItem[] }
const suggestedGroups = computed<SuggestedGroup[]>(() => {
  const ungrouped = inventoryStore.items.filter(i => !i.group_key)
  const map = new Map<string, InventoryItem[]>()
  for (const item of ungrouped) {
    // Normaliza: remove tamanhos comuns do final do nome
    const base = item.name.replace(/\s+(PP|P|M|G|GG|XG|XGG|XXG|\d+)\s*$/i, '').trim()
    if (base.length < 4) continue
    const arr = map.get(base) ?? []
    arr.push(item)
    map.set(base, arr)
  }
  return Array.from(map.entries())
    .filter(([, items]) => items.length >= 2)
    .map(([name, items]) => ({ name, items }))
    .sort((a, b) => b.items.length - a.items.length)
})

function selectSuggestedGroup(sg: SuggestedGroup) {
  selectedIds.value = sg.items.map(i => i.id)
  groupNameInput.value = sg.name
  showGroupModal.value = true
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

function onDocClick(e: MouseEvent) {
  if (filterChipsRef.value && !filterChipsRef.value.contains(e.target as Node)) {
    openFilter.value = null
  }
}

onUnmounted(() => {
  scrollObserver?.disconnect()
  document.removeEventListener('click', onDocClick)
})

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
  try {
    const dv = await inventoryAPI.getDistinctValues()
    distinctBrands.value = dv.brands
    distinctCategories.value = dv.categories
  } catch {}

  document.addEventListener('click', onDocClick)

  nextTick(() => {
    if (scrollSentinel.value) {
      scrollObserver = new IntersectionObserver(([entry]) => {
        if (
          entry.isIntersecting &&
          !inventoryStore.loading &&
          inventoryStore.pagination.page < inventoryStore.pagination.total_pages
        ) {
          loadMore()
        }
      }, { rootMargin: '300px' })
      scrollObserver.observe(scrollSentinel.value)
    }
  })
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
.chip { padding: 0.375rem 0.75rem; border-radius: 20px; background: #f3f4f6; border: 1px solid #e5e7eb; font-size: 0.8rem; cursor: pointer; color: #374151; display: flex; align-items: center; gap: 0.25rem; }
.chip.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.chip-count { background: #ef4444; color: white; border-radius: 10px; padding: 0 5px; font-size: 0.7rem; min-width: 16px; text-align: center; }
.loading-state { display: flex; flex-direction: column; align-items: center; padding: 3rem; color: #6b7280; gap: 1rem; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { display: flex; flex-direction: column; align-items: center; padding: 3rem 1rem; color: #6b7280; gap: 0.5rem; }
/* ── View container ──────────────────────────────────────────────────────────── */
.items-container {
  padding: 0 1rem 1rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* --- COMPACT view (default, 2 cols) --- */
.view-compact {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.3rem;
}
.view-compact .item-grid-image { display: none; }

/* --- LIST view (1 col, todas as infos em linhas separadas) --- */
.view-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.view-list .item-card { padding: 0.35rem 0.75rem; }
.view-list .item-grid-image { display: none; }
.view-list .item-thumb-wrap { display: none; }

/* --- GRID view (imagem em destaque, infos em linhas) --- */
.view-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.5rem;
}
.view-grid .item-card { padding: 0; overflow: hidden; }
.view-grid .item-grid-image {
  display: flex;
  width: 100%;
  height: 110px;
  overflow: hidden;
  background: #f3f4f6;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.view-grid .item-grid-img { width: 100%; height: 100%; object-fit: cover; }
.view-grid .item-grid-placeholder { color: #d1d5db; }
.view-grid .item-thumb-wrap { display: none; }
.view-grid .item-row-main { padding: 0.5rem 0.6rem; }
.view-grid .item-info { gap: 0.25rem; }
.view-grid .item-name { font-size: 0.78rem; white-space: normal; line-height: 1.3; }
.view-grid .item-name-row { flex-direction: column; align-items: flex-start; gap: 0.2rem; }
.view-grid .item-color-tag { max-width: none; }
.view-grid .item-sub { flex-wrap: wrap; }
.view-grid .item-bottom-row { flex-direction: column; align-items: flex-start; gap: 0.35rem; margin-top: 0.25rem; }
.view-grid .item-actions { flex-wrap: wrap; gap: 0.25rem; }
.view-grid .action-btn { font-size: 0.68rem; padding: 0.25rem 0.45rem; }

@media (max-width: 600px) {
  .view-compact { grid-template-columns: 1fr; }
  .view-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
  .item-color-tag { max-width: 60px; overflow: hidden; text-overflow: ellipsis; }
}

/* ── Item grid image (hidden by default, shown in grid view) ─── */
.item-grid-image { display: none; }
.item-grid-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.item-grid-placeholder { color: #d1d5db; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
.item-grid-image.thumb-clickable { cursor: zoom-in; }

/* ── Infinite scroll sentinel ──────────────────────────────────── */
.scroll-sentinel { height: 40px; display: flex; align-items: center; justify-content: center; }
.loading-more { display: flex; align-items: center; justify-content: center; padding: 0.5rem; }
.spinner-sm { width: 20px; height: 20px; border: 2px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; }

/* ── Filter chips ─────────────────────────────────────────────── */
.filter-chips { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem; }

/* ── Chip dropdown filters ────────────────────────────────────── */
.chip-dd-wrap { position: relative; }
.chip-caret { font-size: 0.6rem; margin-left: 0.2rem; }
.chip-dropdown {
  position: absolute; top: calc(100% + 4px); left: 0; z-index: 200;
  background: white; border: 1px solid #e5e7eb; border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1); min-width: 160px; overflow: hidden;
}
.chip-dd-opt {
  display: block; width: 100%; text-align: left;
  padding: 0.45rem 0.85rem; font-size: 0.82rem; color: #374151;
  background: none; border: none; cursor: pointer;
}
.chip-dd-opt:hover { background: #f9fafb; }
.chip-dd-opt.active { background: #dbeafe; color: #1d4ed8; font-weight: 600; }

/* ── Suggestions bar ──────────────────────────────────────────── */
.suggestions-bar { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.4rem; padding: 0.4rem 0.6rem; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 6px; }
.sug-label { font-size: 0.72rem; color: #92400e; font-weight: 600; white-space: nowrap; }
.sug-chip { font-size: 0.72rem; padding: 0.2rem 0.55rem; border-radius: 20px; border: 1px solid #fbbf24; background: #fef3c7; color: #92400e; cursor: pointer; white-space: nowrap; }
.sug-chip:hover { background: #fde68a; }

/* ── Group card ───────────────────────────────────────────────── */
.group-card {
  background: white;
  border-radius: 7px;
  border: 1px solid #e5e7eb;
  padding: 0.5rem 0.75rem;
  grid-column: 1 / -1;
}
.group-card.alert-out  { border-left: 3px solid #ef4444; }
.group-card.alert-low  { border-left: 3px solid #f59e0b; }
.group-card.alert-high { border-left: 3px solid #8b5cf6; }
.group-card.alert-ok   { border-left: 3px solid #10b981; }

.group-header { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.4rem; flex-wrap: wrap; }
.group-title-area { display: flex; align-items: center; gap: 0.6rem; min-width: 0; }
.group-name { font-weight: 700; font-size: 0.85rem; color: #111827; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.group-total-stock { font-size: 0.72rem; color: #6b7280; white-space: nowrap; }
.group-btns { display: flex; gap: 0.3rem; flex-shrink: 0; }
.size-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.size-chip { font-size: 0.68rem; font-weight: 600; padding: 0.18rem 0.55rem; border-radius: 20px; cursor: pointer; border: 1px solid transparent; white-space: nowrap; }
.chip-alert-out      { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
.chip-alert-low      { background: #fef3c7; color: #d97706; border-color: #fcd34d; }
.chip-alert-high     { background: #ede9fe; color: #7c3aed; border-color: #c4b5fd; }
.chip-alert-ok       { background: #d1fae5; color: #059669; border-color: #6ee7b7; }
.chip-alert-inactive { background: #f3f4f6; color: #9ca3af; border-color: #e5e7eb; }
.expand-btn  { background: #f0f9ff; color: #0369a1; }
.ungroup-btn { background: #fff7ed; color: #c2410c; }
.sub-item { margin-left: 0.5rem; border-left: 2px solid #e5e7eb; }

/* ── Brand ─────────────────────────────────────────────────────── */
.item-brand { font-weight: 600; color: #374151; }

/* ── View switcher ────────────────────────────────────────────── */
.view-switcher { display: flex; align-items: center; gap: 0.35rem; }
.view-label { font-size: 0.75rem; color: #9ca3af; margin-right: 0.1rem; }
.view-btn { display: flex; align-items: center; gap: 0.3rem; padding: 0.3rem 0.6rem; border: 1px solid #d1d5db; border-radius: 6px; background: white; color: #6b7280; cursor: pointer; font-size: 0.75rem; transition: all 0.15s; white-space: nowrap; }
.view-btn:hover { border-color: #9ca3af; color: #374151; }
.view-btn.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.view-sep { color: #d1d5db; padding: 0 0.1rem; }

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
.item-name-row { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; min-width: 0; }
.item-name { font-weight: 600; font-size: 0.82rem; color: #111827; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-color-tag { font-size: 0.65rem; font-weight: 500; color: #6b7280; background: #f3f4f6; border-radius: 3px; padding: 0.1rem 0.35rem; white-space: nowrap; flex-shrink: 0; }

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

/* ── Selection mode ──────────────────────────────────────────────────────────── */
.btn-warning { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.card-selected { outline: 2px solid #3b82f6; outline-offset: -2px; }
.card-check { position: absolute; top: 0.35rem; left: 0.35rem; z-index: 2; }
.item-card { position: relative; }
.check-box {
  width: 20px; height: 20px; border-radius: 4px; border: 2px solid #d1d5db;
  background: white; display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.15s;
}
.check-box.checked { background: #3b82f6; border-color: #3b82f6; color: white; }

/* ── Selection floating bar ─────────────────────────────────────────────────── */
.selection-bar {
  position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%);
  background: #1e293b; color: white; border-radius: 12px;
  padding: 0.75rem 1.25rem; display: flex; align-items: center; gap: 1rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3); z-index: 1000; white-space: nowrap;
}
.sel-count { font-size: 0.875rem; font-weight: 500; }
.sel-actions { display: flex; gap: 0.5rem; }
.sel-btn { padding: 0.4rem 1rem; border-radius: 6px; border: none; cursor: pointer; font-size: 0.8rem; font-weight: 600; background: rgba(255,255,255,0.15); color: white; }
.sel-btn:hover { background: rgba(255,255,255,0.25); }
.sel-btn-primary { background: #3b82f6; }
.sel-btn-primary:hover { background: #2563eb; }
.sel-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.sel-bar-enter-active, .sel-bar-leave-active { transition: all 0.25s ease; }
.sel-bar-enter-from, .sel-bar-leave-to { opacity: 0; transform: translateX(-50%) translateY(1rem); }

/* ── Group modal ─────────────────────────────────────────────────────────────── */
.gmodal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.gmodal { background: white; border-radius: 12px; padding: 1.5rem; width: 100%; max-width: 400px; }
.gmodal-title { font-size: 1.05rem; font-weight: 700; color: #111827; margin: 0 0 0.4rem; }
.gmodal-sub { font-size: 0.82rem; color: #6b7280; margin: 0 0 1rem; }
.gmodal-input { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: 0.95rem; outline: none; box-sizing: border-box; margin-bottom: 0.5rem; }
.gmodal-input:focus { border-color: #3b82f6; }
.gmodal-hint { font-size: 0.75rem; color: #9ca3af; margin: 0 0 1.25rem; }
.gmodal-hint strong { color: #374151; }
.gmodal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; }
.gmodal-footer .sel-btn { background: #f3f4f6; color: #374151; }
.gmodal-footer .sel-btn-primary { background: #3b82f6; color: white; }

/* ── Misc ────────────────────────────────────────────────────────────────────── */
.toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.75rem 1.5rem; border-radius: 8px; font-size: 0.9rem; font-weight: 500; z-index: 9999; white-space: nowrap; }
.toast-success { background: #065f46; color: white; }
.toast-error   { background: #7f1d1d; color: white; }
.toast-warning { background: #78350f; color: white; }
</style>
