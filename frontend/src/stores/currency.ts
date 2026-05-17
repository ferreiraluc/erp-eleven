import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { exchangeRateAPI, type QuickRateUpdate } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

export type CurrencyCode = 'G$' | 'R$' | 'USD' | 'EUR'

interface ExchangeRates {
  'G$': number
  'R$': number
  'USD': number
  'EUR': number
}

// Primary key used by the currency store; dashboard writes to LEGACY_KEY
const RATES_CACHE_KEY = 'erp_rates'
const LEGACY_KEY = 'erp_exchange_rates' // written by DashboardView.vue

function loadCachedRates(): Partial<ExchangeRates> {
  try {
    // Prefer our own key; fall back to the dashboard's legacy key
    const raw = localStorage.getItem(RATES_CACHE_KEY) || localStorage.getItem(LEGACY_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return {
      'G$': parsed['G$'] > 0 ? parsed['G$'] : undefined,
      'R$': parsed['R$'] > 0 ? parsed['R$'] : undefined,
      'EUR': parsed['EUR'] > 0 ? parsed['EUR'] : undefined,
    }
  } catch { return {} }
}

function saveCachedRates(rates: ExchangeRates) {
  try {
    const data = { 'G$': rates['G$'], 'R$': rates['R$'], 'EUR': rates['EUR'] }
    localStorage.setItem(RATES_CACHE_KEY, JSON.stringify(data))
    // Also update the legacy key so the dashboard widget stays in sync
    localStorage.setItem(LEGACY_KEY, JSON.stringify(data))
  } catch { /* ignore storage errors */ }
}

export const useCurrencyStore = defineStore('currency', () => {
  const selectedCurrency = ref<CurrencyCode>(
    (localStorage.getItem('selectedCurrency') as CurrencyCode) || 'USD'
  )

  // Seed from localStorage so rates survive page reloads and navigation
  const cached = loadCachedRates()

  // Base exchange rates (all relative to USD)
  const exchangeRates = ref<ExchangeRates>({
    'USD': 1.0,
    'G$': cached['G$'] ?? 7300,
    'R$': cached['R$'] ?? 5.20,
    'EUR': cached['EUR'] ?? 0.92,
  })

  const availableCurrencies = computed(() => [
    { code: 'USD' as CurrencyCode, name: 'US Dollar', symbol: '$', flag: '🇺🇸' },
    { code: 'G$' as CurrencyCode, name: 'Paraguayan Guaraní', symbol: '₲', flag: '🇵🇾' },
    { code: 'R$' as CurrencyCode, name: 'Brazilian Real', symbol: 'R$', flag: '🇧🇷' },
    { code: 'EUR' as CurrencyCode, name: 'Euro', symbol: '€', flag: '🇪🇺' }
  ])

  const getCurrentCurrency = computed(() => {
    return availableCurrencies.value.find(c => c.code === selectedCurrency.value)
  })

  const setSelectedCurrency = (currency: CurrencyCode) => {
    selectedCurrency.value = currency
    localStorage.setItem('selectedCurrency', currency)
  }

  const convertFromUSD = (amountInUSD: number, toCurrency: CurrencyCode): number => {
    const rate = exchangeRates.value[toCurrency]
    return amountInUSD * rate
  }

  const convertToUSD = (amount: number, fromCurrency: CurrencyCode): number => {
    const rate = exchangeRates.value[fromCurrency]
    return amount / rate
  }

  const convertBetweenCurrencies = (amount: number, from: CurrencyCode, to: CurrencyCode): number => {
    if (from === to) return amount
    
    // Convert to USD first, then to target currency
    const amountInUSD = convertToUSD(amount, from)
    return convertFromUSD(amountInUSD, to)
  }

  const formatCurrency = (amount: number, currency?: CurrencyCode): string => {
    const targetCurrency = currency || selectedCurrency.value
    const currencyInfo = availableCurrencies.value.find(c => c.code === targetCurrency)
    
    if (!currencyInfo) return amount.toString()

    const formattedAmount = amount.toLocaleString('pt-BR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })

    return `${currencyInfo.symbol} ${formattedAmount}`
  }

  const updateExchangeRates = (newRates: Partial<ExchangeRates>) => {
    exchangeRates.value = { ...exchangeRates.value, ...newRates }
  }

  // API Integration
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<string | null>(null)

  const loadCurrentRates = async () => {
    try {
      isLoading.value = true
      error.value = null
      
      const response = await exchangeRateAPI.getCurrentRates()
      
      // Update exchange rates with API data
      if (response.usd_to_pyg) exchangeRates.value['G$'] = response.usd_to_pyg
      if (response.usd_to_brl) exchangeRates.value['R$'] = response.usd_to_brl
      if (response.eur_to_usd) exchangeRates.value['EUR'] = 1 / response.eur_to_usd

      lastUpdate.value = response.last_updated

      // Persist so other views (PDV, etc.) pick up real values immediately
      saveCachedRates(exchangeRates.value)
      
    } catch (err: any) {
      error.value = err.message || 'Failed to load exchange rates'
      console.error('Error loading exchange rates:', err)
    } finally {
      isLoading.value = false
    }
  }

  const updateRatesAPI = async (rates: {
    usd_to_pyg?: number
    usd_to_brl?: number  
    eur_to_usd?: number
    eur_to_brl?: number
  }) => {
    try {
      const authStore = useAuthStore()
      if (!authStore.user) throw new Error('User not authenticated')

      isLoading.value = true
      error.value = null

      const updateData: QuickRateUpdate = {
        ...rates,
        source: 'Dashboard',
        updated_by: authStore.user.nome,
        notes: 'Updated from dashboard'
      }

      await exchangeRateAPI.quickUpdate(updateData)
      
      // Reload current rates to get updated data
      await loadCurrentRates()
      
    } catch (err: any) {
      error.value = err.message || 'Failed to update exchange rates'
      console.error('Error updating exchange rates:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  const canEdit = computed(() => {
    const authStore = useAuthStore()
    return authStore.user && ['ADMIN', 'GERENTE'].includes(authStore.user.role)
  })

  return {
    selectedCurrency,
    exchangeRates,
    availableCurrencies,
    getCurrentCurrency,
    setSelectedCurrency,
    convertFromUSD,
    convertToUSD,
    convertBetweenCurrencies,
    formatCurrency,
    updateExchangeRates,
    // API methods
    isLoading,
    error,
    lastUpdate,
    loadCurrentRates,
    updateRatesAPI,
    canEdit
  }
})