<template>
  <div class="folgas-card">
    <div class="card-header">
      <div class="header-left">
        <h3 class="card-title">Controle de Folgas</h3>
        <p class="card-subtitle">{{ getCurrentMonth() }}</p>
      </div>
      <div class="header-right">
        <button @click="openFullCalendar" class="expand-button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="card-content">
      <!-- Mini calendário com indicadores -->
      <div class="mini-calendar">
        <div class="mini-calendar-header">
          <button @click="previousMonth" class="mini-nav-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
            </svg>
          </button>
          <span class="mini-month">{{ getShortMonth() }}</span>
          <button @click="nextMonth" class="mini-nav-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
            </svg>
          </button>
        </div>

        <div class="mini-grid">
          <div v-for="day in ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']" :key="day" class="mini-weekday">
            {{ day }}
          </div>
          
          <div
            v-for="day in miniCalendarDays"
            :key="`${day.date}`"
            :class="[
              'mini-day',
              {
                'other-month': day.isOtherMonth,
                'today': day.isToday,
                'has-folgas': day.folgas && day.folgas.length > 0
              }
            ]"
          >
            <span class="mini-day-number">{{ day.day }}</span>
            <div v-if="day.folgas && day.folgas.length > 0" class="mini-indicators">
              <div
                v-for="folga in day.folgas.slice(0, 2)"
                :key="folga.id"
                class="mini-indicator"
                :style="{ backgroundColor: folga.vendedor_cor }"
              ></div>
              <div v-if="day.folgas.length > 2" class="mini-more">+</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Estatísticas rápidas -->
      <div class="quick-stats">
        <div class="stat-item">
          <div class="stat-number">{{ totalFolgasHoje }}</div>
          <div class="stat-label">Folgas Hoje</div>
        </div>
        <div class="stat-item">
          <div class="stat-number">{{ totalFolgasMes }}</div>
          <div class="stat-label">Total do Mês</div>
        </div>
      </div>

      <!-- Ranking de funcionários -->
      <div class="vendedores-ranking">
        <h4 class="ranking-title">Ranking do Mês</h4>
        <div class="ranking-list">
          <div
            v-for="(vendedor, index) in topVendedores"
            :key="vendedor.vendedor_id"
            class="ranking-item"
          >
            <div class="ranking-position">{{ index + 1 }}º</div>
            <div class="ranking-info">
              <div
                class="vendedor-color"
                :style="{ backgroundColor: vendedor.vendedor_cor }"
              ></div>
              <div class="vendedor-details">
                <span class="vendedor-name">{{ vendedor.vendedor_nome }}</span>
                <span class="vendedor-stats">
                  {{ vendedor.dias_trabalhados }}d trabalhados, {{ vendedor.folgas_aprovadas }}d folgas
                </span>
              </div>
            </div>
            <div class="ranking-score">
              <div class="score-bar">
                <div 
                  class="score-fill"
                  :style="{ 
                    width: `${(vendedor.dias_trabalhados / maxDiasTrabalhados) * 100}%`,
                    backgroundColor: vendedor.vendedor_cor 
                  }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal do calendário completo -->
    <div v-if="showFullCalendar" class="calendar-modal-overlay" @click="closeFullCalendar">
      <div class="calendar-modal" @click.stop>
        <div class="modal-header">
          <h2>Calendário de Folgas</h2>
          <button @click="closeFullCalendar" class="modal-close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="modal-content">
          <FolgasCalendarAdvanced />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import FolgasCalendarAdvanced from './FolgasCalendarAdvanced.vue'

const authStore = useAuthStore()

// Estado reativo
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth())
const showFullCalendar = ref(false)

// Dados
const folgas = ref<any[]>([])
const estatisticas = ref<any[]>([])

// Computed
const miniCalendarDays = computed(() => {
  const firstDay = new Date(currentYear.value, currentMonth.value, 1)
  const startDate = new Date(firstDay)
  const today = new Date()
  
  // Ajustar para começar no domingo
  startDate.setDate(startDate.getDate() - startDate.getDay())
  
  const days = []
  const currentDate = new Date(startDate)
  
  // Gerar 35 dias (5 semanas)
  for (let i = 0; i < 35; i++) {
    const dateStr = currentDate.toISOString().split('T')[0]
    const dayFolgas = folgas.value.filter(f => f.data === dateStr)
    
    days.push({
      day: currentDate.getDate(),
      date: dateStr,
      isOtherMonth: currentDate.getMonth() !== currentMonth.value,
      isToday: currentDate.toDateString() === today.toDateString(),
      folgas: dayFolgas
    })
    
    currentDate.setDate(currentDate.getDate() + 1)
  }
  
  return days
})

const totalFolgasHoje = computed(() => {
  const hoje = new Date().toISOString().split('T')[0]
  return folgas.value.filter(f => f.data === hoje && f.aprovado).length
})

const totalFolgasMes = computed(() => {
  return folgas.value.filter(f => f.aprovado).length
})

const topVendedores = computed(() => {
  return estatisticas.value
    .slice()
    .sort((a, b) => b.dias_trabalhados - a.dias_trabalhados)
    .slice(0, 5)
})

const maxDiasTrabalhados = computed(() => {
  return Math.max(...estatisticas.value.map(f => f.dias_trabalhados), 1)
})

// Métodos
const getCurrentMonth = () => {
  const monthNames = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ]
  return `${monthNames[currentMonth.value]} ${currentYear.value}`
}

const getShortMonth = () => {
  const shortMonths = [
    'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
  ]
  return shortMonths[currentMonth.value]
}

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

const openFullCalendar = () => {
  showFullCalendar.value = true
}

const closeFullCalendar = () => {
  showFullCalendar.value = false
}

const loadData = async () => {
  try {
    // Carregar folgas do calendário
    const folgasResponse = await fetch(`/api/vendedores/folgas/calendario?ano=${currentYear.value}&mes=${currentMonth.value + 1}`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })
    
    if (folgasResponse.ok) {
      folgas.value = await folgasResponse.json()
    }

    // Carregar estatísticas
    const statsResponse = await fetch(`/api/vendedores/estatisticas/resumo?ano=${currentYear.value}&mes=${currentMonth.value + 1}`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (statsResponse.ok) {
      const statsData = await statsResponse.json()
      estatisticas.value = statsData.vendedores || []
    }
  } catch (error) {
    console.error('Erro ao carregar dados das folgas:', error)
  }
}

// Watchers
watch([currentYear, currentMonth], () => {
  loadData()
})

// Lifecycle
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.folgas-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 1.5rem 1rem;
  border-bottom: 1px solid #f3f4f6;
}

.header-left {
  flex: 1;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 0.25rem;
}

.card-subtitle {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

.expand-button {
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

.expand-button:hover {
  background: #e5e7eb;
  color: #374151;
}

.expand-button svg {
  width: 1rem;
  height: 1rem;
}

.card-content {
  padding: 1rem 1.5rem 1.5rem;
}

/* Mini Calendário */
.mini-calendar {
  margin-bottom: 1.5rem;
}

.mini-calendar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.mini-nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  background: none;
  color: #6b7280;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.mini-nav-btn:hover {
  background: #f3f4f6;
  color: #374151;
}

.mini-nav-btn svg {
  width: 0.875rem;
  height: 0.875rem;
}

.mini-month {
  font-size: 0.875rem;
  font-weight: 600;
  color: #1f2937;
}

.mini-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.mini-weekday {
  text-align: center;
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
  padding: 0.25rem;
}

.mini-day {
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  border-radius: 4px;
  position: relative;
  cursor: pointer;
  transition: all 0.2s;
}

.mini-day:hover {
  background: #f9fafb;
}

.mini-day.other-month {
  opacity: 0.3;
}

.mini-day.today {
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 600;
}

.mini-day.has-folgas {
  background: #fef3c7;
}

.mini-day.today.has-folgas {
  background: #bfdbfe;
}

.mini-day-number {
  line-height: 1;
}

.mini-indicators {
  position: absolute;
  bottom: 1px;
  display: flex;
  gap: 1px;
}

.mini-indicator {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  opacity: 0.8;
}

.mini-more {
  font-size: 0.5rem;
  color: #6b7280;
  font-weight: 600;
}

/* Estatísticas */
.quick-stats {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-item {
  flex: 1;
  text-align: center;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
}

.stat-number {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}

/* Ranking */
.vendedores-ranking {
  margin-top: 1.5rem;
}

.ranking-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.75rem;
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  background: #f9fafb;
  border-radius: 6px;
}

.ranking-position {
  width: 1.5rem;
  height: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e5e7eb;
  color: #374151;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 50%;
  flex-shrink: 0;
}

.ranking-item:first-child .ranking-position {
  background: #fbbf24;
  color: white;
}

.ranking-item:nth-child(2) .ranking-position {
  background: #9ca3af;
  color: white;
}

.ranking-item:nth-child(3) .ranking-position {
  background: #d97706;
  color: white;
}

.ranking-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.vendedor-color {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.vendedor-details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.vendedor-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vendedor-stats {
  font-size: 0.625rem;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ranking-score {
  width: 3rem;
  flex-shrink: 0;
}

.score-bar {
  width: 100%;
  height: 4px;
  background: #e5e7eb;
  border-radius: 2px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  transition: width 0.3s ease;
  border-radius: 2px;
}

/* Modal */
.calendar-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1rem;
}

.calendar-modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 1000px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.modal-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.modal-close {
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
}

.modal-close:hover {
  background: #e5e7eb;
  color: #374151;
}

.modal-close svg {
  width: 1rem;
  height: 1rem;
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

/* Responsivo */
@media (max-width: 640px) {
  .quick-stats {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .vendedor-details {
    min-width: 0;
  }
  
  .vendedor-name,
  .vendedor-stats {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>