import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

export interface EventoRastreio {
  data?: string
  local?: string
  situacao?: string
  detalhes?: string
  origem?: string
  destino?: string
}

export interface Rastreamento {
  id: string
  codigo_rastreio: string
  status: 'PENDENTE' | 'EM_TRANSITO' | 'ENTREGUE' | 'ERRO' | 'NAO_ENCONTRADO'
  servico_provedor?: string
  ultima_atualizacao?: string
  descricao?: string
  destinatario?: string
  origem?: string
  destino?: string
  historico_eventos: any[]
  pedido_id?: string
  data_criacao: string
  ativo: boolean
  created_at: string
  updated_at: string
  created_by?: string
  // Dados do pedido relacionado
  numero_pedido?: string
  cliente_nome?: string
  cliente_telefone?: string
  endereco_cidade?: string
  endereco_uf?: string
}

export interface RastreamentoCreate {
  codigo_rastreio: string
  descricao?: string
  destinatario?: string
  origem?: string
  destino?: string
  pedido_id?: string
}

export interface RastreamentoConsulta {
  codigo: string
  servico_id?: string
}

export interface RastreamentoConsultaResponse {
  codigo: string
  status: string
  service_provider: string
  data: EventoRastreio[]
  sucesso: boolean
  erro?: string
}

export interface RastreamentoResumo {
  total_rastreamentos: number
  em_transito: number
  entregues: number
  pendentes: number
  com_erro: number
  rastreamentos_recentes: Rastreamento[]
}

export const useRastreamentoStore = defineStore('rastreamento', () => {
  // Estado
  const rastreamentos = ref<Rastreamento[]>([])
  const rastreamentoAtual = ref<Rastreamento | null>(null)
  const resumoDashboard = ref<RastreamentoResumo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const rastreamentosAtivos = computed(() => 
    rastreamentos.value.filter(r => r.ativo)
  )

  const rastreamentosEmTransito = computed(() =>
    rastreamentosAtivos.value.filter(r => r.status === 'EM_TRANSITO')
  )

  const rastreamentosEntregues = computed(() =>
    rastreamentosAtivos.value.filter(r => r.status === 'ENTREGUE')
  )

  const rastreamentosPendentes = computed(() =>
    rastreamentosAtivos.value.filter(r => r.status === 'PENDENTE')
  )

  const rastreamentosComErro = computed(() =>
    rastreamentosAtivos.value.filter(r => 
      r.status === 'ERRO' || r.status === 'NAO_ENCONTRADO'
    )
  )

  // Actions
  async function listarRastreamentos(filtros?: {
    skip?: number
    limit?: number
    status_filter?: string
    ativo?: boolean
  }) {
    try {
      loading.value = true
      error.value = null

      const params = new URLSearchParams()
      if (filtros?.skip) params.append('skip', filtros.skip.toString())
      if (filtros?.limit) params.append('limit', filtros.limit.toString())
      if (filtros?.status_filter) params.append('status_filter', filtros.status_filter)
      if (filtros?.ativo !== undefined) params.append('ativo', filtros.ativo.toString())

      const url = `/api/rastreamento/${params.toString() ? '?' + params.toString() : ''}`
      const response = await api.get(url)
      
      rastreamentos.value = response.data
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao listar rastreamentos'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function criarRastreamento(dados: RastreamentoCreate) {
    try {
      loading.value = true
      error.value = null

      const response = await api.post('/api/rastreamento/', dados)
      
      rastreamentos.value.unshift(response.data)
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao criar rastreamento'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function obterRastreamento(id: string) {
    try {
      loading.value = true
      error.value = null

      const response = await api.get(`/api/rastreamento/${id}`)
      
      rastreamentoAtual.value = response.data
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao obter rastreamento'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function obterRastreamentoPorCodigo(codigo: string) {
    try {
      loading.value = true
      error.value = null

      const response = await api.get(`/api/rastreamento/codigo/${codigo}`)
      
      rastreamentoAtual.value = response.data
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao obter rastreamento'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function atualizarRastreamento(id: string, dados: Partial<Rastreamento>) {
    try {
      loading.value = true
      error.value = null

      const response = await api.put(`/api/rastreamento/${id}`, dados)
      
      const index = rastreamentos.value.findIndex(r => r.id === id)
      if (index !== -1) {
        rastreamentos.value[index] = response.data
      }
      
      if (rastreamentoAtual.value?.id === id) {
        rastreamentoAtual.value = response.data
      }
      
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao atualizar rastreamento'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function removerRastreamento(id: string) {
    try {
      loading.value = true
      error.value = null

      await api.delete(`/api/rastreamento/${id}`)
      
      rastreamentos.value = rastreamentos.value.filter(r => r.id !== id)
      
      if (rastreamentoAtual.value?.id === id) {
        rastreamentoAtual.value = null
      }
      
      return true
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao remover rastreamento'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function consultarRastreamentoOnline(consulta: RastreamentoConsulta): Promise<RastreamentoConsultaResponse> {
    try {
      loading.value = true
      error.value = null

      const response = await api.post('/api/rastreamento/consultar', consulta)
      
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao consultar rastreamento online'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function consultarESalvarRastreamento(consulta: RastreamentoConsulta) {
    try {
      loading.value = true
      error.value = null

      const response = await api.post('/api/rastreamento/consultar-e-salvar', consulta)
      
      // Verificar se já existe na lista e atualizar, senão adicionar
      const index = rastreamentos.value.findIndex(r => r.codigo_rastreio === consulta.codigo)
      if (index !== -1) {
        rastreamentos.value[index] = response.data
      } else {
        rastreamentos.value.unshift(response.data)
      }
      
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao consultar e salvar rastreamento'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function obterResumoDashboard() {
    try {
      loading.value = true
      error.value = null

      const response = await api.get('/api/rastreamento/resumo/dashboard')
      
      resumoDashboard.value = response.data
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao obter resumo da dashboard'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function atualizarTodosRastreamentos(servicoId: string = '0001') {
    try {
      loading.value = true
      error.value = null

      const response = await api.post(`/api/rastreamento/atualizar-todos?servico_id=${servicoId}`)
      
      // Recarregar a lista após atualização
      await listarRastreamentos()
      
      return response.data
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Erro ao atualizar rastreamentos'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Helpers
  function getStatusColor(status: string): string {
    switch (status) {
      case 'PENDENTE':
        return 'text-yellow-600'
      case 'EM_TRANSITO':
        return 'text-blue-600'
      case 'ENTREGUE':
        return 'text-green-600'
      case 'ERRO':
      case 'NAO_ENCONTRADO':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  function getStatusText(status: string): string {
    switch (status) {
      case 'PENDENTE':
        return 'Pendente'
      case 'EM_TRANSITO':
        return 'Em Trânsito'
      case 'ENTREGUE':
        return 'Entregue'
      case 'ERRO':
        return 'Erro'
      case 'NAO_ENCONTRADO':
        return 'Não Encontrado'
      default:
        return status
    }
  }

  function formatarData(data: string): string {
    if (!data) return ''
    
    try {
      return new Date(data).toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return data
    }
  }

  // Reset
  function resetState() {
    rastreamentos.value = []
    rastreamentoAtual.value = null
    resumoDashboard.value = null
    loading.value = false
    error.value = null
  }

  return {
    // Estado
    rastreamentos,
    rastreamentoAtual,
    resumoDashboard,
    loading,
    error,

    // Computed
    rastreamentosAtivos,
    rastreamentosEmTransito,
    rastreamentosEntregues,
    rastreamentosPendentes,
    rastreamentosComErro,

    // Actions
    listarRastreamentos,
    criarRastreamento,
    obterRastreamento,
    obterRastreamentoPorCodigo,
    atualizarRastreamento,
    removerRastreamento,
    consultarRastreamentoOnline,
    consultarESalvarRastreamento,
    obterResumoDashboard,
    atualizarTodosRastreamentos,

    // Helpers
    getStatusColor,
    getStatusText,
    formatarData,
    resetState
  }
})