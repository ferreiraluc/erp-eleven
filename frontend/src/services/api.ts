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
      localStorage.removeItem('erp_last_route')
      // Use hash-based URL to work correctly with the hash router in production
      window.location.replace('/#/login')
    }
    return Promise.reject(error)
  }
)

export interface HealthStatus {
  api: 'online' | 'offline'
  database: 'online' | 'offline'
  timestamp: number
}

export const healthAPI = {
  check: (): Promise<HealthStatus> =>
    api.get('/health', { timeout: 5000 }).then(r => r.data),
}

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

  // Folgas endpoints
  getFolgasCalendario: (ano: number, mes: number): Promise<any[]> =>
    api.get(`/api/vendedores/folgas/calendario?ano=${ano}&mes=${mes}`).then(res => res.data),

  getEstatisticasResumo: (ano: number, mes: number): Promise<{vendedores: any[]}> =>
    api.get(`/api/vendedores/estatisticas/resumo?ano=${ano}&mes=${mes}`).then(res => res.data),

  // Folgas CRUD
  createFolga: (vendedorId: string, folga: any): Promise<any> =>
    api.post(`/api/vendedores/${vendedorId}/folgas`, folga).then(res => res.data),

  updateFolga: (folgaId: string, folga: any): Promise<any> =>
    api.put(`/api/vendedores/folgas/${folgaId}`, folga).then(res => res.data),

  deleteFolga: (folgaId: string): Promise<{message: string}> =>
    api.delete(`/api/vendedores/folgas/${folgaId}`).then(res => res.data),
}

// Excel Import Types
export interface ImportPreviewRequest {
  file_path: string
  access_token: string
}

export interface ImportPreviewResponse {
  success: boolean
  total_rows: number
  valid_rows: number
  errors: string[]
  preview_data: ImportPreviewSale[]
}

export interface ImportPreviewSale {
  vendedor_nome: string
  data_venda: string
  valor_bruto: number
  moeda: string
  metodo_pagamento: string
  descricao_produto: string
  row_number: number
}

export interface ImportResultResponse {
  success: boolean
  imported_count: number
  skipped_count: number
  total_errors: number
  errors: string[]
}

// Excel Import API
export const excelImportAPI = {
  // Preview de formato personalizado (padrão para VENDASgeral.xlsx)
  previewUpload: (file: File): Promise<ImportPreviewResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/excel-import/preview-custom-format', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(res => res.data)
  },

  // Importar formato personalizado (padrão para VENDASgeral.xlsx)
  importUpload: (file: File): Promise<ImportResultResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/excel-import/import-custom-format', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(res => res.data)
  },

  // Obter template de planilha
  getTemplate: (): Promise<any> =>
    api.get('/api/excel-import/template').then(res => res.data),
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

// Tag Types
export interface Tag {
  id: string
  nome: string
  cor: string
  descricao?: string
  ordem: string
  ativo: boolean
  created_at: string
  updated_at: string
}

export interface TagCreate {
  nome: string
  cor?: string
  descricao?: string
  ordem?: string
  ativo?: boolean
}

// Tags API
export const tagsAPI = {
  getAll: (skip = 0, limit = 100, ativo = true): Promise<Tag[]> => {
    const url = `/api/tags/?skip=${skip}&limit=${limit}&ativo=${ativo}`
    return api.get(url).then(res => res.data)
  },

  getById: (id: string): Promise<Tag> =>
    api.get(`/api/tags/${id}`).then(res => res.data),

  create: (tag: TagCreate): Promise<Tag> =>
    api.post('/api/tags/', tag).then(res => res.data),

  update: (id: string, tag: Partial<TagCreate>): Promise<Tag> =>
    api.put(`/api/tags/${id}`, tag).then(res => res.data),

  delete: (id: string): Promise<{message: string}> =>
    api.delete(`/api/tags/${id}`).then(res => res.data),

  createDefaultTags: (): Promise<any> =>
    api.post('/api/tags/seed').then(res => res.data)
}

// Pedido Types (Simplified)
// ─── Cliente Types ─────────────────────────────────────────────────────────────

export interface Cliente {
  id: string
  nome: string
  telefone?: string
  email?: string
  cpf?: string
  endereco?: string
  ativo: boolean
  created_at: string
  updated_at: string
}

export interface ClienteCreate {
  nome: string
  telefone?: string
  email?: string
  cpf?: string
  endereco?: string
  ativo?: boolean
}

export interface Pedido {
  id: string
  numero_pedido: string
  descricao: string
  valor_total: number
  moeda?: string
  cliente_id?: string
  cliente_nome?: string
  cliente_telefone?: string
  cliente_email?: string
  endereco_entrega?: string
  status: 'PENDENTE' | 'PROCESSANDO' | 'ENVIADO' | 'ENTREGUE' | 'CANCELADO'
  codigo_rastreio?: string
  created_at: string
  updated_at: string
  created_by?: string
  tags: Tag[]
  cliente?: { id: string; nome: string; telefone?: string; email?: string; cpf?: string; endereco?: string }
  anexos_count?: number
}

export interface PedidoCreate {
  descricao: string
  valor_total: number
  moeda?: string
  cliente_id?: string
  cliente_nome?: string
  cliente_telefone?: string
  cliente_email?: string
  endereco_entrega?: string
  status?: 'PENDENTE' | 'PROCESSANDO' | 'ENVIADO' | 'ENTREGUE' | 'CANCELADO'
  codigo_rastreio?: string
  tag_ids?: string[]
}

// Pedidos API
export const pedidosAPI = {
  getAll: (params?: {
    skip?: number
    limit?: number
    status?: string
    cidade?: string
    transportadora?: string
    tag_id?: string
  }): Promise<Pedido[]> => {
    let url = '/api/pedidos/?'
    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, value.toString())
        }
      })
      url += searchParams.toString()
    }
    return api.get(url).then(res => res.data)
  },

  getById: (id: string): Promise<Pedido> =>
    api.get(`/api/pedidos/${id}`).then(res => res.data),

  getByNumber: (numero: string): Promise<Pedido> =>
    api.get(`/api/pedidos/numero/${numero}`).then(res => res.data),

  create: (pedido: PedidoCreate): Promise<Pedido> =>
    api.post('/api/pedidos/', pedido).then(res => res.data),

  update: (id: string, pedido: Partial<PedidoCreate & { tag_ids?: string[] }>): Promise<Pedido> =>
    api.put(`/api/pedidos/${id}`, pedido).then(res => res.data),

  delete: (id: string): Promise<{message: string}> =>
    api.delete(`/api/pedidos/${id}`).then(res => res.data),

  // Verificar rastreamento existente
  verificarRastreamento: (codigoRastreio: string): Promise<{
    exists: boolean
    rastreamento_id?: string
    status?: string
    pedido_associado?: string
  }> =>
    api.get(`/api/pedidos/rastreamento/${codigoRastreio}`).then(res => res.data)
}

// ─── Rastreamentos (quick list for autocomplete) ───────────────────────────────

export interface RastreamentoSimple {
  id: string
  codigo_rastreio: string
  status: string
  destinatario?: string
  descricao?: string
  pedido_id?: string
  numero_pedido?: string
}

export const rastreamentosAPI = {
  list: (params?: { limit?: number }): Promise<RastreamentoSimple[]> => {
    const p = new URLSearchParams()
    if (params?.limit) p.append('limit', String(params.limit))
    return api.get(`/api/rastreamento/?${p.toString()}`).then(r => r.data)
  },
}

// ─── Pedido Anexos ─────────────────────────────────────────────────────────────

export interface PedidoAnexo {
  id: string
  pedido_id: string
  nome_arquivo: string
  tipo_arquivo: string
  tamanho: number
  dados: string  // base64, no prefix
  created_at: string
  created_by?: string
}

export const pedidoAnexosAPI = {
  getAnexos: (pedidoId: string): Promise<PedidoAnexo[]> =>
    api.get(`/api/pedidos/${pedidoId}/anexos`).then(r => r.data),

  upload: (pedidoId: string, data: {
    nome_arquivo: string
    tipo_arquivo: string
    tamanho: number
    dados: string
  }): Promise<PedidoAnexo> =>
    api.post(`/api/pedidos/${pedidoId}/anexos`, data).then(r => r.data),

  delete: (pedidoId: string, anexoId: string): Promise<void> =>
    api.delete(`/api/pedidos/${pedidoId}/anexos/${anexoId}`).then(r => r.data),
}

// ─── Clientes API ──────────────────────────────────────────────────────────────

export const clientesAPI = {
  getAll: (params?: { search?: string; ativo?: boolean; skip?: number; limit?: number }): Promise<Cliente[]> => {
    const p = new URLSearchParams()
    if (params?.search) p.append('search', params.search)
    if (params?.ativo !== undefined) p.append('ativo', String(params.ativo))
    if (params?.skip !== undefined) p.append('skip', String(params.skip))
    if (params?.limit !== undefined) p.append('limit', String(params.limit))
    return api.get(`/api/clientes/?${p.toString()}`).then(r => r.data)
  },
  search: (q: string, limit = 10): Promise<Cliente[]> =>
    api.get(`/api/clientes/search?q=${encodeURIComponent(q)}&limit=${limit}`).then(r => r.data),
  getById: (id: string): Promise<Cliente> =>
    api.get(`/api/clientes/${id}`).then(r => r.data),
  create: (data: ClienteCreate): Promise<Cliente> =>
    api.post('/api/clientes/', data).then(r => r.data),
  update: (id: string, data: Partial<ClienteCreate>): Promise<Cliente> =>
    api.put(`/api/clientes/${id}`, data).then(r => r.data),
  delete: (id: string): Promise<{ message: string }> =>
    api.delete(`/api/clientes/${id}`).then(r => r.data),
  getPedidos: (id: string, params?: { skip?: number; limit?: number }): Promise<Pedido[]> => {
    const p = new URLSearchParams()
    if (params?.skip !== undefined) p.append('skip', String(params.skip))
    if (params?.limit !== undefined) p.append('limit', String(params.limit))
    return api.get(`/api/clientes/${id}/pedidos?${p.toString()}`).then(r => r.data)
  },
}

// ─── Inventory Types ──────────────────────────────────────────────────────────

export interface InventoryItem {
  id: string
  name: string
  description?: string
  category?: string
  size?: string
  color?: string
  unit: string
  location?: string
  barcode?: string
  sku_internal: string
  supplier_id?: string
  cost_price: number
  sale_price: number
  currency: string
  cost_currency: string
  sale_currency: string
  min_stock: number
  max_stock: number
  current_stock: number
  is_active: boolean
  alert_level?: string
  image_data?: string
  brand?: string
  group_key?: string
  created_at: string
  updated_at: string
  created_by?: string
}

export interface InventoryItemList {
  items: InventoryItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AlertSummary {
  low_stock_count: number
  out_of_stock_count: number
  overstocked_count: number
  total_active_items: number
}

export interface StockMovement {
  id: string
  item_id: string
  movement_type: string
  quantity: number
  quantity_before: number
  quantity_after: number
  reason?: string
  reference_type?: string
  reference_id?: string
  unit_cost?: number
  location_from?: string
  location_to?: string
  notes?: string
  created_at: string
  created_by?: string
}

export interface InventorySupplier {
  id: string
  name: string
  contact?: string
  is_active: boolean
  created_at: string
}

export interface GroupResponse {
  group_key: string
  items: InventoryItem[]
  total_stock: number
}

export interface SuggestionResponse {
  name: string
  items: InventoryItem[]
}

// ─── Inventory API ────────────────────────────────────────────────────────────

export const inventoryAPI = {
  getItems: (params: Record<string, any> = {}): Promise<InventoryItemList> => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.append(k, String(v)) })
    return api.get(`/api/inventory/items?${qs}`).then(res => res.data)
  },

  createItem: (item: Partial<InventoryItem>): Promise<InventoryItem> =>
    api.post('/api/inventory/items', item).then(res => res.data),

  getItem: (id: string): Promise<InventoryItem> =>
    api.get(`/api/inventory/items/${id}`).then(res => res.data),

  updateItem: (id: string, item: Partial<InventoryItem>): Promise<InventoryItem> =>
    api.put(`/api/inventory/items/${id}`, item).then(res => res.data),

  deleteItem: (id: string): Promise<{ message: string }> =>
    api.delete(`/api/inventory/items/${id}`).then(res => res.data),

  getByBarcode: (code: string): Promise<InventoryItem[]> =>
    api.get(`/api/inventory/items/barcode/${encodeURIComponent(code)}`).then(res => res.data),

  quickExit: (id: string): Promise<{ message: string; new_stock: number }> =>
    api.post(`/api/inventory/items/${id}/quick-exit`).then(res => res.data),

  groupItems: (itemIds: string[], groupKey: string): Promise<{ message: string; count: number }> =>
    api.post('/api/inventory/items/group', { item_ids: itemIds, group_key: groupKey }).then(res => res.data),

  ungroup: (groupKey: string): Promise<{ message: string; count: number }> =>
    api.post('/api/inventory/items/ungroup', { group_key: groupKey }).then(res => res.data),

  removeFromGroup: (itemId: string): Promise<{ message: string }> =>
    api.delete(`/api/inventory/items/${itemId}/group`).then(res => res.data),

  renameGroup: (oldKey: string, newKey: string): Promise<{ message: string; count: number }> =>
    api.patch('/api/inventory/groups', { old_key: oldKey, new_key: newKey }).then(res => res.data),

  getGroups: (search = ''): Promise<GroupResponse[]> => {
    const qs = search ? `?search=${encodeURIComponent(search)}` : ''
    return api.get(`/api/inventory/groups${qs}`).then(res => res.data)
  },

  getSuggestions: (): Promise<SuggestionResponse[]> =>
    api.get('/api/inventory/suggestions').then(res => res.data),

  batchEdit: (data: {
    item_ids: string[]
    brand?: string
    category?: string
    image_data?: string
    sizes?: Array<{ id: string; size?: string; name?: string; color?: string; barcode?: string }>
  }): Promise<{ message: string; count: number }> =>
    api.patch('/api/inventory/items/batch', data).then(res => res.data),

  getDistinctValues: (): Promise<{ brands: string[]; categories: string[] }> =>
    api.get('/api/inventory/items/distinct-values').then(res => res.data),

  getAlertsSummary: (): Promise<AlertSummary> =>
    api.get('/api/inventory/alerts/summary').then(res => res.data),

  createMovement: (data: any): Promise<StockMovement> =>
    api.post('/api/inventory/movements', data).then(res => res.data),

  createBatchMovement: (data: any): Promise<any> =>
    api.post('/api/inventory/movements/batch', data).then(res => res.data),

  getMovements: (params: Record<string, any> = {}): Promise<StockMovement[]> => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.append(k, String(v)) })
    return api.get(`/api/inventory/movements?${qs}`).then(res => res.data)
  },

  getItemMovements: (itemId: string, skip = 0, limit = 50): Promise<StockMovement[]> =>
    api.get(`/api/inventory/movements/item/${itemId}?skip=${skip}&limit=${limit}`).then(res => res.data),

  getSuppliers: (): Promise<InventorySupplier[]> =>
    api.get('/api/inventory/suppliers').then(res => res.data),

  createSupplier: (data: Partial<InventorySupplier>): Promise<InventorySupplier> =>
    api.post('/api/inventory/suppliers', data).then(res => res.data),

  getSessions: (): Promise<any[]> =>
    api.get('/api/inventory/sessions').then(res => res.data),

  createSession: (data: any): Promise<any> =>
    api.post('/api/inventory/sessions', data).then(res => res.data),

  getSession: (id: string): Promise<any> =>
    api.get(`/api/inventory/sessions/${id}`).then(res => res.data),

  updateSessionStatus: (id: string, status: string): Promise<any> =>
    api.put(`/api/inventory/sessions/${id}/status`, { status }).then(res => res.data),

  scanItem: (sessionId: string, data: any): Promise<any> =>
    api.post(`/api/inventory/sessions/${sessionId}/scan`, data).then(res => res.data),

  applySession: (sessionId: string): Promise<any> =>
    api.post(`/api/inventory/sessions/${sessionId}/apply`).then(res => res.data),

  importCsv: (file: File): Promise<{ created: number; skipped: number; errors: string[] }> => {
    const fd = new FormData(); fd.append('file', file)
    return api.post('/api/inventory/import/csv', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },

  importNfe: (
    file: File,
    opts: { category?: string; currency?: string }
  ): Promise<{ created: number; skipped: number; errors: string[] }> => {
    const fd = new FormData()
    fd.append('file', file)
    if (opts.category) fd.append('category', opts.category)
    fd.append('currency', opts.currency ?? 'BRL')
    return api.post('/api/inventory/import/nfe', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },
}

// Freight Calculator API
export const freteAPI = {
  calcular: (cep_origem: string, cep_destino: string, peso = 0.3) =>
    api.post('/api/rastreamento/calcular-frete', { cep_origem, cep_destino, peso }).then(r => r.data),
}

export default api