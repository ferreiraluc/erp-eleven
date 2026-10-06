import { defineStore } from 'pinia'
import { ref } from 'vue'
import { clientesAPI, type Cliente, type ClienteCreate } from '@/services/api'
export type CustomerStatusFilter = 'active' | 'inactive' | 'all'

export const useClientesStore = defineStore('clientes', () => {
  const clientes = ref<Cliente[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  let loadSequence = 0
  async function loadClientes(search?: string, status: CustomerStatusFilter = 'active') {
    const sequence = ++loadSequence
    try {
      loading.value = true
      error.value = null
      const result = await clientesAPI.getAll({ search, ativo: status !== 'inactive', include_inactive: status === 'all', limit: 200 })
      if (sequence === loadSequence) clientes.value = result
    } catch (e: any) {
      if (sequence === loadSequence) error.value = e.response?.data?.detail || 'Erro ao carregar clientes'
    } finally {
      if (sequence === loadSequence) loading.value = false
    }
  }

  async function createCliente(data: ClienteCreate): Promise<Cliente> {
    const novo = await clientesAPI.create(data)
    clientes.value.unshift(novo)
    return novo
  }

  async function updateCliente(id: string, data: Partial<ClienteCreate>): Promise<Cliente> {
    const updated = await clientesAPI.update(id, data)
    const idx = clientes.value.findIndex(c => c.id === id)
    if (idx !== -1) clientes.value[idx] = updated
    return updated
  }

  async function deleteCliente(id: string) {
    await clientesAPI.delete(id)
    const idx = clientes.value.findIndex(c => c.id === id)
    if (idx !== -1) clientes.value[idx].ativo = false
  }

  return { clientes, loading, error, loadClientes, createCliente, updateCliente, deleteCliente }
})
