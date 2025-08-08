// Exchange Rate Store (Pinia)
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ExchangeRate, WeeklyAverage, QuickRateUpdate } from '@/types/exchangeRate'

export const useExchangeRateStore = defineStore('exchangeRate', () => {
  // State
  const rates = ref({
    usd_to_brl: 0,
    usd_to_pyg: 0,
    eur_to_brl: 0,
    eur_to_pyg: 0,
    last_updated: null as string | null,
    source: null as string | null
  })

  const weeklyAverages = ref<WeeklyAverage[]>([])
  const historyData = ref<ExchangeRate[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isLoading = computed(() => loading.value)
  const hasError = computed(() => error.value !== null)
  const lastUpdated = computed(() => {
    if (!rates.value.last_updated) return null
    return new Date(rates.value.last_updated)
  })

  // Actions
  const fetchCurrentRates = async () => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch('/api/exchange-rates/current', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      
      rates.value = {
        usd_to_brl: data.usd_to_brl || 0,
        usd_to_pyg: data.usd_to_pyg || 0,
        eur_to_brl: data.eur_to_brl || 0,
        eur_to_pyg: data.eur_to_pyg || 0,
        last_updated: data.last_updated,
        source: data.source
      }

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao buscar taxas de câmbio'
      console.error('Error fetching exchange rates:', err)
    } finally {
      loading.value = false
    }
  }

  const updateRates = async (updateData: QuickRateUpdate) => {
    loading.value = true
    error.value = null

    try {
      const response = await fetch('/api/exchange-rates/quick-update', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updateData)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      
      // Refresh current rates after update
      await fetchCurrentRates()
      
      return result

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao atualizar taxas de câmbio'
      throw err
    } finally {
      loading.value = false
    }
  }

  const getWeeklyAverages = async (weeksBack: number = 0) => {
    loading.value = true
    error.value = null

    try {
      const averages: WeeklyAverage[] = []

      // Fetch weekly averages for each currency pair
      const currencyPairs = ['USD_TO_BRL', 'USD_TO_PYG', 'EUR_TO_BRL', 'EUR_TO_PYG']
      
      await Promise.all(
        currencyPairs.map(async (pair) => {
          try {
            const response = await fetch(
              `/api/exchange-rates/weekly-average/${pair}?weeks_back=${weeksBack}`,
              {
                headers: {
                  'Authorization': `Bearer ${localStorage.getItem('token')}`,
                  'Content-Type': 'application/json'
                }
              }
            )

            if (response.ok) {
              const data = await response.json()
              averages.push(data)
            }
          } catch (err) {
            console.warn(`Failed to fetch weekly average for ${pair}:`, err)
          }
        })
      )

      weeklyAverages.value = averages
      return averages

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao buscar médias semanais'
      console.error('Error fetching weekly averages:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  const getSalesWeekAverage = async (saturdayDate: string) => {
    loading.value = true
    error.value = null

    try {
      const averages: any[] = []
      const currencyPairs = ['USD_TO_BRL', 'USD_TO_PYG', 'EUR_TO_BRL', 'EUR_TO_PYG']
      
      await Promise.all(
        currencyPairs.map(async (pair) => {
          try {
            const response = await fetch(
              `/api/exchange-rates/sales-week-average/${pair}?saturday_date=${saturdayDate}`,
              {
                headers: {
                  'Authorization': `Bearer ${localStorage.getItem('token')}`,
                  'Content-Type': 'application/json'
                }
              }
            )

            if (response.ok) {
              const data = await response.json()
              averages.push(data)
            }
          } catch (err) {
            console.warn(`Failed to fetch sales week average for ${pair}:`, err)
          }
        })
      )

      return averages

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao buscar médias da semana de vendas'
      throw err
    } finally {
      loading.value = false
    }
  }

  const getHistory = async (filters: { days?: number; currency_pair?: string } = {}) => {
    loading.value = true
    error.value = null

    try {
      const params = new URLSearchParams()
      if (filters.days) params.append('days', filters.days.toString())

      const response = await fetch(`/api/exchange-rates/history?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      
      // Filter by currency pair if specified
      let history = data.historical_rates || []
      if (filters.currency_pair) {
        history = history.filter((rate: ExchangeRate) => 
          rate.currency_pair === filters.currency_pair
        )
      }

      historyData.value = history
      return history

    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao buscar histórico'
      console.error('Error fetching history:', err)
      return []
    } finally {
      loading.value = false
    }
  }

  const getRateByPair = (pair: string): number => {
    switch (pair) {
      case 'USD_TO_BRL':
        return rates.value.usd_to_brl
      case 'USD_TO_PYG':
        return rates.value.usd_to_pyg
      case 'EUR_TO_BRL':
        return rates.value.eur_to_brl
      case 'EUR_TO_PYG':
        return rates.value.eur_to_pyg
      default:
        return 0
    }
  }

  const convertCurrency = (amount: number, fromCurrency: string, toCurrency: string): number => {
    // Simple conversion logic - you might want to expand this
    const rate = getRateByPair(`${fromCurrency}_TO_${toCurrency}`)
    return rate ? amount * rate : 0
  }

  // Helper function to format currency display
  const formatCurrencyPair = (pair: string): string => {
    const formatMap = {
      'USD_TO_BRL': 'USD → BRL',
      'USD_TO_PYG': 'USD → G$',
      'EUR_TO_BRL': 'EUR → BRL',
      'EUR_TO_PYG': 'EUR → G$'
    }
    return formatMap[pair] || pair
  }

  // Helper function to get currency symbol
  const getCurrencySymbol = (currency: string): string => {
    const symbolMap = {
      'USD': '$',
      'EUR': '€',
      'BRL': 'R$',
      'PYG': 'G$'
    }
    return symbolMap[currency] || currency
  }

  // Clear error
  const clearError = () => {
    error.value = null
  }

  // Reset store
  const resetStore = () => {
    rates.value = {
      usd_to_brl: 0,
      usd_to_pyg: 0,
      eur_to_brl: 0,
      eur_to_pyg: 0,
      last_updated: null,
      source: null
    }
    weeklyAverages.value = []
    historyData.value = []
    loading.value = false
    error.value = null
  }

  return {
    // State
    rates,
    weeklyAverages,
    historyData,
    loading,
    error,

    // Getters
    isLoading,
    hasError,
    lastUpdated,

    // Actions
    fetchCurrentRates,
    updateRates,
    getWeeklyAverages,
    getSalesWeekAverage,
    getHistory,
    getRateByPair,
    convertCurrency,
    
    // Helpers
    formatCurrencyPair,
    getCurrencySymbol,
    clearError,
    resetStore
  }
})