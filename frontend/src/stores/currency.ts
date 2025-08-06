import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export type CurrencyCode = 'G$' | 'R$' | 'USD' | 'EUR'

interface ExchangeRates {
  'G$': number
  'R$': number
  'USD': number
  'EUR': number
}

export const useCurrencyStore = defineStore('currency', () => {
  const selectedCurrency = ref<CurrencyCode>(
    (localStorage.getItem('selectedCurrency') as CurrencyCode) || 'USD'
  )
  
  // Base exchange rates (all relative to USD)
  const exchangeRates = ref<ExchangeRates>({
    'USD': 1.0, // Base currency
    'G$': 7300, // 1 USD = 7,300 Guaranies (approximate)
    'R$': 5.20, // 1 USD = 5.20 Brazilian Real (approximate)
    'EUR': 0.92 // 1 USD = 0.92 Euro (approximate)
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
    updateExchangeRates
  }
})