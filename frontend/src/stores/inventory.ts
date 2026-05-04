import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { inventoryAPI, type InventoryItem, type AlertSummary, type StockMovement } from '@/services/api'

export const useInventoryStore = defineStore('inventory', () => {
  const items = ref<InventoryItem[]>([])
  const currentItem = ref<InventoryItem | null>(null)
  const alerts = ref<AlertSummary | null>(null)
  const movements = ref<StockMovement[]>([])
  const pagination = ref({ total: 0, page: 1, page_size: 50, total_pages: 1 })
  const filters = ref({ search: '', status: '', category: '', brand: '', location: '', size: '', color: '' })
  const loading = ref(false)
  const error = ref<string | null>(null)

  const lowStockItems = computed(() => items.value.filter(i => i.alert_level === 'low'))
  const outOfStockItems = computed(() => items.value.filter(i => i.alert_level === 'out'))

  async function loadItems(page = 1, append = false) {
    try {
      loading.value = true
      error.value = null
      const params: Record<string, any> = {
        page,
        page_size: pagination.value.page_size,
        ...filters.value,
      }
      Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
      const result = await inventoryAPI.getItems(params)
      if (append) {
        items.value = [...items.value, ...result.items]
      } else {
        items.value = result.items
      }
      pagination.value = { total: result.total, page: result.page, page_size: result.page_size, total_pages: result.total_pages }
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Error loading items'
    } finally {
      loading.value = false
    }
  }

  async function createItem(data: Partial<InventoryItem>) {
    const item = await inventoryAPI.createItem(data)
    items.value.unshift(item)
    return item
  }

  async function updateItem(id: string, data: Partial<InventoryItem>) {
    const updated = await inventoryAPI.updateItem(id, data)
    const idx = items.value.findIndex(i => i.id === id)
    if (idx !== -1) items.value[idx] = updated
    if (currentItem.value?.id === id) currentItem.value = updated
    return updated
  }

  async function deleteItem(id: string) {
    await inventoryAPI.deleteItem(id)
    const idx = items.value.findIndex(i => i.id === id)
    if (idx !== -1) items.value[idx].is_active = false
  }

  async function quickExit(id: string) {
    const result = await inventoryAPI.quickExit(id)
    const idx = items.value.findIndex(i => i.id === id)
    if (idx !== -1) {
      items.value[idx].current_stock = result.new_stock
      // Recompute alert level
      const item = items.value[idx]
      if (item.current_stock <= 0) item.alert_level = 'out'
      else if (item.current_stock < item.min_stock) item.alert_level = 'low'
      else item.alert_level = 'ok'
    }
    return result
  }

  async function loadAlerts() {
    try {
      alerts.value = await inventoryAPI.getAlertsSummary()
    } catch (e) {
      // silently fail for dashboard widget
    }
  }

  async function createMovement(data: any) {
    const mv = await inventoryAPI.createMovement(data)
    // Reload item to get updated stock
    const idx = items.value.findIndex(i => i.id === data.item_id)
    if (idx !== -1) {
      const updated = await inventoryAPI.getItem(data.item_id)
      items.value[idx] = updated
    }
    return mv
  }

  async function createBatchMovement(data: any) {
    return await inventoryAPI.createBatchMovement(data)
  }

  return {
    items, currentItem, alerts, movements, pagination, filters, loading, error,
    lowStockItems, outOfStockItems,
    loadItems, createItem, updateItem, deleteItem, quickExit,
    loadAlerts, createMovement, createBatchMovement,
  }
})
