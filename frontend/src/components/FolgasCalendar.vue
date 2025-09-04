<template>
  <div class="folgas-calendar">
    <div class="calendar-header">
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
    </div>

    <div class="calendar-grid">
      <!-- Cabeçalho dos dias da semana -->
      <div v-for="day in weekDays" :key="day" class="weekday-header">
        {{ day }}
      </div>

      <!-- Células do calendário -->
      <div
        v-for="day in calendarDays"
        :key="`${day.date}-${day.month}`"
        :class="[
          'calendar-cell',
          {
            'other-month': day.isOtherMonth,
            'today': day.isToday,
            'has-folgas': day.folgas && day.folgas.length > 0
          }
        ]"
        @click="selectDay(day)"
      >
        <div class="day-number">{{ day.day }}</div>
        
        <!-- Indicadores de folgas por funcionário -->
        <div v-if="day.folgas && day.folgas.length > 0" class="folgas-indicators">
          <div
            v-for="folga in day.folgas.slice(0, 4)"
            :key="folga.id"
            :class="['folga-indicator', `tipo-${folga.tipo.toLowerCase()}`]"
            :style="{ backgroundColor: folga.funcionario_cor }"
            :title="`${folga.vendedor_nome} - ${folga.tipo}`"
          ></div>
          <div v-if="day.folgas.length > 4" class="more-indicator">
            +{{ day.folgas.length - 4 }}
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
            <h5>Folgas do dia:</h5>
            <div
              v-for="folga in selectedDay.folgas"
              :key="folga.id"
              class="folga-item"
            >
              <div class="folga-info">
                <div
                  class="folga-color"
                  :style="{ backgroundColor: folga.vendedor_cor }"
                ></div>
                <div class="folga-details">
                  <span class="funcionario-name">{{ folga.vendedor_nome }}</span>
                  <span class="folga-type">{{ folga.tipo }}</span>
                  <span v-if="folga.periodo !== 'COMPLETO'" class="folga-periodo">
                    ({{ folga.periodo }})
                  </span>
                </div>
                <div class="folga-status">
                  <span :class="['status-badge', folga.aprovado ? 'aprovado' : 'pendente']">
                    {{ folga.aprovado ? 'Aprovado' : 'Pendente' }}
                  </span>
                </div>
              </div>
              <div v-if="folga.motivo" class="folga-motivo">
                {{ folga.motivo }}
              </div>
            </div>
          </div>

          <div v-else class="no-folgas">
            <p>Nenhuma folga registrada para este dia.</p>
          </div>

          <div class="day-modal-actions">
            <button @click="addFolga(selectedDay.date)" class="btn btn-primary">
              Adicionar Folga
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de adicionar folga -->
    <div v-if="showAddModal" class="day-modal-overlay" @click="closeAddModal">
      <div class="day-modal" @click.stop>
        <div class="day-modal-header">
          <h4>Adicionar Folga</h4>
          <button @click="closeAddModal" class="close-button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="day-modal-content">
          <form @submit.prevent="submitFolga" class="folga-form">
            <div class="form-group">
              <label for="vendedor">Vendedor:</label>
              <select v-model="newFolga.vendedor_id" id="vendedor" required>
                <option value="">Selecione um vendedor</option>
                <option v-for="vendedor in vendedores" :key="vendedor.id" :value="vendedor.id">
                  {{ vendedor.nome }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label for="tipo">Tipo de Folga:</label>
              <select v-model="newFolga.tipo" id="tipo" required>
                <option value="FOLGA">Folga</option>
                <option value="FERIAS">Férias</option>
                <option value="LICENCA">Licença</option>
                <option value="FALTA">Falta</option>
                <option value="MEIO_PERIODO">Meio Período</option>
              </select>
            </div>

            <div class="form-group">
              <label for="periodo">Período:</label>
              <select v-model="newFolga.periodo" id="periodo">
                <option value="COMPLETO">Dia Completo</option>
                <option value="MANHA">Manhã</option>
                <option value="TARDE">Tarde</option>
              </select>
            </div>

            <div class="form-group">
              <label for="motivo">Motivo (opcional):</label>
              <textarea v-model="newFolga.motivo" id="motivo" rows="3" placeholder="Descreva o motivo..."></textarea>
            </div>

            <div class="form-actions">
              <button type="button" @click="closeAddModal" class="btn btn-secondary">
                Cancelar
              </button>
              <button type="submit" class="btn btn-primary" :disabled="loading">
                {{ loading ? 'Salvando...' : 'Salvar' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// Estado reativo
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth())
const selectedDay = ref<any>(null)
const showAddModal = ref(false)
const loading = ref(false)

// Dados
const folgas = ref<any[]>([])
const vendedores = ref<any[]>([])

// Nova folga
const newFolga = reactive({
  vendedor_id: '',
  tipo: 'FOLGA',
  periodo: 'COMPLETO',
  motivo: '',
  data: ''
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
  const lastDay = new Date(currentYear.value, currentMonth.value + 1, 0)
  const startDate = new Date(firstDay)
  const today = new Date()
  
  // Ajustar para começar no domingo
  startDate.setDate(startDate.getDate() - startDate.getDay())
  
  const days = []
  const currentDate = new Date(startDate)
  
  // Gerar 42 dias (6 semanas)
  for (let i = 0; i < 42; i++) {
    const dateStr = currentDate.toISOString().split('T')[0]
    const dayFolgas = folgas.value.filter(f => f.data === dateStr)
    
    days.push({
      day: currentDate.getDate(),
      date: dateStr,
      month: currentDate.getMonth(),
      isOtherMonth: currentDate.getMonth() !== currentMonth.value,
      isToday: currentDate.toDateString() === today.toDateString(),
      folgas: dayFolgas
    })
    
    currentDate.setDate(currentDate.getDate() + 1)
  }
  
  return days
})

// Métodos
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

const selectDay = (day: any) => {
  if (!day.isOtherMonth) {
    selectedDay.value = day
  }
}

const closeDayModal = () => {
  selectedDay.value = null
}

const addFolga = (date: string) => {
  newFolga.data = date
  closeDayModal()
  showAddModal.value = true
}

const closeAddModal = () => {
  showAddModal.value = false
  Object.assign(newFolga, {
    vendedor_id: '',
    tipo: 'FOLGA',
    periodo: 'COMPLETO',
    motivo: '',
    data: ''
  })
}

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('pt-BR', { 
    weekday: 'long',
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  })
}

const submitFolga = async () => {
  try {
    loading.value = true
    
    const response = await fetch(`/api/vendedores/${newFolga.vendedor_id}/folgas`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({
        vendedor_id: newFolga.vendedor_id,
        data: newFolga.data,
        tipo: newFolga.tipo,
        periodo: newFolga.periodo,
        motivo: newFolga.motivo || null
      })
    })

    if (!response.ok) {
      throw new Error('Erro ao criar folga')
    }

    await loadFolgas()
    closeAddModal()
  } catch (error) {
    console.error('Erro ao criar folga:', error)
  } finally {
    loading.value = false
  }
}

const loadFolgas = async () => {
  try {
    const response = await fetch(`/api/vendedores/folgas/calendario?ano=${currentYear.value}&mes=${currentMonth.value + 1}`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (response.ok) {
      folgas.value = await response.json()
    }
  } catch (error) {
    console.error('Erro ao carregar folgas:', error)
  }
}

const loadVendedores = async () => {
  try {
    const response = await fetch('/api/vendedores/', {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (response.ok) {
      vendedores.value = await response.json()
    }
  } catch (error) {
    console.error('Erro ao carregar vendedores:', error)
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
.folgas-calendar {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  padding: 1.5rem;
}

.calendar-header {
  margin-bottom: 1.5rem;
}

.month-navigation {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.nav-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border: none;
  background: #f3f4f6;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-button:hover {
  background: #e5e7eb;
}

.nav-button svg {
  width: 1.25rem;
  height: 1.25rem;
}

.month-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.weekday-header {
  background: #f9fafb;
  padding: 0.75rem;
  text-align: center;
  font-weight: 600;
  color: #6b7280;
  font-size: 0.875rem;
}

.calendar-cell {
  background: white;
  min-height: 80px;
  padding: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
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
}

.calendar-cell.has-folgas {
  border-left: 4px solid #3b82f6;
}

.day-number {
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.25rem;
}

.folgas-indicators {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  margin-top: 0.25rem;
}

.folga-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  opacity: 0.8;
}

.more-indicator {
  font-size: 0.625rem;
  color: #6b7280;
  font-weight: 500;
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
}

.day-modal {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.day-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 1.5rem 0;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 1rem;
  margin-bottom: 1rem;
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
}

.close-button svg {
  width: 1rem;
  height: 1rem;
}

.day-modal-content {
  padding: 0 1.5rem 1.5rem;
}

.folgas-list h5 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #1f2937;
}

.folga-item {
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 0.75rem;
}

.folga-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.folga-color {
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
}

.folga-details {
  flex: 1;
}

.funcionario-name {
  font-weight: 600;
  color: #1f2937;
  display: block;
}

.folga-type {
  color: #6b7280;
  font-size: 0.875rem;
}

.folga-periodo {
  color: #6b7280;
  font-size: 0.75rem;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.aprovado {
  background: #d1fae5;
  color: #065f46;
}

.status-badge.pendente {
  background: #fef3c7;
  color: #92400e;
}

.folga-motivo {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #6b7280;
  font-style: italic;
}

.no-folgas {
  text-align: center;
  color: #6b7280;
  padding: 2rem;
}

.day-modal-actions {
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-end;
}

/* Formulário */
.folga-form {
  display: flex;
  flex-direction: column;
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
.form-group textarea {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.875rem;
}

.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #f3f4f6;
  color: #1f2937;
}

.btn-secondary:hover {
  background: #e5e7eb;
}
</style>