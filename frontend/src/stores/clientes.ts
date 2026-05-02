import { defineStore } from 'pinia'
import { ref } from 'vue'
import { clientesAPI, type Cliente, type ClienteCreate } from '@/services/api'

export const useClientesStore = defineStore('clientes', () => {
  const clientes = ref<Cliente[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadClientes(search?: string) {
    try {
      loading.value = true
      error.value = null
      clientes.value = await clientesAPI.getAll({ search, limit: 200 })
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Erro ao carregar clientes'
    } finally {
      loading.value = false
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
