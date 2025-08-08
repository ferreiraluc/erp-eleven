// Types for Exchange Rate functionality

export interface ExchangeRate {
  id: string
  currency_pair: CurrencyPair
  rate: number
  source?: string
  is_active: boolean
  rate_date: string
  notes?: string
  created_at: string
  updated_at: string
  updated_by?: string
}

export enum CurrencyPair {
  USD_TO_PYG = 'USD_TO_PYG',
  USD_TO_BRL = 'USD_TO_BRL', 
  EUR_TO_PYG = 'EUR_TO_PYG',
  EUR_TO_BRL = 'EUR_TO_BRL'
}

export interface CurrentRatesResponse {
  usd_to_pyg?: number
  usd_to_brl?: number
  eur_to_pyg?: number
  eur_to_brl?: number
  last_updated?: string
  source?: string
}

export interface QuickRateUpdate {
  usd_to_pyg?: number | null
  usd_to_brl?: number | null
  eur_to_pyg?: number | null
  eur_to_brl?: number | null
  source?: string
  notes?: string
  updated_by: string
}

export interface WeeklyAverage {
  currency_pair: string
  week_start: string
  week_end: string
  average_rate: number
  sample_count: number
  min_rate: number
  max_rate: number
  rates_details?: ExchangeRate[]
}

export interface SalesWeekAverage extends WeeklyAverage {
  sales_week_start: string
  sales_week_end: string
  daily_rates: DailyRate[]
  recommendation: string
}

export interface DailyRate {
  date: string
  rate: number
  source: string
  updated_by?: string
}

export interface RateHistoryResponse {
  current_rates: CurrentRatesResponse
  weekly_averages: WeeklyAverage[]
  historical_rates: ExchangeRate[]
  total_records: number
}

export interface RateUpdateResponse {
  message: string
  updated_rates: {
    pair: string
    rate: number
    source: string
  }[]
  timestamp: string
  updated_by: string
}

// UI Helper Types
export interface RateDisplayItem {
  pair: string
  label: string
  value: number
  source?: string
  updated_at?: string
  change?: string
  trend?: 'positive' | 'negative' | 'neutral'
}

export interface EditableRateItem {
  pair: string
  label: string
  value: number
  placeholder: string
}

export interface WeekOption {
  offset: number
  label: string
}

export interface HistoryFilter {
  days?: number
  currency_pair?: string
}

// Store State Types
export interface ExchangeRateState {
  rates: CurrentRatesResponse
  weeklyAverages: WeeklyAverage[]
  historyData: ExchangeRate[]
  loading: boolean
  error: string | null
}

// API Error Types
export interface ApiError {
  detail: string
  status_code: number
}