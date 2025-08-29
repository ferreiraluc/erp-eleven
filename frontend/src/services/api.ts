import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_data')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export interface LoginRequest {
  email: string
  senha: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface DashboardStats {
  total_sales_today: number
  total_sales_week: number
  total_sales_month: number
  pending_orders: number
  active_vendors: number
  exchange_rate_g_to_r: number
}

export interface Sale {
  id: string
  data_venda: string
  vendedor_nome: string
  moeda: string
  valor_bruto: number
  valor_liquido: number
  metodo_pagamento: string
  descricao_produto: string
}

export interface Vendor {
  id: string
  nome: string
  taxa_comissao: number
  meta_semanal: number
  telefone: string
  ativo: boolean
}

export interface User {
  id: string
  nome: string
  email: string
  role: string
  ativo: boolean
  ultimo_login?: string
  created_at: string
  updated_at: string
}

// Auth API
export const authAPI = {
  login: (credentials: LoginRequest): Promise<LoginResponse> => 
    api.post('/api/auth/login', credentials).then(res => res.data),
  
  getCurrentUser: (): Promise<User> => 
    api.get('/api/auth/me').then(res => res.data),
  
  logout: (): Promise<void> => 
    api.post('/api/auth/logout').then(res => res.data),
}

// Dashboard API
export const dashboardAPI = {
  getStats: (): Promise<DashboardStats> => 
    api.get('/api/dashboard/stats').then(res => res.data),
  
  getRecentSales: (limit = 10): Promise<Sale[]> => 
    api.get(`/api/vendas/?limit=${limit}`).then(res => res.data),
}

// Sales API
export const salesAPI = {
  getAll: (): Promise<Sale[]> => 
    api.get('/api/vendas/').then(res => res.data),
  
  create: (sale: Partial<Sale>): Promise<Sale> => 
    api.post('/api/vendas/', sale).then(res => res.data),
}

// Vendor Types
export interface VendorCreate {
  nome: string
  taxa_comissao?: number
  meta_semanal?: number
  conta_bancaria?: string
  telefone?: string
  ativo?: boolean
  usuario_id?: string
}

export interface VendorResponse {
  id: string
  nome: string
  taxa_comissao: number
  meta_semanal: number
  conta_bancaria?: string
  telefone?: string
  ativo: boolean
  created_at: string
  updated_at: string
}

// Vendors API
export const vendorsAPI = {
  getAll: (skip = 0, limit = 100, ativo?: boolean): Promise<VendorResponse[]> => {
    let url = `/api/vendedores/?skip=${skip}&limit=${limit}`
    if (ativo !== undefined) {
      url += `&ativo=${ativo}`
    }
    return api.get(url).then(res => res.data)
  },
  
  getById: (id: string): Promise<VendorResponse> => 
    api.get(`/api/vendedores/${id}`).then(res => res.data),
  
  create: (vendor: VendorCreate): Promise<VendorResponse> => 
    api.post('/api/vendedores/', vendor).then(res => res.data),
  
  update: (id: string, vendor: Partial<VendorCreate>): Promise<VendorResponse> => 
    api.put(`/api/vendedores/${id}`, vendor).then(res => res.data),
  
  delete: (id: string): Promise<{message: string}> => 
    api.delete(`/api/vendedores/${id}`).then(res => res.data),
}

// Exchange Rate Types
export interface ExchangeRateResponse {
  usd_to_pyg: number | null
  usd_to_brl: number | null
  eur_to_usd: number | null
  eur_to_brl: number | null
  last_updated: string | null
  source: string | null
}

export interface QuickRateUpdate {
  usd_to_pyg?: number
  usd_to_brl?: number
  eur_to_usd?: number
  eur_to_brl?: number
  source: string
  notes?: string
  updated_by: string
}

export interface HistoricalRateUpdate {
  rate?: number
  source?: string
  notes?: string
  updated_by?: string
}

export interface ExchangeRateHistory {
  current_rates: ExchangeRateResponse
  historical_rates: Array<{
    id: string
    currency_pair: string
    rate: number
    source: string
    is_active: boolean
    created_at: string
    updated_by: string
  }>
  total_records: number
}

// Exchange Rate API
export const exchangeRateAPI = {
  getCurrentRates: (): Promise<ExchangeRateResponse> =>
    api.get('/api/exchange-rates/current').then(res => res.data),
  
  quickUpdate: (rates: QuickRateUpdate): Promise<any> =>
    api.post('/api/exchange-rates/quick-update', rates).then(res => res.data),
  
  getHistory: (days = 30): Promise<ExchangeRateHistory> =>
    api.get(`/api/exchange-rates/history?days=${days}`).then(res => res.data),
  
  getWeeklyAverage: (currencyPair: string, weeksBack = 0): Promise<any> =>
    api.get(`/api/exchange-rates/weekly-average/${currencyPair}?weeks_back=${weeksBack}`).then(res => res.data),
    
  getSalesAverage: (currencyPair: string, daysBack = 7): Promise<any> =>
    api.get(`/api/exchange-rates/sales-average/${currencyPair}?days_back=${daysBack}`).then(res => res.data),
    
  editHistoricalRate: (rateId: string, update: HistoricalRateUpdate): Promise<any> =>
    api.put(`/api/exchange-rates/history/${rateId}`, update).then(res => res.data),
    
  deleteHistoricalRate: (rateId: string): Promise<any> =>
    api.delete(`/api/exchange-rates/history/${rateId}`).then(res => res.data)
}

export default api