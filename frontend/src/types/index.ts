// Base types
export type Currency = 'G$' | 'R$' | 'U$' | 'EUR'
export type PaymentMethod = 'DEBITO' | 'CREDITO' | 'PIX' | 'DINHEIRO' | 'TRANSFERENCIA'
export type OrderStatus = 'PENDENTE' | 'PROCESSANDO' | 'ENVIADO' | 'ENTREGUE'
export type ShippingCarrier = 'CORREIOS' | 'AZUL_CARGO' | 'PARTICULAR' | 'SUPERFRETE'

// Entity types
export interface User {
  id: string
  nome: string
  email: string
  role: 'admin' | 'manager' | 'employee'
  createdAt: Date
  updatedAt: Date
}

export interface Vendedor {
  id: string
  nome: string
  taxa_comissao: number
  meta_semanal: number
  conta_bancaria?: string
  telefone?: string
  ativo: boolean
  total_vendas?: number
  comissao_acumulada?: number
  createdAt: Date
  updatedAt: Date
}

export interface Cambista {
  id: string
  nome: string
  taxa_g_para_r: number
  taxa_u_para_r: number
  taxa_eur_para_r: number
  conta_bancaria?: string
  telefone?: string
  observacoes?: string
  ativo: boolean
  createdAt: Date
  updatedAt: Date
}

export interface Venda {
  id: string
  vendedor_id: string
  vendedor?: Vendedor
  cambista_id?: string
  cambista?: Cambista
  moeda: Currency
  valor_bruto: number
  taxa_cambio_usada?: number
  valor_cambista?: number
  valor_liquido: number
  metodo_pagamento: PaymentMethod
  data_venda: Date
  descricao_produto?: string
  observacoes?: string
  createdAt: Date
  updatedAt: Date
}

export interface Pedido {
  id: string
  cliente_nome: string
  cliente_telefone?: string
  cliente_email?: string
  endereco_rua: string
  endereco_numero?: string
  endereco_complemento?: string
  endereco_bairro?: string
  endereco_cidade: string
  endereco_uf: string
  endereco_cep: string
  transportadora: ShippingCarrier
  codigo_rastreio?: string
  valor_frete?: number
  peso_kg?: number
  status: OrderStatus
  data_criacao: Date
  data_envio?: Date
  data_entrega?: Date
  observacoes?: string
  createdAt: Date
  updatedAt: Date
}

// API Response types
export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// Dashboard types
export interface DashboardStats {
  totalSales: number
  totalRevenue: number
  activeVendors: number
  pendingOrders: number
  salesGrowth: number
  revenueGrowth: number
}

export interface SalesChart {
  date: string
  vendas: number
  receita: number
}

export interface VendorPerformance {
  vendedor_id: string
  nome: string
  vendas: number
  comissao: number
  meta_atingida: boolean
}

// Form types
export interface LoginForm {
  email: string
  password: string
}

export interface VendedorForm {
  nome: string
  taxa_comissao: number
  meta_semanal: number
  conta_bancaria?: string
  telefone?: string
}

export interface CambistaForm {
  nome: string
  taxa_g_para_r: number
  taxa_u_para_r: number
  taxa_eur_para_r: number
  conta_bancaria?: string
  telefone?: string
  observacoes?: string
}

export interface VendaForm {
  vendedor_id: string
  cambista_id?: string
  moeda: Currency
  valor_bruto: number
  metodo_pagamento: PaymentMethod
  data_venda: Date
  descricao_produto?: string
  observacoes?: string
}

export interface PedidoForm {
  cliente_nome: string
  cliente_telefone?: string
  cliente_email?: string
  endereco_rua: string
  endereco_numero?: string
  endereco_complemento?: string
  endereco_bairro?: string
  endereco_cidade: string
  endereco_uf: string
  endereco_cep: string
  transportadora: ShippingCarrier
  codigo_rastreio?: string
  valor_frete?: number
  peso_kg?: number
  observacoes?: string
}

// Error types
export interface ApiError {
  message: string
  code?: string
  details?: Record<string, unknown>
}

// Filter and search types
export interface BaseFilters {
  page?: number
  pageSize?: number
  search?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export interface VendasFilters extends BaseFilters {
  vendedor_id?: string
  moeda?: Currency
  data_inicio?: Date
  data_fim?: Date
  metodo_pagamento?: PaymentMethod
}

export interface PedidosFilters extends BaseFilters {
  status?: OrderStatus
  transportadora?: ShippingCarrier
  data_inicio?: Date
  data_fim?: Date
}