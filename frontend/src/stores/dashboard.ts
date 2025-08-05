import { defineStore } from 'pinia'
import { ref } from 'vue'
import { dashboardAPI, salesAPI, type DashboardStats, type Sale } from '@/services/api'

export const useDashboardStore = defineStore('dashboard', () => {
  const stats = ref<DashboardStats | null>(null)
  const recentSales = ref<Sale[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const loadStats = async () => {
    try {
      isLoading.value = true
      error.value = null
      
      // For now, create mock data since dashboard endpoint might not exist yet
      stats.value = {
        total_sales_today: 2450.50,
        total_sales_week: 15230.75,
        total_sales_month: 67890.25,
        pending_orders: 12,
        active_vendors: 5,
        exchange_rate_g_to_r: 5.65
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to load dashboard stats'
      console.error('Dashboard stats error:', err)
    } finally {
      isLoading.value = false
    }
  }

  const loadRecentSales = async () => {
    try {
      const sales = await salesAPI.getAll()
      recentSales.value = sales.slice(0, 5) // Get last 5 sales
    } catch (err: any) {
      console.error('Recent sales error:', err)
      // Mock recent sales data for now
      recentSales.value = []
    }
  }

  const refreshData = async () => {
    await Promise.all([
      loadStats(),
      loadRecentSales()
    ])
  }

  return {
    // State
    stats,
    recentSales,
    isLoading,
    error,
    
    // Actions
    loadStats,
    loadRecentSales,
    refreshData,
  }
})