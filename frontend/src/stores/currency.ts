import { ref, computed, watch } from 'vue'
import { uiText, uiLocale } from '@/i18n/uiText'
import { defineStore } from 'pinia'
import { exchangeRateAPI, type QuickRateUpdate, type ExchangeRateResponse } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

export type CurrencyCode = 'G$' | 'R$' | 'USD' | 'EUR'

interface ExchangeRates {
  'G$': number
  'R$': number
  'USD': number
  'EUR': number
}

// One cache; the legacy dashboard key is read only during migration.
const RATES_CACHE_KEY = 'erp_rates'
const LEGACY_KEY = 'erp_exchange_rates'

function loadCachedRates(): Partial<ExchangeRates> {
  try {
    // Prefer our own key; fall back to the dashboard's legacy key
    const raw = localStorage.getItem(RATES_CACHE_KEY) || localStorage.getItem(LEGACY_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return {
      'G$': Number.isFinite(Number(parsed['G$'])) && Number(parsed['G$']) > 0 ? Number(parsed['G$']) : undefined,
      'R$': Number.isFinite(Number(parsed['R$'])) && Number(parsed['R$']) > 0 ? Number(parsed['R$']) : undefined,
      'EUR': Number.isFinite(Number(parsed['EUR'])) && Number(parsed['EUR']) > 0 ? Number(parsed['EUR']) : undefined,
    }
  } catch { return {} }
}

function saveCachedRates(rates: ExchangeRates) {
  try {
    const data = { 'G$': rates['G$'], 'R$': rates['R$'], 'EUR': rates['EUR'] }
    localStorage.setItem(RATES_CACHE_KEY, JSON.stringify(data))
    localStorage.removeItem(LEGACY_KEY)
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
    { code: 'USD' as CurrencyCode, name: uiText("Dólar americano"), symbol: '$', flag: '🇺🇸' },
    { code: 'G$' as CurrencyCode, name: uiText("Guarani paraguaio"), symbol: '₲', flag: '🇵🇾' },
    { code: 'R$' as CurrencyCode, name: uiText("Real brasileiro"), symbol: 'R$', flag: '🇧🇷' },
    { code: 'EUR' as CurrencyCode, name: uiText("Euro"), symbol: '€', flag: '🇪🇺' }
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

    const formattedAmount = amount.toLocaleString(uiLocale(), {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })

    return `${currencyInfo.symbol} ${formattedAmount}`
  }

  const currentRates = ref<ExchangeRateResponse | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<string | null>(null)
  const auth = useAuthStore()
  let generation = 0
  let pending: Promise<boolean> | null = null
  watch([() => auth.user?.id, () => auth.token], () => {
    generation++; pending = null; currentRates.value = null; error.value = null; isLoading.value = false
  }, { flush: 'sync' })

  const loadCurrentRates = (): Promise<boolean> => {
    if (pending) return pending
    const request = ++generation, owner = auth.user?.id, token = auth.token
    isLoading.value = true; error.value = null
    const active = () => request === generation && owner === auth.user?.id && token === auth.token
    pending = exchangeRateAPI.getCurrentRates().then(response => {
      if (!active()) return false
      // Pydantic Decimal is serialized as a string. Normalize at the shared boundary.
      const positive = (value: unknown) => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : null
      currentRates.value = { ...response, usd_to_pyg: positive(response.usd_to_pyg), usd_to_brl: positive(response.usd_to_brl),
        eur_to_usd: positive(response.eur_to_usd), eur_to_brl: positive(response.eur_to_brl) }
      const rates = currentRates.value
      exchangeRates.value = { USD: 1, 'G$': rates.usd_to_pyg ?? 0, 'R$': rates.usd_to_brl ?? 0, EUR: rates.eur_to_usd ? 1 / rates.eur_to_usd : 0 }
      lastUpdate.value = response.last_updated
      saveCachedRates(exchangeRates.value)
      return true
    }).catch(() => {
      if (active()) error.value = uiText('Erro ao carregar taxas de câmbio')
      return false
    }).finally(() => { if (active()) { pending = null; isLoading.value = false } })
    return pending
  }

  const updateRatesAPI = async (rates: Partial<QuickRateUpdate>) => {
    if (!auth.user) throw new Error(uiText('Usuário não autenticado'))
    const owner = auth.user.id, token = auth.token
    await exchangeRateAPI.quickUpdate({ ...rates, source: rates.source || 'ERP', updated_by: auth.user.nome })
    if (owner !== auth.user?.id || token !== auth.token) throw new Error(uiText('Usuário não autenticado'))
    // Discard an older in-flight read that could overwrite the newly saved values.
    generation++; pending = null
    if (!await loadCurrentRates()) throw new Error(uiText('Taxas salvas. Não foi possível recarregar; tente atualizar.'))
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
    currentRates,
    // API methods
    isLoading,
    error,
    lastUpdate,
    loadCurrentRates,
    updateRatesAPI,
    canEdit
  }
})