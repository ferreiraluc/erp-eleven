<template>
  <div class="folgas-calendar-advanced">
    <!-- Header com filtros -->
    <div class="calendar-header">
      <div class="header-controls">
        <div class="month-navigation">
          <button @click="previousMonth" class="nav-button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
            </svg>
          </button>
          <h3 class="month-title">
            {{ monthNames[currentMonth] }} {{ currentYear }}
          </h3>
          <button @click="nextMonth" class="nav-button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
            </svg>
          </button>
        </div>

        <!-- Filtros avançados -->
        <div class="filters">
          <div class="filter-group">
            <label>Vendedor:</label>
            <select v-model="filters.vendedorId" @change="loadFolgas">
              <option value="">Todos</option>
              <option v-for="vendedor in vendedores" :key="vendedor.id" :value="vendedor.id">
                {{ vendedor.nome }}
              </option>
            </select>
          </div>

          <div class="filter-group">
            <label>Tipo:</label>
            <select v-model="filters.tipo" @change="loadFolgas">
              <option value="">Todos</option>
              <option value="FOLGA">Folga</option>
              <option value="FERIAS">Férias</option>
              <option value="LICENCA">Licença</option>
              <option value="FALTA">Falta</option>
              <option value="MEIO_PERIODO">Meio Período</option>
            </select>
          </div>

          <div class="filter-group">
            <label>Status:</label>
            <select v-model="filters.aprovado" @change="loadFolgas">
              <option value="">Todos</option>
              <option value="true">Aprovadas</option>
              <option value="false">Pendentes</option>
            </select>
          </div>
        </div>

        <!-- Ações em lote -->
        <div class="bulk-actions" v-if="selectedFolgas.length > 0">
          <span class="selected-count">{{ selectedFolgas.length }} selecionadas</span>
          <button @click="approveSelected" class="bulk-btn approve">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
            </svg>
            Aprovar
          </button>
          <button @click="rejectSelected" class="bulk-btn reject">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
            Rejeitar
          </button>
          <button @click="deleteSelected" class="bulk-btn delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
            Excluir
          </button>
        </div>
      </div>
    </div>

    <!-- Legenda -->
    <div class="calendar-legend">
      <div class="legend-item">
        <div class="legend-color pending"></div>
        <span>Pendente</span>
      </div>
      <div class="legend-item">
        <div class="legend-color approved"></div>
        <span>Aprovada</span>
      </div>
      <div class="legend-item">
        <div class="legend-color rejected"></div>
        <span>Rejeitada</span>
      </div>
      <div class="legend-item">
        <div class="legend-color today"></div>
        <span>Hoje</span>
      </div>
    </div>

    <!-- Calendário -->
    <div class="calendar-grid">
      <div v-for="day in weekDays" :key="day" class="weekday-header">
        {{ day }}
      </div>

      <div
        v-for="day in calendarDays"
        :key="`${day.date}-${day.month}`"
        :class="[
          'calendar-cell',
          {
            'other-month': day.isOtherMonth,
            'today': day.isToday,
            'has-folgas': day.folgas && day.folgas.length > 0,
            'weekend': day.isWeekend
          }
        ]"
        @click="selectDay(day)"
      >
        <div class="day-number">{{ day.day }}</div>
        
        <div v-if="day.folgas && day.folgas.length > 0" class="folgas-container">
          <div
            v-for="folga in day.folgas"
            :key="folga.id"
            :class="[
              'folga-item',
              `tipo-${folga.tipo.toLowerCase()}`,
              { 
                'approved': folga.aprovado === true,
                'rejected': folga.aprovado === false && folga.aprovado !== null,
                'pending': folga.aprovado === null,
                'selected': selectedFolgas.includes(folga.id)
              }
            ]"
            :style="{ 
              backgroundColor: folga.vendedor_cor,
              opacity: folga.aprovado === false ? 0.5 : 1
            }"
            @click.stop="toggleFolgaSelection(folga)"
            :title="`${folga.vendedor_nome} - ${folga.tipo} (${folga.aprovado === null ? 'Pendente' : folga.aprovado ? 'Aprovada' : 'Rejeitada'})`"
          >
            <div class="folga-content">
              <span class="vendedor-initial">{{ folga.vendedor_nome.charAt(0) }}</span>
              <div class="folga-status">
                <svg v-if="folga.aprovado === true" class="status-icon approved" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <svg v-else-if="folga.aprovado === false" class="status-icon rejected" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
                <svg v-else class="status-icon pending" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              </div>
              <div class="action-buttons">
                <button @click.stop="editFolga(folga)" class="action-btn edit">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="m18 2 4 4-14 14H4v-4L18 2zM14.5 5.5 18.5 9.5"/>
                  </svg>
                </button>
                <button @click.stop="deleteFolga(folga)" class="action-btn delete">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de detalhes do dia -->
    <div v-if="selectedDay" class="day-modal-overlay" @click="closeDayModal">
      <div class="day-modal" @click.stop>
        <div class="day-modal-header">
          <h4>{{ formatDate(selectedDay.date) }}</h4>
          <button @click="closeDayModal" class="close-button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="day-modal-content">
          <div v-if="selectedDay.folgas && selectedDay.folgas.length > 0" class="folgas-list">
            <h5>Folgas do dia ({{ selectedDay.folgas.length }}):</h5>
            <div
              v-for="folga in selectedDay.folgas"
              :key="folga.id"
              class="folga-detail-item"
            >
              <div class="folga-header">
                <div class="folga-info">
                  <div
                    class="folga-color"
                    :style="{ backgroundColor: folga.vendedor_cor }"
                  ></div>
                  <div class="folga-details">
                    <span class="vendedor-name">{{ folga.vendedor_nome }}</span>
                    <span class="folga-type">{{ folga.tipo }} - {{ folga.periodo }}</span>
                  </div>
                </div>
                
                <div class="folga-actions">
                  <span :class="['status-badge', getStatusClass(folga)]">
                    {{ getStatusText(folga) }}
                  </span>
                  <button @click="editFolga(folga)" class="btn btn-sm btn-secondary">
                    Editar
                  </button>
                  <button @click="deleteFolga(folga)" class="btn btn-sm btn-danger">
                    Excluir
                  </button>
                </div>
              </div>
              
              <div v-if="folga.motivo" class="folga-motivo">
                <strong>Motivo:</strong> {{ folga.motivo }}
              </div>
            </div>
          </div>

          <div v-else class="no-folgas">
            <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
            <p>Nenhuma folga registrada para este dia.</p>
          </div>

          <div class="day-modal-actions">
            <button @click="addFolga(selectedDay.date)" class="btn btn-primary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
              </svg>
              Adicionar Folga
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de criar/editar folga -->
    <div v-if="showFolgaModal" class="day-modal-overlay" @click="closeFolgaModal">
      <div class="day-modal" @click.stop>
        <div class="day-modal-header">
          <h4>{{ editingFolga ? 'Editar Folga' : 'Adicionar Folga' }}</h4>
          <button @click="closeFolgaModal" class="close-button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="day-modal-content">
          <form @submit.prevent="submitFolga" class="folga-form">
            <div class="form-row">
              <div class="form-group">
                <label for="vendedor">Vendedor:</label>
                <select v-model="folgaForm.vendedor_id" id="vendedor" required>
                  <option value="">Selecione um vendedor</option>
                  <option v-for="vendedor in vendedores" :key="vendedor.id" :value="vendedor.id">
                    {{ vendedor.nome }}
                  </option>
                </select>
              </div>

              <div class="form-group">
                <label for="data">Data:</label>
                <input v-model="folgaForm.data" type="date" id="data" required>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="tipo">Tipo de Folga:</label>
                <select v-model="folgaForm.tipo" id="tipo" required>
                  <option value="FOLGA">Folga</option>
                  <option value="FERIAS">Férias</option>
                  <option value="LICENCA">Licença</option>
                  <option value="FALTA">Falta</option>
                  <option value="MEIO_PERIODO">Meio Período</option>
                </select>
              </div>

              <div class="form-group">
                <label for="periodo">Período:</label>
                <select v-model="folgaForm.periodo" id="periodo">
                  <option value="COMPLETO">Dia Completo</option>
                  <option value="MANHA">Manhã</option>
                  <option value="TARDE">Tarde</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label for="motivo">Motivo:</label>
              <textarea v-model="folgaForm.motivo" id="motivo" rows="3" placeholder="Descreva o motivo..."></textarea>
            </div>

            <div class="form-row" v-if="authStore.userRole === 'ADMIN' || authStore.userRole === 'GERENTE'">
              <div class="form-group">
                <label class="checkbox-label">
                  <input v-model="folgaForm.aprovado" type="checkbox">
                  <span class="checkmark"></span>
                  Aprovar automaticamente
                </label>
              </div>
            </div>

            <div class="form-actions">
              <button type="button" @click="closeFolgaModal" class="btn btn-secondary">
                Cancelar
              </button>
              <button type="submit" class="btn btn-primary" :disabled="loading">
                {{ loading ? 'Salvando...' : editingFolga ? 'Atualizar' : 'Salvar' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Modal de confirmação de exclusão -->
    <div v-if="showDeleteModal" class="day-modal-overlay" @click="cancelDelete">
      <div class="delete-modal" @click.stop>
        <div class="delete-modal-header">
          <div class="warning-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
            </svg>
          </div>
          <h4>Confirmar Exclusão</h4>
        </div>
        
        <div class="delete-modal-content">
          <p v-if="folgaToDelete">
            Tem certeza que deseja excluir a folga de 
            <strong>{{ folgaToDelete.vendedor_nome }}</strong> 
            do dia <strong>{{ formatDate(folgaToDelete.data) }}</strong>?
          </p>
          <p v-else-if="selectedFolgas.length > 1">
            Tem certeza que deseja excluir <strong>{{ selectedFolgas.length }} folgas</strong> selecionadas?
          </p>
        </div>

        <div class="delete-modal-actions">
          <button @click="cancelDelete" class="btn btn-secondary">
            Cancelar
          </button>
          <button @click="confirmDelete" class="btn btn-danger" :disabled="loading">
            {{ loading ? 'Excluindo...' : 'Sim, Excluir' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { vendorsAPI } from '@/services/api'

const authStore = useAuthStore()

// Estado reativo
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth())
const selectedDay = ref<any>(null)
const showFolgaModal = ref(false)
const showDeleteModal = ref(false)
const loading = ref(false)
const editingFolga = ref<any>(null)
const folgaToDelete = ref<any>(null)
const selectedFolgas = ref<string[]>([])

// Dados
const folgas = ref<any[]>([])
const vendedores = ref<any[]>([])

// Filtros
const filters = reactive({
  vendedorId: '',
  tipo: '',
  aprovado: ''
})

// Formulário de folga
const folgaForm = reactive({
  vendedor_id: '',
  data: '',
  tipo: 'FOLGA',
  periodo: 'COMPLETO',
  motivo: '',
  aprovado: false
})

// Constantes
const monthNames = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
]

const weekDays = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

// Computed
const calendarDays = computed(() => {
  const firstDay = new Date(currentYear.value, currentMonth.value, 1)
  const startDate = new Date(firstDay)
  const today = new Date()
  
  startDate.setDate(startDate.getDate() - startDate.getDay())
  
  const days = []
  const currentDate = new Date(startDate)
  
  for (let i = 0; i < 42; i++) {
    const dateStr = currentDate.toISOString().split('T')[0]
    const dayFolgas = filteredFolgas.value.filter(f => f.data === dateStr)
    
    days.push({
      day: currentDate.getDate(),
      date: dateStr,
      month: currentDate.getMonth(),
      isOtherMonth: currentDate.getMonth() !== currentMonth.value,
      isToday: currentDate.toDateString() === today.toDateString(),
      isWeekend: currentDate.getDay() === 0 || currentDate.getDay() === 6,
      folgas: dayFolgas
    })
    
    currentDate.setDate(currentDate.getDate() + 1)
  }
  
  return days
})

const filteredFolgas = computed(() => {
  return folgas.value.filter(folga => {
    if (filters.vendedorId && folga.vendedor_id !== filters.vendedorId) return false
    if (filters.tipo && folga.tipo !== filters.tipo) return false
    if (filters.aprovado !== '') {
      const isApproved = filters.aprovado === 'true'
      if (folga.aprovado !== isApproved) return false
    }
    return true
  })
})

// Métodos de navegação
const previousMonth = () => {
  if (currentMonth.value === 0) {
    currentMonth.value = 11
    currentYear.value--
  } else {
    currentMonth.value--
  }
}

const nextMonth = () => {
  if (currentMonth.value === 11) {
    currentMonth.value = 0
    currentYear.value++
  } else {
    currentMonth.value++
  }
}

// Métodos de seleção
const selectDay = (day: any) => {
  if (!day.isOtherMonth) {
    selectedDay.value = day
  }
}

const closeDayModal = () => {
  selectedDay.value = null
}

const toggleFolgaSelection = (folga: any) => {
  const index = selectedFolgas.value.indexOf(folga.id)
  if (index > -1) {
    selectedFolgas.value.splice(index, 1)
  } else {
    selectedFolgas.value.push(folga.id)
  }
}

// Métodos de folga
const addFolga = (date: string) => {
  editingFolga.value = null
  Object.assign(folgaForm, {
    vendedor_id: '',
    data: date,
    tipo: 'FOLGA',
    periodo: 'COMPLETO',
    motivo: '',
    aprovado: false
  })
  closeDayModal()
  showFolgaModal.value = true
}

const editFolga = (folga: any) => {
  editingFolga.value = folga
  Object.assign(folgaForm, {
    vendedor_id: folga.vendedor_id,
    data: folga.data,
    tipo: folga.tipo,
    periodo: folga.periodo,
    motivo: folga.motivo || '',
    aprovado: folga.aprovado || false
  })
  showFolgaModal.value = true
}

const closeFolgaModal = () => {
  showFolgaModal.value = false
  editingFolga.value = null
  selectedFolgas.value = []
}

const submitFolga = async () => {
  try {
    loading.value = true
    
    const payload = editingFolga.value ? {
      data: folgaForm.data,
      tipo: folgaForm.tipo,
      periodo: folgaForm.periodo,
      motivo: folgaForm.motivo || null,
      aprovado: folgaForm.aprovado
    } : {
      vendedor_id: folgaForm.vendedor_id,
      data: folgaForm.data,
      tipo: folgaForm.tipo,
      periodo: folgaForm.periodo,
      motivo: folgaForm.motivo || null
    }
    
    if (editingFolga.value) {
      await vendorsAPI.updateFolga(editingFolga.value.id, payload)
    } else {
      await vendorsAPI.createFolga(folgaForm.vendedor_id, payload)
    }

    await loadFolgas()
    closeFolgaModal()
    
    // Mostrar mensagem de sucesso
    showNotification(editingFolga.value ? 'Folga atualizada com sucesso!' : 'Folga criada com sucesso!', 'success')
    
  } catch (error: any) {
    showNotification(error.message || 'Erro ao salvar folga', 'error')
  } finally {
    loading.value = false
  }
}

// Métodos de exclusão
const deleteFolga = (folga: any) => {
  folgaToDelete.value = folga
  selectedFolgas.value = []
  showDeleteModal.value = true
}

const deleteSelected = () => {
  if (selectedFolgas.value.length === 0) return
  folgaToDelete.value = null
  showDeleteModal.value = true
}

const cancelDelete = () => {
  showDeleteModal.value = false
  folgaToDelete.value = null
}

const confirmDelete = async () => {
  try {
    loading.value = true
    
    if (folgaToDelete.value) {
      // Excluir uma folga específica
      await vendorsAPI.deleteFolga(folgaToDelete.value.id)
      showNotification('Folga excluída com sucesso!', 'success')
    } else if (selectedFolgas.value.length > 0) {
      // Excluir folgas selecionadas
      const deletePromises = selectedFolgas.value.map(folgaId =>
        vendorsAPI.deleteFolga(folgaId)
      )
      
      await Promise.all(deletePromises)
      showNotification(`${selectedFolgas.value.length} folgas excluídas com sucesso!`, 'success')
    }
    
    await loadFolgas()
    cancelDelete()
    selectedFolgas.value = []
    
  } catch (error) {
    showNotification('Erro ao excluir folga(s)', 'error')
  } finally {
    loading.value = false
  }
}

// Métodos de aprovação em lote
const approveSelected = async () => {
  await bulkUpdateApproval(true)
}

const rejectSelected = async () => {
  await bulkUpdateApproval(false)
}

const bulkUpdateApproval = async (approved: boolean) => {
  try {
    loading.value = true
    
    const updatePromises = selectedFolgas.value.map(folgaId =>
      vendorsAPI.updateFolga(folgaId, { aprovado: approved })
    )
    
    await Promise.all(updatePromises)
    
    const action = approved ? 'aprovadas' : 'rejeitadas'
    showNotification(`${selectedFolgas.value.length} folgas ${action} com sucesso!`, 'success')
    
    selectedFolgas.value = []
    await loadFolgas()
    
  } catch (error) {
    showNotification('Erro ao atualizar folgas', 'error')
  } finally {
    loading.value = false
  }
}

// Métodos utilitários
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('pt-BR', { 
    weekday: 'long',
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  })
}

const getStatusClass = (folga: any) => {
  if (folga.aprovado === true) return 'aprovado'
  if (folga.aprovado === false) return 'rejeitado'
  return 'pendente'
}

const getStatusText = (folga: any) => {
  if (folga.aprovado === true) return 'Aprovada'
  if (folga.aprovado === false) return 'Rejeitada'
  return 'Pendente'
}

const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
  if (window.showNotification) {
    window.showNotification(message, type)
  } else {
    console.log(`${type.toUpperCase()}: ${message}`)
  }
}

// Métodos de carregamento
const loadFolgas = async () => {
  try {
    console.log('Loading folgas for:', currentYear.value, currentMonth.value + 1)
    const data = await vendorsAPI.getFolgasCalendario(currentYear.value, currentMonth.value + 1)
    folgas.value = data || []
    console.log('Folgas loaded:', data?.length || 0)
  } catch (error) {
    console.error('Erro ao carregar folgas:', error)
    showNotification('Erro ao carregar folgas', 'error')
    folgas.value = []
  }
}

const loadVendedores = async () => {
  try {
    console.log('Loading vendedores...')
    const data = await vendorsAPI.getAll()
    vendedores.value = data || []
    console.log('Vendedores loaded:', data?.length || 0)
  } catch (error) {
    console.error('Erro ao carregar vendedores:', error)
    showNotification('Erro ao carregar vendedores', 'error')
    vendedores.value = []
  }
}

// Watchers
watch([currentYear, currentMonth], () => {
  loadFolgas()
})

// Lifecycle
onMounted(() => {
  loadFolgas()
  loadVendedores()
})
</script>

<style scoped>
/* Estilo base do calendário avançado */
.folgas-calendar-advanced {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  overflow: hidden;
}

/* Header com controles */
.calendar-header {
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  background: white;
  color: #1f2937;
}

.header-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.month-navigation {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
}

.nav-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid #e5e7eb;
  background: white;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  color: #6b7280;
}

.nav-button:hover {
  background: #f9fafb;
  color: #1f2937;
}

.nav-button svg {
  width: 1.25rem;
  height: 1.25rem;
}

.month-title {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0;
  text-align: center;
  color: #1f2937;
}

/* Filtros */
.filters {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 120px;
}

.filter-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
}

.filter-group select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  color: #1f2937;
  font-size: 0.875rem;
}

.filter-group select option {
  color: #1f2937;
  background: white;
}

/* Ações em lote */
.bulk-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-top: 1rem;
}

.selected-count {
  font-weight: 600;
  color: #374151;
}

.bulk-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.bulk-btn svg {
  width: 1rem;
  height: 1rem;
}

.bulk-btn.approve {
  background: #374151;
  color: white;
}

.bulk-btn.approve:hover {
  background: #1f2937;
}

.bulk-btn.reject {
  background: #6b7280;
  color: white;
}

.bulk-btn.reject:hover {
  background: #4b5563;
}

.bulk-btn.delete {
  background: #9ca3af;
  color: white;
}

.bulk-btn.delete:hover {
  background: #6b7280;
}

/* Legenda */
.calendar-legend {
  display: flex;
  gap: 1rem;
  padding: 1rem 1.5rem;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.legend-color {
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
}

.legend-color.pending {
  background: #9ca3af;
  border: 1px solid #6b7280;
}

.legend-color.approved {
  background: #374151;
  border: 1px solid #1f2937;
}

.legend-color.rejected {
  background: #d1d5db;
  border: 1px solid #9ca3af;
}

.legend-color.today {
  background: #1f2937;
  border: 2px solid #000000;
}

/* Grid do calendário */
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: #e5e7eb;
  gap: 1px;
}

.weekday-header {
  background: #f9fafb;
  padding: 1rem 0.5rem;
  text-align: center;
  font-weight: 600;
  color: #374151;
  font-size: 0.875rem;
}

.calendar-cell {
  background: white;
  min-height: 120px;
  padding: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  display: flex;
  flex-direction: column;
}

.calendar-cell:hover {
  background: #f9fafb;
}

.calendar-cell.other-month {
  background: #f9fafb;
  opacity: 0.5;
}

.calendar-cell.today {
  background: #dbeafe;
  box-shadow: inset 0 0 0 2px #3b82f6;
}

.calendar-cell.weekend {
  background: #fafafa;
}

.calendar-cell.weekend.other-month {
  background: #f5f5f5;
}

.day-number {
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.25rem;
  align-self: flex-start;
}

.folgas-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

/* Itens de folga no calendário */
.folga-item {
  border-radius: 4px;
  padding: 0.25rem;
  font-size: 0.75rem;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.folga-item:hover {
  transform: scale(1.02);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.folga-item.selected {
  box-shadow: 0 0 0 2px #000000;
  transform: scale(1.05);
}

.folga-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 0.25rem;
}

.vendedor-initial {
  font-weight: 700;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.625rem;
  flex-shrink: 0;
}

.folga-status {
  display: flex;
  align-items: center;
  flex: 1;
  justify-content: center;
}

.status-icon {
  width: 12px;
  height: 12px;
  opacity: 0.8;
}

.status-icon.approved {
  color: rgba(255, 255, 255, 0.9);
}

.status-icon.rejected {
  color: rgba(255, 255, 255, 0.6);
}

.status-icon.pending {
  color: rgba(255, 255, 255, 0.8);
}

.action-buttons {
  display: none;
  gap: 2px;
}

.folga-item:hover .action-buttons {
  display: flex;
}

.action-btn {
  width: 16px;
  height: 16px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  color: white;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.action-btn svg {
  width: 10px;
  height: 10px;
}

/* Estados das folgas */
.folga-item.approved {
  opacity: 1;
}

.folga-item.rejected {
  opacity: 0.4;
}

.folga-item.pending {
  opacity: 0.8;
}

/* Modais */
.day-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1rem;
}

.day-modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.day-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.day-modal-header h4 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
  color: #1f2937;
}

.close-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  background: #f3f4f6;
  border-radius: 6px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.close-button:hover {
  background: #e5e7eb;
  color: #374151;
}

.close-button svg {
  width: 1rem;
  height: 1rem;
}

.day-modal-content {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
}

/* Lista de folgas no modal */
.folgas-list h5 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #1f2937;
}

.folga-detail-item {
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 0.75rem;
  background: #f9fafb;
}

.folga-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.folga-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.folga-color {
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.folga-details {
  display: flex;
  flex-direction: column;
}

.vendedor-name {
  font-weight: 600;
  color: #1f2937;
  font-size: 0.875rem;
}

.folga-type {
  color: #6b7280;
  font-size: 0.75rem;
}

.folga-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.aprovado {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.status-badge.pendente {
  background: #f9fafb;
  color: #6b7280;
  border: 1px solid #e5e7eb;
}

.status-badge.rejeitado {
  background: #f3f4f6;
  color: #9ca3af;
  border: 1px solid #d1d5db;
}

.folga-motivo {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #6b7280;
  font-style: italic;
  padding-top: 0.5rem;
  border-top: 1px solid #e5e7eb;
}

/* Estado vazio */
.no-folgas {
  text-align: center;
  color: #6b7280;
  padding: 3rem 2rem;
}

.empty-icon {
  width: 3rem;
  height: 3rem;
  color: #d1d5db;
  margin: 0 auto 1rem;
}

/* Formulário */
.folga-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-weight: 600;
  color: #1f2937;
  font-size: 0.875rem;
}

.form-group select,
.form-group input,
.form-group textarea {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.form-group select:focus,
.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: 500;
  color: #1f2937;
}

.checkbox-label input[type="checkbox"] {
  margin: 0;
}

.day-modal-actions,
.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid #e5e7eb;
}

/* Botões */
.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.btn-primary {
  background: #1f2937;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #374151;
}

.btn-secondary {
  background: #f3f4f6;
  color: #1f2937;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.btn-danger {
  background: #6b7280;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #4b5563;
}

.btn-sm {
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn svg {
  width: 1rem;
  height: 1rem;
}

/* Modal de confirmação de exclusão */
.delete-modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 400px;
  overflow: hidden;
}

.delete-modal-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.warning-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  background: #f3f4f6;
  border-radius: 50%;
  color: #6b7280;
  flex-shrink: 0;
}

.warning-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.delete-modal-header h4 {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
  color: #1f2937;
}

.delete-modal-content {
  padding: 1.5rem;
}

.delete-modal-content p {
  color: #6b7280;
  line-height: 1.6;
  margin: 0;
}

.delete-modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
}

/* Responsivo */
@media (max-width: 768px) {
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .calendar-cell {
    min-height: 80px;
  }
  
  .folga-item {
    font-size: 0.625rem;
    min-height: 20px;
  }
  
  .vendedor-initial {
    width: 14px;
    height: 14px;
    font-size: 0.5rem;
  }
  
  .bulk-actions {
    flex-direction: column;
    align-items: stretch;
  }
  
  .bulk-actions .bulk-btn {
    justify-content: center;
  }
}
</style>